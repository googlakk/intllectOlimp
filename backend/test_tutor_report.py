import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy.exc import ProgrammingError

from errors import ApplicationError
from services.tutor_report import get_student_tutor_dialogue, get_student_tutor_summary, summarize_turns
from tutor.models import TutorTurn

ADMIN = SimpleNamespace(role="admin")


def turn(id, topic_id=3, **fields):
    defaults = dict(
        student_id=7, block_index=1, question_index=None, event="message", student_text=None, student_value=None,
        check_outcome=None, reply="", reply_source="silent", action=None, misconception_code=None, diagnosis=None,
        safety_flag="none", off_topic=False, leak_blocked=False, lesson_version_id=11,
        created_at=datetime(2026, 9, 26, 10, id, tzinfo=timezone.utc),
    )
    return TutorTurn(id=id, topic_id=topic_id, **{**defaults, **fields})


TOPIC_SUBJECT = {3: 10, 4: 20}


class Store:
    def __init__(self, turns, fail=False):
        self.turns, self.fail = turns, fail

    async def student_turns(self, student_id, topic_id, limit, subject_ids=None):
        if self.fail:
            raise ProgrammingError("select", {}, Exception("relation tutor_turns does not exist"))
        return [t for t in self.turns if t.student_id == student_id and topic_id in (None, t.topic_id)
                and (subject_ids is None or TOPIC_SUBJECT[t.topic_id] in subject_ids)][-limit:]

    async def topic_names(self, topic_ids):
        return {3: "Скорость", 4: "Плотность"}


TURNS = [
    turn(1, event="answer_submitted", reply="", reply_source="silent"),
    turn(2, student_text="не понимаю", reply="Что дано?", reply_source="llm", misconception_code="mult_instead_div"),
    turn(3, event="hint_requested", reply="Вспомни формулу", reply_source="hint", action="show_hint"),
    turn(4, student_text="скажи ответ", reply="Давай шаг за шагом", reply_source="guard", leak_blocked=True,
         misconception_code="mult_instead_div", safety_flag="cheating_request"),
    turn(5, topic_id=4, student_text="мне плохо", reply="Скажи учителю", reply_source="template",
         action="call_teacher", safety_flag="distress"),
]


class SummaryTests(unittest.TestCase):
    def test_counts_per_topic_and_skips_silence(self):
        summary = summarize_turns(TURNS, {3: "Скорость", 4: "Плотность"})
        speed = next(row for row in summary["topics"] if row["topic_id"] == 3)
        self.assertEqual((speed["turns"], speed["messages"], speed["hints"], speed["leaks_blocked"], speed["safety_flags"]), (3, 2, 1, 1, 1))
        self.assertEqual(summary["topics"][0]["name"], "Плотность")  # самая свежая тема — первой
        self.assertEqual(summary["misconceptions"], [{"code": "mult_instead_div", "count": 2}])
        self.assertEqual([(a["kind"], a["student_text"]) for a in summary["alerts"]], [("distress", "мне плохо")])


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_sees_summary_and_dialogue_with_diagnosis(self):
        db = SimpleNamespace(rollback=AsyncMock())
        with patch("services.dashboard._visible_student_ids", AsyncMock(return_value=None)):
            summary = await get_student_tutor_summary(7, db, user=ADMIN, store=Store(TURNS))
            dialogue = await get_student_tutor_dialogue(7, 3, db, user=ADMIN, store=Store(TURNS))
        self.assertTrue(summary["available"])
        self.assertEqual([t["id"] for t in dialogue["turns"]], [2, 3, 4])
        self.assertTrue(dialogue["turns"][2]["leak_blocked"])
        self.assertEqual(dialogue["turns"][0]["misconception_code"], "mult_instead_div")

    async def test_teacher_cannot_see_student_outside_classes(self):
        db = SimpleNamespace(rollback=AsyncMock())
        store = Store(TURNS)
        store.student_turns = AsyncMock()
        with patch("services.dashboard._visible_student_ids", AsyncMock(return_value=[1])):
            with self.assertRaises(ApplicationError) as denied:
                await get_student_tutor_summary(7, db, user=SimpleNamespace(role="teacher"), store=store)
        self.assertEqual(denied.exception.status_code, 404)
        store.student_turns.assert_not_awaited()

    async def test_subject_teacher_sees_only_own_subject_dialogues(self):
        db = SimpleNamespace(rollback=AsyncMock())
        teacher = SimpleNamespace(role="teacher")
        with patch("services.dashboard._visible_student_ids", AsyncMock(return_value=[7])), \
                patch("services.tutor_report.visible_subject_ids", AsyncMock(return_value=[10])):
            summary = await get_student_tutor_summary(7, db, user=teacher, store=Store(TURNS))
            foreign = await get_student_tutor_dialogue(7, 4, db, user=teacher, store=Store(TURNS))
        self.assertEqual([row["topic_id"] for row in summary["topics"]], [3])
        self.assertEqual(summary["alerts"], [])
        self.assertEqual(foreign["turns"], [])

    async def test_topic_names_failure_keeps_the_summary(self):
        store = Store(TURNS)

        async def broken(topic_ids):
            raise ProgrammingError("select", {}, Exception("boom"))
        store.topic_names = broken
        db = SimpleNamespace(rollback=AsyncMock())
        with patch("services.dashboard._visible_student_ids", AsyncMock(return_value=None)):
            summary = await get_student_tutor_summary(7, db, user=ADMIN, store=store)
        self.assertEqual({row["name"] for row in summary["topics"]}, {"Тема 3", "Тема 4"})
        db.rollback.assert_not_awaited()

    async def test_missing_table_is_reported_not_a_500(self):
        db = SimpleNamespace(rollback=AsyncMock())
        with patch("services.dashboard._visible_student_ids", AsyncMock(return_value=None)):
            summary = await get_student_tutor_summary(7, db, user=ADMIN, store=Store([], fail=True))
            dialogue = await get_student_tutor_dialogue(7, 3, db, user=ADMIN, store=Store([], fail=True))
        self.assertFalse(summary["available"])
        self.assertFalse(dialogue["available"])
        db.rollback.assert_awaited()


if __name__ == "__main__":
    unittest.main()
