"""Учебники: загрузка PDF и фоновая обработка в «книга → страницы → параграфы → элементы».

Обработка идёт по шагам и возобновляется: готовые страницы не переделываются.
Платные шаги (распознавание сканов, оглавление, элементы) включаются только
флагом TEXTBOOK_AI_ENABLED — без него книга ждёт в статусе «нужен ИИ».
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Protocol

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from languages import LANGUAGE_NAME, normalize_language
from services.auth import AuthPrincipal
from services.teacher_assignments import teacher_subject_ids
from textbooks.cleanup import clean_page_text
from textbooks.extract import PageText, extract_pages, render_pages_png
from textbooks.items import ITEMS_MAX_TOKENS, ITEMS_PROMPT, ITEMS_TOOL, parse_items
from textbooks.models import Textbook, TextbookItem, TextbookPage, TextbookSection
from textbooks.ocr import OCR_MAX_TOKENS, OCR_PROMPT, OCR_TOOL, parse_ocr_page
from textbooks.toc import (
    MIN_CALIBRATION_SHARE, TOC_PROMPT, TOC_TOOL, build_sections, calibrate_offset, find_toc_pages, parse_toc_entries,
)

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 150 * 1024 * 1024
# Обработка, которая дольше этого не обновляла книгу, считается остановившейся (перезапуск сервера).
STALE_AFTER = timedelta(minutes=10)
OCR_CONCURRENCY = 8
# Параграфов разбирается одновременно (у каждого — долгий ответ модели).
ITEMS_CONCURRENCY = 6
TOC_MAX_TOKENS = 8000
SECTION_TEXT_LIMIT = 120_000
RUNNING_STATUSES = ("extracting", "recognizing", "structuring")
UNAVAILABLE = "Учебники временно недоступны"

ToolCaller = Callable[..., Awaitable[Any]]


class TextbookServiceError(ApplicationError):
    pass


@dataclass(frozen=True)
class TextbookSettings:
    ai_enabled: bool
    bucket: str


def textbook_settings(env: dict[str, str] | None = None) -> TextbookSettings:
    env = os.environ if env is None else env
    return TextbookSettings(
        ai_enabled=(env.get("TEXTBOOK_AI_ENABLED") or "").strip().lower() in {"1", "true", "yes"},
        bucket=(env.get("TEXTBOOK_BUCKET") or "textbooks").strip(),
    )


# ---------- Хранилище (база) ----------

class TextbookStore(Protocol):
    async def claim(self, textbook_id: int, stale_before: datetime) -> bool: ...
    async def rollback(self) -> None: ...
    async def sections(self, textbook_id: int) -> list[TextbookSection]: ...
    async def get(self, textbook_id: int) -> Textbook | None: ...
    async def update(self, textbook_id: int, **fields: Any) -> None: ...
    async def page_states(self, textbook_id: int) -> dict[int, str]: ...
    async def save_pages(self, textbook_id: int, pages: list[dict[str, Any]]) -> None: ...
    async def pages(self, textbook_id: int) -> list[TextbookPage]: ...
    async def replace_sections(self, textbook_id: int, sections: list[dict[str, Any]]) -> list[TextbookSection]: ...
    async def replace_items(self, textbook_id: int, section_id: int, items: list[dict[str, Any]]) -> None: ...
    async def set_section_status(self, section_id: int, status: str) -> None: ...


class SqlTextbookStore:
    """Каждая запись — отдельная фиксация: обработка долгая, прогресс не должен теряться."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def claim(self, textbook_id: int, stale_before: datetime) -> bool:
        """Занять книгу в базе: второй запуск (другой процесс, двойной щелчок) её не получит.
        Застрявшую после перезапуска сервера обработку можно занять заново."""
        claimed = await self.db.execute(
            update(Textbook)
            .where(Textbook.id == textbook_id,
                   (Textbook.status.not_in(RUNNING_STATUSES)) | (Textbook.updated_at < stale_before))
            .values(status="extracting", error=None, updated_at=datetime.now(timezone.utc))
            .returning(Textbook.id)
        )
        won = claimed.scalar_one_or_none() is not None
        await self.db.commit()
        return won

    async def rollback(self) -> None:
        await self.db.rollback()

    async def sections(self, textbook_id: int) -> list[TextbookSection]:
        rows = list((await self.db.scalars(
            select(TextbookSection).where(TextbookSection.textbook_id == textbook_id).order_by(TextbookSection.position)
        )).all())
        await self.db.commit()  # не держим транзакцию открытой во время вызовов модели
        return rows

    async def get(self, textbook_id: int) -> Textbook | None:
        book = await self.db.get(Textbook, textbook_id)
        await self.db.commit()
        return book

    async def update(self, textbook_id: int, **fields: Any) -> None:
        book = await self.db.get(Textbook, textbook_id)
        if book is None:
            return
        for key, value in fields.items():
            setattr(book, key, value)
        await self.db.commit()

    async def page_states(self, textbook_id: int) -> dict[int, str]:
        rows = (await self.db.execute(
            select(TextbookPage.page_index, TextbookPage.source, TextbookPage.status)
            .where(TextbookPage.textbook_id == textbook_id)
        )).all()
        await self.db.commit()
        return {row.page_index: f"{row.source}:{row.status}" for row in rows}

    async def save_pages(self, textbook_id: int, pages: list[dict[str, Any]]) -> None:
        existing = {
            page.page_index: page for page in (await self.db.scalars(
                select(TextbookPage).where(
                    TextbookPage.textbook_id == textbook_id,
                    TextbookPage.page_index.in_([page["page_index"] for page in pages]),
                )
            )).all()
        }
        for values in pages:
            current = existing.get(values["page_index"])
            if current is not None and current.source == "edited":
                continue  # учитель исправил страницу, пока шло распознавание, — его правка важнее
            page = current or TextbookPage(textbook_id=textbook_id, page_index=values["page_index"])
            for key, value in values.items():
                setattr(page, key, value)
            self.db.add(page)
        await self.db.commit()

    async def pages(self, textbook_id: int) -> list[TextbookPage]:
        rows = list((await self.db.scalars(
            select(TextbookPage).where(TextbookPage.textbook_id == textbook_id).order_by(TextbookPage.page_index)
        )).all())
        await self.db.commit()
        return rows

    async def replace_sections(self, textbook_id: int, sections: list[dict[str, Any]]) -> list[TextbookSection]:
        await self.db.execute(delete(TextbookSection).where(TextbookSection.textbook_id == textbook_id))
        rows = [TextbookSection(textbook_id=textbook_id, **values) for values in sections]
        self.db.add_all(rows)
        await self.db.commit()
        return rows

    async def replace_items(self, textbook_id: int, section_id: int, items: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(TextbookItem).where(TextbookItem.section_id == section_id))
        self.db.add_all(
            TextbookItem(textbook_id=textbook_id, section_id=section_id, position=position, **values)
            for position, values in enumerate(items)
        )
        await self.db.commit()

    async def set_section_status(self, section_id: int, status: str) -> None:
        section = await self.db.get(TextbookSection, section_id)
        if section is not None:
            section.items_status = status
            await self.db.commit()


