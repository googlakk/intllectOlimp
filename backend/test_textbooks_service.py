import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from llm.base import STOP_TOOL, ToolResult
from services.textbooks import (
    IngestDeps, TextbookServiceError, TextbookSettings, create_textbook, delete_textbook, ingest_textbook,
    process_textbook, section_text,
)
from textbooks.extract import PageText
from textbooks.models import Textbook, TextbookPage, TextbookSection

ON = TextbookSettings(ai_enabled=True, bucket="textbooks")
OFF = TextbookSettings(ai_enabled=False, bucket="textbooks")


class MemoryStore:
    """Как настоящая сессия базы: параллельные операции — ошибка."""

    def __init__(self, book):
        self.book, self.pages_by_index, self.section_rows, self.items = book, {}, [], {}
        self.busy, self.claimable, self.rollbacks = False, True, 0

    async def claim(self, textbook_id, stale_before):
        return self.claimable

    async def rollback(self):
        self.rollbacks += 1

    async def sections(self, textbook_id):
        return list(self.section_rows)

    async def get(self, textbook_id):
        return self.book if self.book.id == textbook_id else None

    async def update(self, textbook_id, **fields):
        for key, value in fields.items():
            setattr(self.book, key, value)

    async def page_states(self, textbook_id):
        return {i: f"{p.source}:{p.status}" for i, p in self.pages_by_index.items()}

    async def save_pages(self, textbook_id, pages):
        if self.busy:
            raise RuntimeError("concurrent operations are not permitted")
        self.busy = True
        await asyncio.sleep(0)
        self.busy = False
        for values in pages:
            page = self.pages_by_index.get(values["page_index"]) or TextbookPage(textbook_id=textbook_id, text="", source="text", status="pending", needs_review=False)
            for key, value in values.items():
                setattr(page, key, value)
            self.pages_by_index[values["page_index"]] = page

    async def pages(self, textbook_id):
        return [self.pages_by_index[i] for i in sorted(self.pages_by_index)]

    async def replace_sections(self, textbook_id, sections):
        self.section_rows = [TextbookSection(id=i + 1, textbook_id=textbook_id, items_status="pending", **s) for i, s in enumerate(sections)]
        return self.section_rows

    async def replace_items(self, textbook_id, section_id, items):
        self.items[section_id] = items

    async def set_section_status(self, section_id, status):
        next(s for s in self.section_rows if s.id == section_id).items_status = status


class Storage:
    def __init__(self, fail=False, size=1000):
        self.fail, self.size = fail, size

    async def object_size(self, *, bucket, path):
        return self.size

    async def create_signed_upload(self, *, bucket, path):
        return f"https://storage/upload/{bucket}/{path}?token=t"

    async def download_bytes(self, *, bucket, path):
        if self.fail:
            raise RuntimeError("storage down")
        return b"%PDF"


def book():
    return Textbook(id=1, organization_id=5, subject_id=11, grade=8, language="ru", title="Физика 8", storage_path="5/x/f.pdf",
                    status="uploaded", progress={})


# Книга из 8 страниц: 0 — обложка-скан, 1–5 — параграфы, 6 — скан с задачами, 7 — оглавление.
TEXT_PAGES = {
    1: "§ 1. Строение вещества\nВещество состоит из моле-\nкул.",
    2: "Продолжение параграфа 1.",
    3: "§ 2. Плотность вещества\nПлотность — масса единицы объёма.",
    4: "Продолжение параграфа 2.",
    5: "Ещё текст.",
    7: "СОДЕРЖАНИЕ\n§ 1. Строение вещества 1\n§ 2. Плотность вещества 3",
}


def fake_extract(data):
    return [PageText(index=i, text=TEXT_PAGES.get(i, ""), is_scan=i not in TEXT_PAGES) for i in range(8)]


def fake_render(data, indices):
    return [(i, b"png") for i in indices]


