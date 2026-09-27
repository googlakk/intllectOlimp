import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.exc import ProgrammingError

from errors import ApplicationError
from feedback.models import LessonFeedback
from services.auth import AuthPrincipal
from services.feedback import clean_feedback, list_lesson_feedback, submit_lesson_feedback


def principal(role="student", student_id=5):
    return AuthPrincipal(profile_id=1, auth_user_id=uuid4(), organization_id=3, role=role, login_name="s", display_name="S",
                         must_change_password=False, teacher_id=None, student_id=student_id, grade=8, access_token="t")


class CleanFeedbackTests(unittest.TestCase):
    def test_empty_feedback_is_not_saved(self):
        self.assertIsNone(clean_feedback(None, None, "   "))

    def test_rating_must_be_one_to_five(self):
        with self.assertRaises(ApplicationError):
            clean_feedback(6, None, None)

    def test_comment_is_trimmed_and_limited(self):
        self.assertEqual(clean_feedback(None, True, "  " + "а" * 3000)["comment"], "а" * 2000)


class SubmitTests(unittest.IsolatedAsyncioTestCase):
    def db(self, commit=None):
        db = MagicMock()
        db.scalar = AsyncMock(return_value=SimpleNamespace(published_version_id=41, active_version_id=42))
        db.commit = commit or AsyncMock()
        db.rollback = AsyncMock()
        return db

    async def test_feedback_is_saved_against_published_version(self):
        db = self.db()
        result = await submit_lesson_feedback(principal(), db, topic_id=9, rating=4, had_errors=True, comment="Опечатка в ответе")
        self.assertEqual(result, {"saved": True})
        saved = db.add.call_args.args[0]
        self.assertIsInstance(saved, LessonFeedback)
        self.assertEqual((saved.student_id, saved.topic_id, saved.lesson_version_id, saved.rating, saved.had_errors),
                         (5, 9, 41, 4, True))

    async def test_skipped_feedback_writes_nothing(self):
        db = self.db()
        self.assertEqual(await submit_lesson_feedback(principal(), db, topic_id=9, rating=None, had_errors=None, comment=""), {"saved": False})
        db.add.assert_not_called()

    async def test_missing_table_does_not_break_the_lesson(self):
        db = self.db(commit=AsyncMock(side_effect=ProgrammingError("insert", {}, Exception("no table"))))
        with self.assertRaises(ApplicationError) as error:
            await submit_lesson_feedback(principal(), db, topic_id=9, rating=5, had_errors=False, comment=None)
        self.assertEqual(error.exception.status_code, 503)
        db.rollback.assert_awaited()

    async def test_only_students_leave_feedback(self):
        with self.assertRaises(ApplicationError) as error:
            await submit_lesson_feedback(principal(role="teacher", student_id=None), self.db(), topic_id=9, rating=5, had_errors=None, comment=None)
        self.assertEqual(error.exception.status_code, 403)


class ListTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_list_with_summary(self):
        feedback = LessonFeedback(id=1, organization_id=3, student_id=5, topic_id=9, lesson_version_id=41, rating=2,
                                  had_errors=True, comment="Неверный ответ в задаче 3", created_at=datetime(2026, 9, 27, tzinfo=timezone.utc))
        row = SimpleNamespace(LessonFeedback=feedback, student_name="Эмир", topic_name="Дроби", subject_id=4, subject_name="Алгебра", grade=8)
        rows, summary = MagicMock(), MagicMock()
        rows.all.return_value = [row]
        summary.one.return_value = (3, 3.6666, 1)
        db = SimpleNamespace(execute=AsyncMock(side_effect=[rows, summary]), rollback=AsyncMock())
        result = await list_lesson_feedback(principal(role="admin", student_id=None), db)
        self.assertTrue(result["available"])
        self.assertEqual(result["summary"], {"total": 3, "average_rating": 3.7, "with_errors": 1})
        self.assertEqual(result["items"][0]["subject_name"], "Алгебра")
        self.assertEqual(result["items"][0]["comment"], "Неверный ответ в задаче 3")

    async def test_missing_table_reports_unavailable(self):
        db = SimpleNamespace(execute=AsyncMock(side_effect=ProgrammingError("select", {}, Exception("no table"))), rollback=AsyncMock())
        result = await list_lesson_feedback(principal(role="admin", student_id=None), db)
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