class FileStorage(Protocol):
    async def create_signed_upload(self, *, bucket: str, path: str) -> str: ...
    async def delete_object(self, *, bucket: str, path: str) -> None: ...
    async def object_size(self, *, bucket: str, path: str) -> int | None: ...
    async def download_bytes(self, *, bucket: str, path: str) -> bytes: ...


# ---------- Обработка книги ----------

@dataclass
class IngestDeps:
    store: TextbookStore
    storage: FileStorage
    tool_caller: ToolCaller
    settings: TextbookSettings
    extract: Callable[[bytes], list[PageText]] = extract_pages
    render: Callable[[bytes, list[int]], Iterable[tuple[int, bytes]]] = render_pages_png
    log: list[str] = field(default_factory=list)


async def ingest_textbook(textbook_id: int, deps: IngestDeps, *, claimed: bool = False) -> str:
    """Весь путь книги. Возвращает итоговый статус; при ошибке — failed с понятным текстом.

    claimed=True — книгу уже заняли в запросе (process_textbook), повторно не занимаем.
    """
    store = deps.store
    book = await store.get(textbook_id)
    if book is None:
        return "missing"
    if not claimed and not await store.claim(textbook_id, datetime.now(timezone.utc) - STALE_AFTER):
        return "busy"
    try:
        size = await deps.storage.object_size(bucket=deps.settings.bucket, path=book.storage_path)
        if size is None:
            await store.update(textbook_id, status="failed", error="Файл учебника не загружен в хранилище.")
            return "failed"
        if size > MAX_FILE_BYTES:
            await store.update(textbook_id, status="failed", error="Файл больше 150 МБ.")
            return "failed"
        data = await deps.storage.download_bytes(bucket=deps.settings.bucket, path=book.storage_path)
        pages = await asyncio.to_thread(deps.extract, data)
        states = await store.page_states(textbook_id)
        fresh = []
        for page in pages:
            state = states.get(page.index, "")
            # Готовые и исправленные учителем страницы не трогаем — обработка возобновляется.
            if state.endswith(":done") or state.startswith("edited:"):
                continue
            if page.is_scan:
                fresh.append({"page_index": page.index, "source": "ocr", "status": "pending", "text": ""})
            else:
                fresh.append({"page_index": page.index, "source": "text", "status": "done", "text": clean_page_text(page.text)})
        if fresh:
            await store.save_pages(textbook_id, fresh)
        scans = [row.page_index for row in await store.pages(textbook_id) if row.source == "ocr" and row.status != "done"]
        await store.update(textbook_id, page_count=len(pages), progress={"stage": "extracted", "pages": len(pages), "scans_left": len(scans)})

        if not deps.settings.ai_enabled:
            await store.update(textbook_id, status="needs_ai", progress={
                "stage": "needs_ai", "pages": len(pages), "scans_left": len(scans),
            })
            return "needs_ai"

        if scans:
            await store.update(textbook_id, status="recognizing")
            failed, reason = await _recognize(textbook_id, data, scans, deps, len(pages))
            if failed:
                # Без части страниц (часто это оглавление в конце) разбор даст неверные параграфы.
                await store.update(textbook_id, status="failed", error=(
                    f"Не распознано {failed} стр. из {len(scans)}{f': {reason}' if reason else ''}. "
                    "Нажмите «Запустить обработку» — распознаются только недостающие страницы."
                ))
                return "failed"

        await store.update(textbook_id, status="structuring")
        status = await _structure(textbook_id, book.language, deps)
        await store.update(textbook_id, status=status)
        return status
    except Exception as exc:  # книга не должна «зависнуть» в обработке
        logger.warning("Textbook %s ingest failed: %s: %s", textbook_id, exc.__class__.__name__, str(exc)[:300])
        try:
            await store.rollback()  # после ошибки базы сессия иначе не даст записать статус
            await store.update(textbook_id, status="failed",
                               error=f"Обработка прервалась ({exc.__class__.__name__}). Запустите её ещё раз.")
        except Exception as write_exc:
            logger.warning("Textbook %s failure status not saved: %s", textbook_id, write_exc.__class__.__name__)
        return "failed"


