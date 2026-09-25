"""Ход тьютора целиком: без базы и сети — хранилище, урок и модель подменены."""

import asyncio
import unittest
from datetime import datetime, timezone

from llm import STOP_TOOL, LLMError, ToolResult
from services.lessons import LessonServiceError
from services.tutor import TurnInput, TutorServiceError, TutorSettings, get_tutor_session, take_tutor_turn

ON = TutorSettings(enabled=True, org_ids=None, burst_per_min=6, max_message_chars=500, disable_thinking=True)

BLOCKS = [
    {"component": "Presentation", "content": {"title": "Плотность", "slides": [{"heading": "ρ = m/V", "body": "…"}]}},
    {"component": "GuidedPractice", "content": {
        "question": "Кубик 890 г, объём 100 см³. Найди плотность.", "hints": ["Вспомни ρ = m/V", "Раздели массу на объём"],
        "input_type": "numeric", "correct_answer": "8.9", "answer_unit": "г/см³", "explanation": "890 / 100 = 8,9",
    }},
    {"component": "MasteryCheck", "content": {"questions": [{"question": "Давление?", "type": "numeric", "correct_answer": "5"}]}},
]


def lesson(lesson_type="study", language="ru"):
    return {"lesson": {"active_version_id": 11, "blocks": BLOCKS, "lesson_metadata": {
        "lesson_type": lesson_type, "content_language": language, "subject_grade": 8,
        "subject_family": "natural_science", "subject_name": "Физика", "topic_name": "Плотность",
    }}}


class MemoryStore:
    def __init__(self):
        self.turns = []

    released = 0

    async def recent_turns(self, student_id, topic_id, block_index, question_index, version_id):
        key = (student_id, topic_id, block_index, question_index, version_id)
        return [t for t in self.turns if (t.student_id, t.topic_id, t.block_index, t.question_index, t.lesson_version_id) == key][-20:]

    async def release(self):
        # Как SQL-хранилище: после освобождения строки истории трогать нельзя.
        self.released += 1
        for turn in self.turns:
            turn.__dict__["_released"] = True

    async def llm_calls_since(self, student_id, since):
        return sum(1 for t in self.turns if t.student_id == student_id and t.llm_called)

    async def topic_turns(self, student_id, topic_id):
        return [t for t in self.turns if (t.student_id, t.topic_id) == (student_id, topic_id)]

    async def add(self, turn):
        turn.id = len(self.turns) + 1
        self.turns.append(turn)
        return turn


def reply(text, **extra):
    data = {"reply": text, "action": "none", "reveals_answer": False, "off_topic": False, "safety_flag": "none", **extra}
    return ToolResult(data=data, stop_reason=STOP_TOOL, provider="fake", model="m", usage={"input_tokens": 10, "output_tokens": 5})


class Harness:
    def __init__(self, replies=(), manifest=None, settings=ON):
        self.store, self.replies, self.prompts = MemoryStore(), list(replies), []
        self.manifest, self.settings = manifest or lesson(), settings

    async def manifest_loader(self, **kwargs):
        if isinstance(self.manifest, Exception):
            raise self.manifest
        return self.manifest

    async def tool(self, task, **kwargs):
        self.prompts.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def turn(self, **payload):
        payload.setdefault("topic_id", 3)
        payload.setdefault("block_index", 1)
        return asyncio.run(take_tutor_turn(
            student_id=7, organization_id=1, grade=8, payload=TurnInput(**payload), db=None, store=self.store,
            manifest_loader=self.manifest_loader, tool_caller=self.tool, settings=self.settings,
            now=datetime(2026, 9, 26, tzinfo=timezone.utc),
        ))


