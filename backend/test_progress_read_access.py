import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from services.progress import ProgressServiceError
from services.progress_access import list_visible_student_progress, require_progress_topic_visibility
from routes.progress import by_student, by_student_topic, attempts, ProgressInput


class ProgressReadAccessTests(unittest.IsolatedAsyncioTestCase):
    def test_oversized_numeric_response_key_is_rejected_at_input(self):
        with self.assertRaises(ValidationError):
            ProgressInput(student_id=2, topic_id=31, response_details={"9" * 5000: {"value": "x", "outcome": "correct"}})

    async def test_teacher_list_query_filters_exact_subjects_including_raw_answers(self):
        result = MagicMock()
        result.all.return_value = [(SimpleNamespace(), "Дроби", None)]
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        user = SimpleNamespace(role="teacher")
        with patch("services.progress_access.teacher_subject_ids", AsyncMock(return_value=[12])), \
             patch("services.progress_access.serialize_progress", return_value={"response_details": {"0": {"value": "ответ"}}}):
            rows = await list_visible_student_progress(2, db, user=user)
        query = str(db.execute.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("sections.subject_id IN (12)", query)
        self.assertIn("progress.student_id = 2", query)
        self.assertEqual(rows[0]["response_details"]["0"]["value"], "ответ")

    async def test_teacher_without_assignments_gets_no_unrestricted_topic_read(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=None))
        with patch("services.progress_access.teacher_subject_ids", AsyncMock(return_value=[])):
            with self.assertRaises(ProgressServiceError) as denied:
                await require_progress_topic_visibility(31, db, user=SimpleNamespace(role="teacher"))
        self.assertEqual(denied.exception.status_code, 404)
        query = str(db.scalar.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("sections.subject_id IN", query)

    async def test_assigned_topic_guard_does_not_restrict_to_a_grade_ceiling(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=31))
        with patch("services.progress_access.teacher_subject_ids", AsyncMock(return_value=[12])):
            await require_progress_topic_visibility(31, db, user=SimpleNamespace(role="teacher"))
        query = str(db.scalar.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("sections.subject_id IN (12)", query)
        self.assertIn("topics.id = 31", query)
        self.assertNotIn("grade", query)

    async def test_admin_and_student_reads_keep_existing_behavior(self):
        for role in ("admin", "student"):
            with self.subTest(role=role):
                user, db = SimpleNamespace(role=role), SimpleNamespace()
                with patch("services.progress_access.list_student_progress", AsyncMock(return_value=[{"id": 7}])) as original, \
                     patch("services.progress_access.teacher_subject_ids", AsyncMock()) as assignments:
                    self.assertEqual(await list_visible_student_progress(2, db, user=user), [{"id": 7}])
                    await require_progress_topic_visibility(31, db, user=user)
                original.assert_awaited_once_with(2, db)
                assignments.assert_not_awaited()


class ProgressReadRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_student_class_visibility_is_checked_before_list_read(self):
        user, db = SimpleNamespace(role="teacher"), SimpleNamespace()
        with patch("routes.progress.require_student_visibility", AsyncMock(side_effect=RuntimeError("student denied"))) as visibility, \
             patch("routes.progress.list_visible_student_progress", AsyncMock()) as read:
            with self.assertRaisesRegex(RuntimeError, "student denied"):
                await by_student(2, user=user, db=db)
        visibility.assert_awaited_once_with(user, 2, db)
        read.assert_not_awaited()

    async def test_foreign_subject_topic_and_attempts_return_404_without_loading_answers(self):
        user, db = SimpleNamespace(role="teacher"), SimpleNamespace()
        for endpoint, reader in ((by_student_topic, "get_student_topic_progress"), (attempts, "list_attempts")):
            with self.subTest(endpoint=endpoint.__name__):
                with patch("routes.progress.require_student_visibility", AsyncMock()) as visibility, \
                     patch("routes.progress.require_progress_topic_visibility", AsyncMock(side_effect=ProgressServiceError(404, "Урок недоступен."))) as scope, \
                     patch(f"routes.progress.{reader}", AsyncMock()) as read:
                    with self.assertRaises(HTTPException) as denied:
                        await endpoint(2, 31, user=user, db=db)
                self.assertEqual(denied.exception.status_code, 404)
                visibility.assert_awaited_once_with(user, 2, db)
                scope.assert_awaited_once_with(31, db, user=user)
                read.assert_not_awaited()