def _model_error_reason(exc: Exception) -> str:
    """Понятная учителю причина сбоя модели (без ключей и технических подробностей)."""
    text = str(exc).lower()
    if "credit balance" in text or "billing" in text:
        return "закончился баланс API Anthropic — пополните его в Plans & Billing"
    if "rate" in text and "limit" in text:
        return "превышен лимит запросов к модели — повторите позже"
    if "overloaded" in text:
        return "модель перегружена — повторите позже"
    return "ошибка модели"


async def _recognize(textbook_id: int, data: bytes, indices: list[int], deps: IngestDeps, total: int) -> tuple[int, str]:
    """Возвращает число нераспознанных страниц и причину последнего сбоя модели."""
    from llm.router import TASK_TEXTBOOK_OCR

    semaphore = asyncio.Semaphore(OCR_CONCURRENCY)
    done = 0
    failed = 0
    reasons: list[str] = []

    async def one(index: int, png: bytes) -> tuple[int, dict[str, Any] | None]:
        import base64

        async with semaphore:
            try:
                result = await deps.tool_caller(
                    TASK_TEXTBOOK_OCR, system=OCR_PROMPT, user=f"Страница PDF №{index + 1}.", tool=OCR_TOOL,
                    max_tokens=OCR_MAX_TOKENS, user_images=[{"media_type": "image/png", "data": base64.b64encode(png).decode()}],
                )
                page = parse_ocr_page(getattr(result, "data", None) or {}) if getattr(result, "ok", False) else None
            except Exception as exc:
                logger.warning("Textbook %s page %s OCR failed: %s", textbook_id, index, exc.__class__.__name__)
                reasons.append(_model_error_reason(exc))
                page = None
        return index, page

    # Рендер — работа процессора: по несколько страниц в потоке, чтобы не держать все картинки в памяти.
    for start in range(0, len(indices), OCR_CONCURRENCY * 2):
        chunk = indices[start:start + OCR_CONCURRENCY * 2]
        images = await asyncio.to_thread(lambda part=chunk: list(deps.render(data, part)))
        results = await asyncio.gather(*(one(index, png) for index, png in images))
        # Запись — после пачки и по очереди: одна сессия базы не допускает параллельных операций.
        await deps.store.save_pages(textbook_id, [
            {"page_index": index, "source": "ocr", "status": "failed", "needs_review": True}
            if page is None or not page["text"] else
            {"page_index": index, "source": "ocr", "status": "done", "text": page["text"],
             "printed_page": page["printed_page"], "uncertain": page["uncertain"], "figures": page["figures"],
             "needs_review": bool(page["uncertain"])}
            for index, page in results
        ])
        done += len(results)
        failed += sum(1 for _index, page in results if page is None or not page["text"])
        if reasons and reasons[-1].startswith("закончился баланс"):
            break  # без денег на счёте дальше каждая страница упадёт — не тратим время
        await deps.store.update(textbook_id, progress={"stage": "recognizing", "pages": total, "scans_left": len(indices) - done})
    failed += len(indices) - done  # не дошли из-за остановки
    return failed, (reasons[-1] if reasons else "")