class Caller:
    def __init__(self, ocr_fails=()):
        self.calls, self.ocr_fails = [], set(ocr_fails)

    async def __call__(self, task, **kwargs):
        self.calls.append((task, kwargs))
        tool = kwargs["tool"]["name"]
        if tool == "textbook_page":
            page = int(kwargs["user"].split("№")[1].rstrip(".")) - 1
            if page in self.ocr_fails:
                raise RuntimeError("model down")
            return ToolResult(data={"text": f"## УПРАЖНЕНИЕ 1\n1. Найдите $\\rho$ (стр. {page})", "printed_page": page,
                                    "uncertain": ["формула"] if page == 6 else []}, stop_reason=STOP_TOOL)
        if tool == "textbook_toc":
            return ToolResult(data={"entries": [
                {"kind": "section", "number": "§ 1", "title": "Строение вещества", "page": 1},
                {"kind": "section", "number": "§ 2", "title": "Плотность вещества", "page": 3},
            ]}, stop_reason=STOP_TOOL)
        return ToolResult(data={"items": [{"kind": "definition", "page": 3, "text": "Плотность — масса единицы объёма."}]},
                          stop_reason=STOP_TOOL)


def run(coro):
    return asyncio.run(coro)


class IngestTests(unittest.TestCase):
    def deps(self, store, settings=ON, caller=None, storage=None):
        return IngestDeps(store=store, storage=storage or Storage(), tool_caller=caller or Caller(), settings=settings,
                          extract=fake_extract, render=fake_render)

    def test_without_ai_flag_book_waits_and_no_model_is_called(self):
        store, caller = MemoryStore(book()), Caller()
        self.assertEqual(run(ingest_textbook(1, self.deps(store, OFF, caller))), "needs_ai")
        self.assertEqual(caller.calls, [])
        self.assertEqual(store.pages_by_index[1].text, "§ 1. Строение вещества\nВещество состоит из молекул.")
        self.assertEqual(store.pages_by_index[6].status, "pending")
        self.assertEqual(store.book.progress["scans_left"], 2)

    def test_full_path_builds_sections_and_items(self):
        store, caller = MemoryStore(book()), Caller()
        self.assertEqual(run(ingest_textbook(1, self.deps(store, caller=caller))), "ready")
        ocr = [kw for task, kw in caller.calls if kw["tool"]["name"] == "textbook_page"]
        self.assertEqual(len(ocr), 2)
        self.assertEqual(ocr[0]["user_images"][0]["media_type"], "image/png")
        self.assertTrue(store.pages_by_index[6].needs_review)  # модель не уверена во фрагменте
        self.assertEqual([(s.number, s.pdf_from, s.pdf_to) for s in store.section_rows], [("§ 1", 1, 2), ("§ 2", 3, 6)])
        self.assertEqual(store.book.page_offset, 0)
        self.assertEqual(store.items[2][0]["kind"], "definition")

    def test_resume_skips_done_pages(self):
        store = MemoryStore(book())
        run(ingest_textbook(1, self.deps(store)))
        store.pages_by_index[2].text, store.pages_by_index[2].source = "Исправлено учителем", "edited"
        caller = Caller()
        run(ingest_textbook(1, self.deps(store, caller=caller)))
        self.assertFalse([kw for task, kw in caller.calls if kw["tool"]["name"] == "textbook_page"])
        self.assertEqual(store.pages_by_index[2].text, "Исправлено учителем")

    def test_failed_recognition_stops_before_structure_with_reason(self):
        store, caller = MemoryStore(book()), Caller(ocr_fails={0})
        self.assertEqual(run(ingest_textbook(1, self.deps(store, caller=caller))), "failed")
        self.assertIn("Не распознано 1 стр. из 2", store.book.error)
        self.assertNotIn("textbook_toc", [kw["tool"]["name"] for task, kw in caller.calls])

    def test_empty_credit_balance_is_explained(self):
        from services.textbooks import _model_error_reason
        self.assertIn("баланс", _model_error_reason(RuntimeError("Your credit balance is too low to access the Anthropic API")))

    def test_failed_page_is_marked_and_retried_next_time(self):
        store = MemoryStore(book())
        run(ingest_textbook(1, self.deps(store, caller=Caller(ocr_fails={0}))))
        self.assertEqual((store.pages_by_index[0].status, store.pages_by_index[0].needs_review), ("failed", True))
        caller = Caller()
        run(ingest_textbook(1, self.deps(store, caller=caller)))
        self.assertEqual([kw["user"] for task, kw in caller.calls if kw["tool"]["name"] == "textbook_page"], ["Страница PDF №1."])

    def test_no_toc_goes_to_review(self):
        store = MemoryStore(book())
        deps = self.deps(store)
        deps.extract = lambda data: [PageText(index=i, text="текст страницы " * 5, is_scan=False) for i in range(4)]
        self.assertEqual(run(ingest_textbook(1, deps)), "needs_review")
        self.assertIn("оглавление", store.book.error)

    def test_storage_failure_marks_book_failed(self):
        store = MemoryStore(book())
        self.assertEqual(run(ingest_textbook(1, self.deps(store, storage=Storage(fail=True)))), "failed")
        self.assertIn("Обработка прервалась", store.book.error)
        self.assertNotIn("storage down", store.book.error)  # подробности — в лог, не учителю
        self.assertEqual(store.rollbacks, 1)

    def test_reprocess_keeps_sections_links_and_done_items(self):
        store = MemoryStore(book())
        run(ingest_textbook(1, self.deps(store)))
        first_sections = store.section_rows
        store.section_rows[1].items_status = "failed"
        caller = Caller()
        self.assertEqual(run(ingest_textbook(1, self.deps(store, caller=caller))), "ready")
        self.assertIs(store.section_rows, first_sections)  # параграфы не пересобраны — привязки тем целы
        tools = [kw["tool"]["name"] for task, kw in caller.calls]
        self.assertNotIn("textbook_toc", tools)
        self.assertEqual(tools.count("textbook_items"), 1)  # только недоделанный параграф

    def test_second_run_of_same_book_does_nothing(self):
        store, caller = MemoryStore(book()), Caller()
        store.claimable = False
        self.assertEqual(run(ingest_textbook(1, self.deps(store, caller=caller))), "busy")
        self.assertEqual(caller.calls, [])

    def test_real_file_size_is_checked(self):
        store = MemoryStore(book())
        self.assertEqual(run(ingest_textbook(1, self.deps(store, storage=Storage(size=200 * 1024 * 1024)))), "failed")
        self.assertIn("150", store.book.error)
        store = MemoryStore(book())
        self.assertEqual(run(ingest_textbook(1, self.deps(store, storage=Storage(size=None)))), "failed")

    def test_sections_are_extracted_concurrently_and_failure_is_isolated(self):
        state = {"now": 0, "peak": 0}

        class SlowCaller(Caller):
            async def __call__(self, task, **kwargs):
                if kwargs["tool"]["name"] != "textbook_items":
                    return await super().__call__(task, **kwargs)
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
                await asyncio.sleep(0.01)
                state["now"] -= 1
                if "§ 1" in kwargs["user"]:
                    raise RuntimeError("model down")
                return await super().__call__(task, **kwargs)

        store = MemoryStore(book())
        self.assertEqual(run(ingest_textbook(1, self.deps(store, caller=SlowCaller()))), "needs_review")
        self.assertEqual(state["peak"], 2)  # оба параграфа — одновременно
        self.assertEqual([s.items_status for s in store.section_rows], ["failed", "done"])

    def test_section_text_has_printed_page_marks(self):
        self.assertEqual(section_text({4: "A", 5: " ", 6: "B"}, 4, 6, 2), "[стр. 2]\nA\n\n[стр. 4]\nB")