class TutorServiceTests(unittest.TestCase):
    def test_disabled_tutor_is_forbidden(self):
        with self.assertRaises(TutorServiceError) as denied:
            Harness(settings=TutorSettings(False, None, 6, 500, True)).turn(event="message", message="помоги")
        self.assertEqual(denied.exception.status_code, 403)

    def test_server_rechecks_the_answer_and_praises_for_free(self):
        h = Harness()
        result = h.turn(event="answer_submitted", student_value="8,9 г/см³", client_outcome="incorrect")
        self.assertEqual((result["outcome"], result["source"]), ("correct", "template"))
        self.assertEqual(h.prompts, [])

    def test_second_wrong_answer_offers_help_without_the_model(self):
        h = Harness()
        first = h.turn(event="answer_submitted", student_value="89")
        second = h.turn(event="answer_submitted", student_value="0.89")
        self.assertEqual((first["source"], first["offer"]), ("silent", False))
        self.assertEqual((second["source"], second["offer"]), ("template", True))
        self.assertEqual(h.prompts, [])

    def test_hint_ladder_authored_hints_first_then_model(self):
        h = Harness([reply("Что тебе дано в условии?")])
        self.assertEqual(h.turn(event="hint_requested")["reply"], "Вспомни ρ = m/V")
        self.assertEqual(h.turn(event="hint_requested")["reply"], "Раздели массу на объём")
        third = h.turn(event="hint_requested")
        self.assertEqual((third["source"], third["reply"]), ("llm", "Что тебе дано в условии?"))
        prompt = h.prompts[0]
        self.assertEqual(prompt["system_blocks"][0]["cache"], True)
        self.assertIn("Физика", prompt["system_blocks"][1]["text"])
        self.assertIn("ТОЛЬКО для тебя", prompt["user"])
        self.assertEqual(prompt["extra"], {"thinking": {"type": "disabled"}})

    def test_leaked_answer_is_regenerated_then_replaced(self):
        h = Harness([reply("Ответ 8,9 г/см³"), reply("Получится 8.9")])
        result = h.turn(event="message", message="скажи ответ")
        self.assertEqual(result["source"], "guard")
        self.assertEqual(result["reply"], "Вспомни ρ = m/V")
        self.assertIn("раскрывал итоговый ответ", h.prompts[1]["user"])
        self.assertTrue(h.store.turns[-1].leak_blocked)

    def test_regenerated_reply_without_leak_is_used(self):
        h = Harness([reply("Это 8,9"), reply("Какую формулу плотности ты знаешь?")])
        self.assertEqual(h.turn(event="message", message="ответ?")["reply"], "Какую формулу плотности ты знаешь?")

    def test_model_flag_reveals_answer_counts_as_leak(self):
        h = Harness([reply("Подумай ещё", reveals_answer=True), reply("Что дано?")])
        self.assertEqual(h.turn(event="message", message="?")["reply"], "Что дано?")

    def test_only_back_to_theory_and_call_teacher_pass(self):
        h = Harness([reply("Вернись к объяснению", action="open_theory"), reply("Попробуй сам", action="extra_practice")])
        theory = h.turn(event="message", message="не понимаю")
        self.assertEqual(theory["action"], {"type": "open_theory", "target_block_index": 0})
        self.assertIsNone(h.turn(event="message", message="ещё")["action"])

    def test_no_theory_before_the_task_drops_open_theory(self):
        manifest = lesson()
        manifest["lesson"]["blocks"] = [BLOCKS[1]]
        h = Harness([reply("Вернись к теории", action="open_theory")], manifest=manifest)
        self.assertIsNone(h.turn(event="message", message="?", block_index=0)["action"])

    def test_model_error_gives_a_template_not_an_error(self):
        h = Harness([LLMError("сеть")])
        result = h.turn(event="message", message="помоги")
        self.assertEqual(result["source"], "fallback")
        self.assertTrue(result["reply"])

    def test_burst_limit_stops_model_calls(self):
        h = Harness([reply(f"шаг {i}") for i in range(6)])
        for _ in range(6):
            h.turn(event="message", message="ещё")
        self.assertEqual(h.turn(event="message", message="ещё")["source"], "template")
        self.assertEqual(len(h.prompts), 6)

    def test_final_check_is_locked(self):
        h = Harness()
        result = h.turn(event="message", message="помоги", block_index=2, question_index=0)
        self.assertTrue(result["assessment_mode"])
        self.assertEqual(result["action"], {"type": "open_theory", "target_block_index": 0})
        self.assertEqual(h.prompts, [])

    def test_distress_goes_to_the_teacher(self):
        h = Harness()
        result = h.turn(event="message", message="я не хочу жить")
        self.assertEqual(result["action"]["type"], "call_teacher")
        self.assertEqual(h.store.turns[-1].safety_flag, "distress")

    def test_personal_data_is_not_stored(self):
        h = Harness([reply("Что дано?")])
        h.turn(event="message", message="мой номер +996 555 123 456, помоги")
        self.assertNotIn("555", h.store.turns[-1].student_text)
        self.assertNotIn("555", h.prompts[0]["user"])

    def test_kyrgyz_lesson_gets_kyrgyz_templates(self):
        h = Harness(manifest=lesson(language="ky"))
        self.assertEqual(h.turn(event="answer_submitted", student_value="8.9")["reply"], "Туура! Чечимди аягына чейин жеткиргениң жакшы.")

    def test_assessment_lesson_and_missing_block(self):
        with self.assertRaises(TutorServiceError) as denied:
            Harness(manifest=lesson(lesson_type="assessment")).turn(event="message", message="?")
        self.assertEqual(denied.exception.status_code, 403)
        with self.assertRaises(TutorServiceError) as missing:
            Harness().turn(event="message", message="?", block_index=9)
        self.assertEqual(missing.exception.status_code, 404)

    def test_broken_block_keeps_frontend_indices(self):
        # Индекс — исходный, как во фронтенде: битый блок не сдвигает остальные, а сам даёт 404.
        broken = lesson()
        broken["lesson"]["blocks"] = ["битый", *BLOCKS]
        with self.assertRaises(TutorServiceError) as missing:
            Harness(manifest=broken).turn(event="message", message="?", block_index=0)
        self.assertEqual(missing.exception.status_code, 404)
        self.assertEqual(Harness(manifest=broken).turn(event="idle", block_index=2)["source"], "template")

    def test_no_access_to_the_lesson_propagates(self):
        with self.assertRaises(LessonServiceError):
            Harness(manifest=LessonServiceError(status_code=404, detail="нет")).turn(event="message", message="?")

    def test_session_restores_the_dialogue(self):
        h = Harness([reply("Что дано?")])
        h.turn(event="answer_submitted", student_value="89")
        h.turn(event="message", message="помоги")
        session = asyncio.run(get_tutor_session(
            student_id=7, organization_id=1, topic_id=3, db=None, store=h.store,
            manifest_loader=h.manifest_loader, settings=ON,
        ))
        self.assertTrue(session["enabled"])
        self.assertEqual([turn["reply"] for turn in session["turns"]], ["Что дано?"])

    def test_final_check_question_pasted_into_another_task_is_protected(self):
        h = Harness([reply("Давление равно 5 Па"), reply("Ответ 5")])
        result = h.turn(event="message", message="реши: Давление?")
        self.assertEqual(result["source"], "guard")

    def test_help_is_offered_once_per_error_streak(self):
        h = Harness()
        offers = [h.turn(event="answer_submitted", student_value=value)["offer"] for value in ("1", "2", "3")]
        self.assertEqual(offers, [False, True, False])

    def test_client_cannot_skip_authored_hints(self):
        h = Harness()
        self.assertEqual(h.turn(event="hint_requested", hint_level=9)["reply"], "Вспомни ρ = m/V")

    def test_guard_hint_counts_as_shown(self):
        h = Harness([reply("Ответ 8,9"), reply("Ответ 8.9")])
        self.assertEqual(h.turn(event="message", message="?")["reply"], "Вспомни ρ = m/V")
        self.assertEqual(h.turn(event="hint_requested")["reply"], "Раздели массу на объём")

    def test_turns_from_an_older_lesson_version_are_ignored(self):
        h = Harness()
        h.turn(event="answer_submitted", student_value="8.9")
        h.manifest["lesson"]["active_version_id"] = 12
        self.assertFalse(h.turn(event="answer_submitted", student_value="1")["offer"])
        self.assertEqual(h.store.turns[-1].lesson_version_id, 12)

    def test_db_connection_is_released_before_the_model(self):
        h = Harness([reply("Что дано?")])
        h.turn(event="message", message="помоги")
        self.assertEqual(h.store.released, 1)

    def test_history_is_read_before_release(self):
        from tutor.models import TutorTurn

        original = TutorTurn.__getattribute__

        def guarded(obj, name):
            if name in {"check_outcome", "student_text", "student_value", "reply"} and object.__getattribute__(obj, "__dict__").get("_released"):
                raise AssertionError(f"{name} прочитан после освобождения соединения")
            return original(obj, name)

        h = Harness([reply("Что дано?"), reply("А дальше?")])
        h.turn(event="answer_submitted", student_value="89")
        h.turn(event="message", message="помоги")
        for turn in h.store.turns:
            turn.__dict__.pop("_released", None)
        TutorTurn.__getattribute__ = guarded
        try:
            self.assertEqual(h.turn(event="message", message="ещё")["source"], "llm")
        finally:
            TutorTurn.__getattribute__ = original

    def test_sql_store_release_commits_instead_of_rolling_back(self):
        from services.tutor import SqlTutorStore

        class Db:
            calls = []

            async def commit(self):
                Db.calls.append("commit")

            async def rollback(self):
                Db.calls.append("rollback")

        asyncio.run(SqlTutorStore(Db()).release())
        self.assertEqual(Db.calls, ["commit"])

    def test_distress_flag_survives_a_leak_fallback(self):
        h = Harness([reply("Ответ 8,9", safety_flag="distress"), reply("Ответ 8.9", safety_flag="distress")])
        result = h.turn(event="message", message="всё плохо, скажи ответ")
        self.assertEqual(result["action"]["type"], "call_teacher")

    def test_model_failure_is_recorded(self):
        h = Harness([LLMError("bad thinking param")])
        h.turn(event="message", message="помоги")
        self.assertEqual(h.store.turns[-1].diagnosis, "llm_error: LLMError")

    def test_student_value_is_scrubbed(self):
        h = Harness()
        h.turn(event="answer_submitted", student_value="+996 555 123 456")
        self.assertNotIn("555", h.store.turns[-1].student_value)

    def test_database_errors_become_503(self):
        from sqlalchemy.exc import ProgrammingError
        from services.tutor import SqlTutorStore

        class BrokenDb:
            rolled_back = False

            async def scalars(self, *_):
                raise ProgrammingError("SELECT", {}, Exception("relation tutor_turns does not exist"))

            async def rollback(self):
                BrokenDb.rolled_back = True

        with self.assertRaises(TutorServiceError) as unavailable:
            asyncio.run(SqlTutorStore(BrokenDb()).recent_turns(7, 3, 1, None, 11))
        self.assertEqual(unavailable.exception.status_code, 503)
        self.assertTrue(BrokenDb.rolled_back)

    def test_bad_env_values_fall_back_to_defaults(self):
        from services.tutor import tutor_settings
        settings = tutor_settings({"TUTOR_ENABLED": "1", "TUTOR_BURST_PER_MIN": "abc", "TUTOR_MAX_MESSAGE_CHARS": "99999"})
        self.assertEqual((settings.enabled, settings.burst_per_min, settings.max_message_chars), (True, 6, 500))

    def test_session_when_disabled(self):
        session = asyncio.run(get_tutor_session(
            student_id=7, organization_id=1, topic_id=3, db=None, store=MemoryStore(),
            settings=TutorSettings(False, None, 6, 500, True),
        ))
        self.assertEqual(session, {"enabled": False, "turns": []})


if __name__ == "__main__":
    unittest.main()