async def _structure(textbook_id: int, language: str, deps: IngestDeps) -> str:
    """Оглавление → параграфы → элементы. Возвращает ready или needs_review."""
    from llm.router import TASK_TEXTBOOK_STRUCTURE

    rows = await deps.store.pages(textbook_id)
    pages = [PageText(index=row.page_index, text=row.text or "", is_scan=row.source == "ocr") for row in rows]
    book = await deps.store.get(textbook_id)
    existing = await deps.store.sections(textbook_id)
    if existing:
        # Параграфы уже есть: не пересобираем — к ним привязаны темы КТП и правки учителя.
        # Дорабатываем только элементы параграфов, которые ещё не готовы.
        return await _extract_items(textbook_id, existing, pages, book.page_offset if book else 0, None, deps)
    toc_pages = find_toc_pages(pages)
    if not toc_pages:
        await deps.store.update(textbook_id, error="Не найдено оглавление — параграфы нужно разметить вручную.")
        return "needs_review"
    toc_text = "\n\n".join(pages[index].text for index in toc_pages)
    result = await deps.tool_caller(
        TASK_TEXTBOOK_STRUCTURE, system=TOC_PROMPT, user=toc_text, tool=TOC_TOOL, max_tokens=TOC_MAX_TOKENS,
    )
    entries = parse_toc_entries(getattr(result, "data", None) or {}) if getattr(result, "ok", False) else []
    if not entries:
        await deps.store.update(textbook_id, error="Не удалось разобрать оглавление.")
        return "needs_review"
    offset, share = calibrate_offset(entries, pages, toc_pages)
    # Оглавление в конце книги — последний параграф на него не заходит.
    stop = toc_pages[0] if toc_pages[0] > len(pages) // 2 else None
    sections = build_sections(entries, len(pages), offset, stop_index=stop)
    saved = await deps.store.replace_sections(textbook_id, [
        {"position": position, "number": section.number, "title": section.title, "chapter": section.chapter,
         "printed_page": section.printed_page, "pdf_from": section.pdf_from, "pdf_to": section.pdf_to}
        for position, section in enumerate(sections)
    ])
    await deps.store.update(textbook_id, page_offset=offset, progress={
        "stage": "items", "sections": len(saved), "calibration": round(share, 2), "items_done": 0,
    })
    status = await _extract_items(textbook_id, saved, pages, offset, share, deps)
    return "needs_review" if share < MIN_CALIBRATION_SHARE else status