class AssignmentDb:
    async def execute(self, statement):
        result = MagicMock()
        result.all.return_value = [(11,)]
        return result

    async def get(self, model, key):
        return SimpleNamespace(id=11, grade=8, name="Физика", instruction_language="ru")


class Db(AssignmentDb):
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        pass


USER = SimpleNamespace(organization_id=5, profile_id=9, teacher_id=3, role="teacher")


class CreateTests(unittest.TestCase):
    def test_creates_book_with_private_path_and_upload_link(self):
        db = Db()
        result = run(create_textbook({"title": "Физика", "subject_id": 11, "grade": 8, "file_name": "Fizika 8 klass.pdf", "file_size": 1000},
                                     db, user=USER, storage=Storage(), settings=ON))
        self.assertTrue(db.added[0].storage_path.startswith("5/"))
        self.assertTrue(db.added[0].storage_path.endswith("/Fizika_8_klass.pdf"))
        self.assertIn("token=", result["upload_url"])

    def test_rejects_book_in_other_language_than_subject(self):
        with self.assertRaises(TextbookServiceError) as error:
            run(create_textbook({"title": "Physics", "subject_id": 11, "grade": 8, "language": "en",
                                 "file_name": "physics.pdf", "file_size": 10}, Db(), user=USER, storage=Storage(), settings=ON))
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn("английский", error.exception.detail)

    def test_english_book_for_english_subject(self):
        class EnglishDb(Db):
            async def get(self, model, key):
                return SimpleNamespace(id=11, grade=8, name="Physics", instruction_language="en")
        db = EnglishDb()
        run(create_textbook({"title": "Physics", "subject_id": 11, "grade": 8, "language": "en",
                             "file_name": "physics.pdf", "file_size": 10}, db, user=USER, storage=Storage(), settings=ON))
        self.assertEqual(db.added[0].language, "en")

    def test_rejects_non_pdf_and_huge_files(self):
        for payload, code in (({"file_name": "a.docx", "file_size": 10}, 422), ({"file_name": "a.pdf", "file_size": 300 * 1024 * 1024}, 413)):
            with self.assertRaises(TextbookServiceError) as error:
                run(create_textbook({"title": "x", "subject_id": 11, "grade": 8, **payload}, Db(), user=USER, storage=Storage(), settings=ON))
            self.assertEqual(error.exception.status_code, code)


