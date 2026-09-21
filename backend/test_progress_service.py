import unittest
from types import SimpleNamespace

from models import Student, Topic
from services.progress import (
    ProgressServiceError,
    derive_canonical_mastery,
    derive_mastery_status,
    get_student_topic_progress,
    list_student_progress,
    save_progress_record,
)
from objectives import decompose_objectives


def run(coro):
    import asyncio

    return asyncio.run(coro)


class FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeReadSession:
    def __init__(self, rows=None, scalar_row=None):
        self.rows = rows or []
        self.scalar_row = scalar_row

    async def scalars(self, _statement):
        return FakeScalars(self.rows)

    async def scalar(self, _statement):
        return self.scalar_row


class FakeSaveValidationSession:
    def __init__(self, *, student=None, topic=None):
        self.student = student
        self.topic = topic

    async def get(self, model, _row_id):
        if model is Student:
            return self.student
        if model is Topic:
            return self.topic
        return None


def progress_row(**overrides):
    defaults = {
        "id": 1,
        "student_id": 2,
        "topic_id": 3,
        "status": "in_progress",
        "score": None,
        "mastery_level": None,
        "time_spent_sec": 0,
        "started_at": None,
        "completed_at": None,
        "attempts": 0,
        "current_step": 1,
        "max_opened_step": 1,
        "answers": {},
        "attempts_by_step": {},
        "elapsed_time_sec": 0,
        "objective_evidence": {},
        "objective_mastery": {},
        "mastery_status": "not_assessed",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class MasteryStatusTests(unittest.TestCase):
    def test_fallback_is_kept_without_objective_mastery(self):
        self.assertEqual(derive_mastery_status(None, "not_assessed"), "not_assessed")
        self.assertIsNone(derive_mastery_status({}, None))

    def test_all_mastered_wins(self):
        self.assertEqual(
            derive_mastery_status(
                {
                    "o1": {"status": "mastered"},
                    "o2": {"status": "mastered"},
                },
                "needs_practice",
            ),
            "mastered",
        )

    def test_any_needs_practice_wins_over_in_progress(self):
        self.assertEqual(
            derive_mastery_status(
                {
                    "o1": {"status": "in_progress"},
                    "o2": {"status": "needs_practice"},
                },
                None,
            ),
            "needs_practice",
        )

    def test_non_terminal_mastery_becomes_in_progress(self):
        self.assertEqual(
            derive_mastery_status(
                {
                    "o1": {"status": "not_assessed"},
                    "o2": {"status": "in_progress"},
                },
                None,
            ),
            "in_progress",
        )


class CanonicalMasteryDerivationTests(unittest.TestCase):
    def test_no_objective_mapping_keeps_client_payload(self):
        result = derive_canonical_mastery(
            [{"component": "ShortExplanation", "content": {"text": "Intro"}}],
            None,
            {},
            {},
            lesson_completed=False,
        )

        self.assertIsNone(result)

    def test_derives_mastery_from_canonical_lesson_mapping(self):
        objective_id = decompose_objectives("Понимать правило")[0]["id"]
        result = derive_canonical_mastery(
            [
                {
                    "component": "RetrievalCheck",
                    "content": {
                        "evidence_stage": "diagnostic",
                        "objective_ids": [objective_id],
                    },
                },
                {
                    "component": "IndependentProblem",
                    "content": {
                        "evidence_stage": "assessment",
                        "objective_ids": [objective_id],
                    },
                },
            ],
            "Понимать правило",
            {"0": True, "1": True},
            {"0": 1, "1": 2},
            lesson_completed=True,
        )

        self.assertIsNotNone(result)
        mastery, evidence, status = result
        self.assertEqual(status, "mastered")
        self.assertEqual(mastery[objective_id]["status"], "mastered")
        self.assertEqual(mastery[objective_id]["score"], 100)
        self.assertEqual(evidence[objective_id], [
            {
                "objective_id": objective_id,
                "block_index": 0,
                "stage": "diagnostic",
                "correct": True,
                "attempts": 1,
            },
            {
                "objective_id": objective_id,
                "block_index": 1,
                "stage": "assessment",
                "correct": True,
                "attempts": 2,
            },
        ])


class ProgressReadServiceTests(unittest.TestCase):
    def test_list_student_progress_serializes_rows(self):
        rows = [
            progress_row(id=1, current_step=2),
            progress_row(id=2, status="completed", score=90, mastery_status="mastered"),
        ]

        result = run(list_student_progress(2, FakeReadSession(rows=rows)))

        self.assertEqual([item["id"] for item in result], [1, 2])
        self.assertEqual(result[0]["current_step"], 2)
        self.assertEqual(result[1]["status"], "completed")
        self.assertEqual(result[1]["mastery_status"], "mastered")

    def test_get_student_topic_progress_serializes_row(self):
        row = progress_row(id=10, status="completed", score=75)

        result = run(get_student_topic_progress(2, 3, FakeReadSession(scalar_row=row)))

        self.assertEqual(result["id"], 10)
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["topic_id"], 3)

    def test_get_student_topic_progress_reports_missing_session(self):
        with self.assertRaises(ProgressServiceError) as ctx:
            run(get_student_topic_progress(2, 99, FakeReadSession(scalar_row=None)))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Сессия урока не найдена")


class ProgressSaveValidationTests(unittest.TestCase):
    def _payload(self, **overrides):
        defaults = {
            "student_id": 2,
            "topic_id": 3,
            "score": None,
            "mastery_level": None,
            "time_spent_sec": 0,
            "current_step": 0,
            "max_opened_step": 0,
            "answers": {},
            "attempts_by_step": {},
            "elapsed_time_sec": 0,
            "status": "completed",
            "objective_evidence": None,
            "objective_mastery": None,
            "mastery_status": None,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_missing_student_is_domain_error(self):
        with self.assertRaises(ProgressServiceError) as ctx:
            run(save_progress_record(self._payload(), FakeSaveValidationSession()))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Ученик не найден")

    def test_missing_topic_is_domain_error(self):
        db = FakeSaveValidationSession(student=SimpleNamespace(id=2))

        with self.assertRaises(ProgressServiceError) as ctx:
            run(save_progress_record(self._payload(), db))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Тема не найдена")

    def test_current_step_cannot_exceed_opened_step(self):
        db = FakeSaveValidationSession(
            student=SimpleNamespace(id=2),
            topic=SimpleNamespace(id=3),
        )

        with self.assertRaises(ProgressServiceError) as ctx:
            run(save_progress_record(
                self._payload(status="in_progress", current_step=4, max_opened_step=3),
                db,
            ))

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "Текущий шаг ещё не открыт")


if __name__ == "__main__":
    unittest.main()