async def _extract_items(textbook_id: int, sections: list[TextbookSection], pages: list[PageText], offset: int | None,
                         share: float | None, deps: IngestDeps) -> str:
    from llm.router import TASK_TEXTBOOK_STRUCTURE

    by_index = {page.index: page.text for page in pages}
    failed = 0
    todo = [section for section in sections if section.items_status != "done"]

    async def extract(section: TextbookSection) -> list[dict[str, Any]] | None:
        text = section_text(by_index, section.pdf_from, section.pdf_to, offset)
        try:
            result = await deps.tool_caller(
                TASK_TEXTBOOK_STRUCTURE, system=ITEMS_PROMPT,
                user=f"Параграф: {section.number} {section.title}\n\n{text}", tool=ITEMS_TOOL, max_tokens=ITEMS_MAX_TOKENS,
            )
            return parse_items(getattr(result, "data", None) or {}) if getattr(result, "ok", False) else None
        except Exception as exc:
            logger.warning("Textbook %s section %s items failed: %s", textbook_id, section.id, exc.__class__.__name__)
            return None

    # Параграфы независимы: модель разбирает несколько сразу; запись в базу — по очереди после пачки
    # (одна сессия базы не допускает параллельных операций).
    done = 0
    for start in range(0, len(todo), ITEMS_CONCURRENCY):
        chunk = todo[start:start + ITEMS_CONCURRENCY]
        results = await asyncio.gather(*(extract(section) for section in chunk))
        for section, items in zip(chunk, results):
            if items is None:
                failed += 1
                await deps.store.set_section_status(section.id, "failed")
            else:
                await deps.store.replace_items(textbook_id, section.id, items)
                await deps.store.set_section_status(section.id, "done")
        done += len(chunk)
        await deps.store.update(textbook_id, progress={
            "stage": "items", "sections": len(sections), "items_left": len(todo) - done,
            **({"calibration": round(share, 2)} if share is not None else {}),
        })
    return "needs_review" if failed else "ready"


def section_text(pages: dict[int, str], pdf_from: int, pdf_to: int, offset: int | None) -> str:
    """Текст параграфа с метками печатных страниц — модели и учителю нужны ссылки «стр. N»."""
    parts = []
    for index in range(pdf_from, pdf_to + 1):
        text = pages.get(index, "").strip()
        if text:
            printed = index - (offset or 0)
            parts.append(f"[стр. {printed}]\n{text}")
    return "\n\n".join(parts)[:SECTION_TEXT_LIMIT]


# ---------- Запуск в фоне ----------

_running: dict[int, asyncio.Task[Any]] = {}


def start_ingest(textbook_id: int) -> bool:
    """Обработка в фоне того же процесса (книга уже занята в базе запросом)."""
    task = _running.get(textbook_id)
    if task is not None and not task.done():
        return False
    _running[textbook_id] = asyncio.get_running_loop().create_task(_run_ingest(textbook_id))
    return True


async def _run_ingest(textbook_id: int) -> None:
    from database import AsyncSessionLocal
    from llm import call_tool
    from storage import SupabaseStorage

    try:
        async with AsyncSessionLocal() as db:
            await ingest_textbook(textbook_id, IngestDeps(
                store=SqlTextbookStore(db), storage=SupabaseStorage(), tool_caller=call_tool, settings=textbook_settings(),
            ), claimed=True)
    finally:
        _running.pop(textbook_id, None)