async def CLAIM_OK(book_id):
    return True


class AccessTests(unittest.TestCase):
    def test_same_organization_unassigned_subject_is_hidden(self):
        class GetDb(AssignmentDb):
            async def get(self, model, key):
                other = book()
                other.subject_id = 12
                return other

        started = []
        with self.assertRaises(TextbookServiceError) as denied:
            run(process_textbook(1, GetDb(), user=USER, starter=started.append, claim=CLAIM_OK))
        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(started, [])

    def test_book_without_organization_is_hidden(self):
        class GetDb(AssignmentDb):
            async def get(self, model, key):
                orphan = book()
                orphan.organization_id = None
                return orphan

        with self.assertRaises(TextbookServiceError):
            run(process_textbook(1, GetDb(), user=USER, starter=lambda book_id: True, claim=CLAIM_OK))

    def test_other_organization_cannot_process_book(self):
        class GetDb(AssignmentDb):
            async def get(self, model, key):
                return book()  # книга организации 5

        started = []
        with self.assertRaises(TextbookServiceError) as denied:
            run(process_textbook(1, GetDb(), user=SimpleNamespace(organization_id=6), starter=started.append, claim=CLAIM_OK))
        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(started, [])
        result = run(process_textbook(1, GetDb(), user=USER, starter=lambda book_id: started.append(book_id) or True, claim=CLAIM_OK))
        self.assertTrue(result["started"])
        self.assertEqual(started, [1])

    def test_busy_book_is_not_started_again(self):
        class GetDb(AssignmentDb):
            async def get(self, model, key):
                return book()

        async def busy(book_id):
            return False

        started = []
        result = run(process_textbook(1, GetDb(), user=USER, starter=started.append, claim=busy))
        self.assertEqual((result["started"], started), (False, []))


class DeleteTests(unittest.TestCase):
    class Db(AssignmentDb):
        def __init__(self, status="ready"):
            self.row, self.deleted = book(), False
            self.row.status = status

        async def get(self, model, key):
            return self.row

        async def delete(self, row):
            self.deleted = True

        async def commit(self):
            pass

    class Files(Storage):
        removed = []

        async def delete_object(self, *, bucket, path):
            self.removed.append(path)

    def test_book_and_its_file_are_deleted(self):
        db, files = self.Db(), self.Files()
        run(delete_textbook(1, db, user=USER, storage=files, settings=ON))
        self.assertTrue(db.deleted)
        self.assertEqual(files.removed, ["5/x/f.pdf"])

    def test_running_book_is_not_deleted(self):
        from datetime import datetime, timezone
        db = self.Db(status="recognizing")
        db.row.updated_at = datetime.now(timezone.utc)
        with self.assertRaises(TextbookServiceError) as refused:
            run(delete_textbook(1, db, user=USER, storage=self.Files(), settings=ON))
        self.assertEqual(refused.exception.status_code, 409)
        self.assertFalse(db.deleted)


if __name__ == "__main__":
    unittest.main()