# ---------- Операции для учителя и админа ----------

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _require_access(book: Textbook | None, user: AuthPrincipal) -> Textbook:
    # Книга без организации не «общая»: её не видит никто (например, после удаления организации).
    if book is None or book.organization_id is None or book.organization_id != user.organization_id:
        raise TextbookServiceError(404, "Учебник не найден")
    return book


async def _require_book_access(book: Textbook | None, user: AuthPrincipal, db: AsyncSession) -> Textbook:
    book = _require_access(book, user)
    if user.role != "admin" and book.subject_id not in await teacher_subject_ids(user, db):
        raise TextbookServiceError(404, "Учебник не относится к назначенным предметам")
    return book


async def _guarded(db: AsyncSession, action: Awaitable[Any]) -> Any:
    try:
        return await action
    except SQLAlchemyError as exc:
        logger.warning("Textbook store failed: %s", exc.__class__.__name__)
        await db.rollback()
        raise TextbookServiceError(503, UNAVAILABLE) from exc


def _stalled(book: Textbook) -> bool:
    """Обработка «застряла»: статус рабочий, а книга давно не обновлялась (сервер перезапускался)."""
    updated = book.updated_at
    return (book.status in RUNNING_STATUSES and updated is not None
            and updated < datetime.now(timezone.utc) - STALE_AFTER and book.id not in _running)


def serialize_textbook(book: Textbook) -> dict[str, Any]:
    return {
        "stalled": _stalled(book),
        "id": book.id, "title": book.title, "authors": book.authors, "year": book.year, "grade": book.grade,
        "subject_id": book.subject_id, "language": book.language, "status": book.status, "progress": book.progress or {},
        "page_count": book.page_count, "page_offset": book.page_offset, "student_display": book.student_display,
        "error": book.error, "created_at": book.created_at.isoformat() if book.created_at else None,
    }


def require_same_language(book_language: str, subject: Any) -> None:
    """Уроки предмета строятся по его учебникам — языки должны совпадать."""
    subject_language = subject.instruction_language or "ru"
    if book_language != subject_language:
        raise TextbookServiceError(422, (
            f"Учебник на языке «{LANGUAGE_NAME.get(book_language, book_language)}», а предмет «{subject.name}» "
            f"ведётся на языке «{LANGUAGE_NAME.get(subject_language, subject_language)}». "
            "Выберите учебник на языке предмета."
        ))


async def create_textbook(payload: dict[str, Any], db: AsyncSession, *, user: AuthPrincipal,
                          storage: FileStorage | None = None, settings: TextbookSettings | None = None) -> dict[str, Any]:
    language = normalize_language(payload.get("language"))
    if payload.get("subject_id") is not None:
        from models import Subject
        chosen = await _guarded(db, db.get(Subject, payload["subject_id"]))
        if chosen is not None:
            require_same_language(language, chosen)
    if user.role != "admin":
        subject_id = payload.get("subject_id")
        from services.educator_access import require_subject_management
        if subject_id is None:
            raise TextbookServiceError(403, "Выберите назначенный вам предмет")
        subject = await require_subject_management(user, subject_id, db)
        if subject.grade != int(payload["grade"]):
            raise TextbookServiceError(422, "Учебник должен соответствовать классу предмета")
    settings = settings or textbook_settings()
    if int(payload.get("file_size") or 0) > MAX_FILE_BYTES:
        raise TextbookServiceError(413, "Файл больше 150 МБ")
    if user.organization_id is None:
        raise TextbookServiceError(403, "Учебник загружается от имени школы")
    if not str(payload.get("file_name") or "").lower().endswith(".pdf"):
        raise TextbookServiceError(422, "Нужен файл PDF")
    safe = _SAFE_NAME.sub("_", str(payload["file_name"]))[-80:] or "book.pdf"
    path = f"{user.organization_id}/{uuid.uuid4().hex}/{safe}"
    if storage is None:
        from storage import SupabaseStorage
        storage = SupabaseStorage()
    try:
        upload_url = await storage.create_signed_upload(bucket=settings.bucket, path=path)
    except Exception as exc:
        logger.warning("Textbook upload link failed: %s", exc.__class__.__name__)
        raise TextbookServiceError(503, "Хранилище учебников недоступно") from exc
    book = Textbook(
        organization_id=user.organization_id, subject_id=payload.get("subject_id"), grade=int(payload["grade"]),
        language=language, title=str(payload["title"]).strip()[:300],
        authors=(str(payload.get("authors") or "").strip()[:300] or None), year=payload.get("year"),
        storage_path=path, file_size=payload.get("file_size"), status="uploaded", progress={},
        created_by_profile_id=user.profile_id,
    )
    db.add(book)
    await _guarded(db, db.commit())
    return {"textbook": serialize_textbook(book), "upload_url": upload_url}


async def process_textbook(textbook_id: int, db: AsyncSession, *, user: AuthPrincipal,
                           starter: Callable[[int], bool] = start_ingest,
                           claim: Callable[[int], Awaitable[bool]] | None = None) -> dict[str, Any]:
    """Книга занимается прямо в запросе: интерфейс сразу видит «идёт обработка» и начинает опрос."""
    await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    if claim is None:
        store = SqlTextbookStore(db)
        claim = lambda book_id: store.claim(book_id, datetime.now(timezone.utc) - STALE_AFTER)  # noqa: E731
    won = await _guarded(db, claim(textbook_id))
    started = bool(won) and starter(textbook_id)
    # UPDATE через ORM синхронизирует объект в сессии: статус уже «extracting».
    book = await _guarded(db, db.get(Textbook, textbook_id))
    return {"textbook": serialize_textbook(book), "started": started}


async def delete_textbook(textbook_id: int, db: AsyncSession, *, user: AuthPrincipal,
                          storage: FileStorage | None = None, settings: TextbookSettings | None = None) -> None:
    """Удалить учебник целиком: файл в хранилище, страницы, параграфы, элементы и привязки тем.
    Во время обработки удалять нельзя — сначала дождаться окончания (или остановки)."""
    settings = settings or textbook_settings()
    book = await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    if book.status in RUNNING_STATUSES and not _stalled(book):
        raise TextbookServiceError(409, "Идёт обработка — удалить учебник можно после её окончания")
    if storage is None:
        from storage import SupabaseStorage
        storage = SupabaseStorage()
    try:
        await storage.delete_object(bucket=settings.bucket, path=book.storage_path)
    except Exception as exc:
        raise TextbookServiceError(503, "Хранилище учебников недоступно — попробуйте позже") from exc
    await _guarded(db, db.delete(book))  # страницы, параграфы, элементы и привязки удаляются каскадом
    await _guarded(db, db.commit())


async def list_textbooks(db: AsyncSession, *, user: AuthPrincipal) -> list[dict[str, Any]]:
    statement = select(Textbook).where(Textbook.organization_id == user.organization_id)
    if user.role != "admin":
        statement = statement.where(Textbook.subject_id.in_(await teacher_subject_ids(user, db)))
    books = await _guarded(db, db.scalars(statement.order_by(Textbook.grade, Textbook.title)))
    return [serialize_textbook(book) for book in books.all()]


async def get_textbook(textbook_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    book = await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    sections = (await _guarded(db, db.scalars(
        select(TextbookSection).where(TextbookSection.textbook_id == textbook_id).order_by(TextbookSection.position)
    ))).all()
    counts: dict[int, int] = {}
    for section_id in (await _guarded(db, db.scalars(
        select(TextbookItem.section_id).where(TextbookItem.textbook_id == textbook_id)
    ))).all():
        counts[section_id] = counts.get(section_id, 0) + 1
    review = (await _guarded(db, db.scalars(
        select(TextbookPage.page_index).where(TextbookPage.textbook_id == textbook_id, TextbookPage.needs_review.is_(True))
    ))).all()
    return {
        "textbook": serialize_textbook(book),
        "pages_to_review": list(review),
        "sections": [
            {"id": section.id, "number": section.number, "title": section.title, "chapter": section.chapter,
             "printed_page": section.printed_page, "pdf_from": section.pdf_from, "pdf_to": section.pdf_to,
             "items_status": section.items_status, "items": counts.get(section.id, 0)}
            for section in sections
        ],
    }


async def get_section(textbook_id: int, section_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    """Параграф для просмотра учителем: текст со страницами и выделенные элементы."""
    book = await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    section = await _guarded(db, db.get(TextbookSection, section_id))
    if section is None or section.textbook_id != book.id:
        raise TextbookServiceError(404, "Параграф не найден")
    pages = (await _guarded(db, db.scalars(
        select(TextbookPage).where(TextbookPage.textbook_id == book.id,
                                   TextbookPage.page_index.between(section.pdf_from, section.pdf_to))
    ))).all()
    items = (await _guarded(db, db.scalars(
        select(TextbookItem).where(TextbookItem.section_id == section.id).order_by(TextbookItem.position)
    ))).all()
    return {
        "section": {"id": section.id, "number": section.number, "title": section.title, "chapter": section.chapter,
                    "printed_page": section.printed_page, "pdf_from": section.pdf_from, "pdf_to": section.pdf_to,
                    "items_status": section.items_status},
        "pages": [_serialize_page(page, book.page_offset) for page in sorted(pages, key=lambda page: page.page_index)],
        "items": [{"id": item.id, "kind": item.kind, "label": item.label, "page": item.page, "text": item.text,
                   "answer": item.answer, "difficulty": item.difficulty} for item in items],
    }


def _serialize_page(page: TextbookPage, offset: int | None) -> dict[str, Any]:
    return {
        "page_index": page.page_index,
        "printed_page": page.printed_page if page.printed_page is not None else page.page_index - (offset or 0),
        "text": page.text, "source": page.source, "status": page.status,
        "needs_review": page.needs_review, "uncertain": page.uncertain or [],
    }


async def update_page(textbook_id: int, page_index: int, text: str, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    """Учитель исправил распознанный текст: страница помечается «исправлено» и не перезаписывается обработкой."""
    book = await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    page = await _guarded(db, db.scalar(
        select(TextbookPage).where(TextbookPage.textbook_id == book.id, TextbookPage.page_index == page_index)
    ))
    if page is None:
        raise TextbookServiceError(404, "Страница не найдена")
    page.text, page.source, page.status, page.needs_review, page.uncertain = text.strip(), "edited", "done", False, []
    # Элементы параграфа выделены из старого текста — при следующей обработке выделяются заново.
    for section in (await _guarded(db, db.scalars(
        select(TextbookSection).where(TextbookSection.textbook_id == book.id,
                                      TextbookSection.pdf_from <= page_index, TextbookSection.pdf_to >= page_index)
    ))).all():
        section.items_status = "stale"
    await _guarded(db, db.commit())
    return _serialize_page(page, book.page_offset)


async def set_textbook_subject(textbook_id: int, subject_id: int, db: AsyncSession, *, user: AuthPrincipal) -> dict[str, Any]:
    """Указать предмет КТП, к темам которого привязывается учебник."""
    from services.educator_access import require_subject_management

    book = await _require_book_access(await _guarded(db, db.get(Textbook, textbook_id)), user, db)
    subject = await require_subject_management(user, subject_id, db)
    if subject.grade != book.grade:
        raise TextbookServiceError(422, "Предмет другого класса")
    require_same_language(book.language, subject)
    if book.subject_id != subject_id:
        # Связи тем прежнего предмета с этой книгой снимаются — иначе генерация продолжила бы ими пользоваться.
        from models import Section, Topic
        from textbooks.models import TopicTextbookLink

        new_topics = select(Topic.id).join(Section, Section.id == Topic.section_id).where(Section.subject_id == subject_id)
        book_sections = select(TextbookSection.id).where(TextbookSection.textbook_id == book.id)
        await _guarded(db, db.execute(delete(TopicTextbookLink).where(
            TopicTextbookLink.section_id.in_(book_sections), TopicTextbookLink.topic_id.not_in(new_topics),
        )))
    book.subject_id = subject_id
    await _guarded(db, db.commit())
    return serialize_textbook(book)
