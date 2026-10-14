import unittest
from datetime import datetime
from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from models import AccountEvent, Classroom, ClassroomStudent, Student
from services.accounts import reset_temporary_password, set_account_blocked, transfer_student
from services.auth import AuthServiceError
from services.student_lifecycle import list_removed_students, remove_student, restore_student
from test_accounts_service import profile
from test_auth_dependencies import principal


class StudentLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = principal(role="admin")
        self.target = profile(role="student", student_id=9)
        self.classroom = Classroom(id=7, organization_id=1, grade=7, name="7А", status="active")
        self.enrollment = ClassroomStudent(id=20, classroom_id=7, student_id=9)
        self.db = MagicMock()
        self.db.scalar = AsyncMock(return_value=self.target)
        rows = MagicMock()
        rows.all.return_value = [self.enrollment]
        self.db.scalars = AsyncMock(return_value=rows)
        self.db.commit = AsyncMock()
        self.db.flush = AsyncMock()

    async def test_removal_closes_enrollment_preserves_history_and_does_not_touch_duplicate(self):
        other_profile = profile(role="student", student_id=10)
        other_profile.id = 5
        other_enrollment = ClassroomStudent(id=21, classroom_id=8, student_id=10)
        with (
            patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)),
            patch("services.student_lifecycle.forget_principal") as forget,
        ):
            await remove_student(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        self.assertEqual(self.target.status, "archived")
        self.assertIsInstance(self.enrollment.left_at, datetime)
        self.assertEqual(other_profile.status, "active")
        self.assertIsNone(other_enrollment.left_at)
        event = self.db.add.call_args.args[0]
        self.assertIsInstance(event, AccountEvent)
        self.assertEqual(event.event_type, "account_blocked")
        self.assertEqual(event.metadata_json, {"action": "student_removed", "classroom_id": 7, "previous_status": "active"})
        self.assert_event_type_allowed_by_existing_schema(event.event_type)
        self.db.delete.assert_not_called()
        self.db.commit.assert_awaited_once()
        forget.assert_called_once_with(self.target.auth_user_id)
        statement = self.db.scalar.await_args.args[0]
        self.assertEqual(statement.compile().params["organization_id_1"], self.user.organization_id)
        self.assertEqual(statement.compile().params["role_1"], "student")
        enrollment_statement = self.db.scalars.await_args.args[0]
        self.assertEqual(enrollment_statement.compile().params["student_id_1"], 9)

    async def test_teacher_cannot_remove_or_restore(self):
        for operation, kwargs in ((remove_student, {"classroom_id": 7}), (restore_student, {"target_classroom_id": 8})):
            with self.assertRaises(AuthServiceError) as error:
                await operation(principal(role="teacher"), student_profile_id=4, db=self.db, **kwargs)
            self.assertEqual(error.exception.status_code, 403)
        self.db.scalar.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    async def test_foreign_or_nonstudent_profile_is_not_found(self):
        self.db.scalar.return_value = None
        with patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)):
            with self.assertRaises(AuthServiceError) as error:
                await remove_student(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        self.assertEqual(error.exception.status_code, 404)
        self.db.commit.assert_not_awaited()

    async def test_stale_class_selection_cannot_remove_a_transferred_student(self):
        self.enrollment.classroom_id = 8
        with patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)):
            with self.assertRaises(AuthServiceError) as error:
                await remove_student(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.target.status, "active")
        self.assertIsNone(self.enrollment.left_at)
        self.db.commit.assert_not_awaited()

    async def test_removal_retry_is_idempotent(self):
        self.target.status = "archived"
        with patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)):
            await remove_student(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        self.db.scalars.assert_not_awaited()
        self.db.add.assert_not_called()

    async def test_failed_commit_does_not_report_success_or_invalidate_identity(self):
        self.db.commit.side_effect = RuntimeError("Database unavailable")
        with (
            patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)),
            patch("services.student_lifecycle.forget_principal") as forget,
        ):
            with self.assertRaises(RuntimeError):
                await remove_student(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        forget.assert_not_called()

    async def test_restore_preserves_credentials_and_recalculates_grade_access(self):
        for previous_status in ("active", "blocked", "invited"):
            with self.subTest(previous_status=previous_status):
                self.target.status = "archived"
                student = Student(id=9, name="Student", grade=7)
                self.db.get = AsyncMock(return_value=student)
                self.db.scalar = AsyncMock(side_effect=[self.target, None, AccountEvent(metadata_json={"action": "student_removed", "previous_status": previous_status})])
                target_class = Classroom(id=8, organization_id=1, grade=8, name="8А", status="active")
                with (
                    patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=target_class)),
                    patch("services.student_lifecycle.refresh_student_access", new=AsyncMock()) as refresh,
                    patch("services.student_lifecycle.forget_principal") as forget,
                ):
                    await restore_student(self.user, student_profile_id=4, target_classroom_id=8, db=self.db)
                self.assertEqual(student.grade, 8)
                self.assertEqual(self.target.status, previous_status)
                self.assertEqual(self.target.login_name, "target.user")
                self.assertFalse(self.target.must_change_password)
                refresh.assert_awaited_once_with(9, self.db)
                forget.assert_called_once_with(self.target.auth_user_id)
                created_enrollment = self.db.add.call_args_list[-2].args[0]
                self.assertEqual((created_enrollment.student_id, created_enrollment.classroom_id), (9, 8))
                restore_event = self.db.add.call_args_list[-1].args[0]
                self.assertEqual(restore_event.event_type, "account_restored")
                self.assertEqual(restore_event.metadata_json["action"], "student_restored")
                self.assert_event_type_allowed_by_existing_schema(restore_event.event_type)
                # Ordinary account blocks must not supply a removal's previous status.
                statement = self.db.scalar.await_args_list[-1].args[0]
                compiled = statement.compile(dialect=postgresql.dialect())
                self.assertIn("->>", str(compiled))
                self.assertIn("action", compiled.params.values())
                self.assertIn("student_removed", compiled.params.values())
                self.assertIn("account_blocked", compiled.params.values())

    def assert_event_type_allowed_by_existing_schema(self, event_type):
        migrations = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
        for migration in ("20260923100000_classroom_assignment_audit.sql", "20260930083857_teacher_subject_assignment_audit.sql"):
            text = (migrations / migration).read_text()
            constraint = re.search(r"event_type\s+IN\s*\((.*?)\)", text, re.IGNORECASE | re.DOTALL)
            self.assertIsNotNone(constraint)
            allowed = re.findall(r"'([^']+)'", constraint.group(1))
            self.assertIn(event_type, allowed)

    async def test_restore_rejects_an_archived_classroom(self):
        self.classroom.status = "archived"
        with patch("services.student_lifecycle.require_classroom_management", new=AsyncMock(return_value=self.classroom)):
            with self.assertRaises(AuthServiceError) as error:
                await restore_student(self.user, student_profile_id=4, target_classroom_id=7, db=self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.db.scalar.assert_not_awaited()

    async def test_archived_roster_is_organization_scoped_without_secrets(self):
        self.target.status = "archived"
        student = Student(id=9, name="Student", grade=7)
        rows = MagicMock()
        rows.all.return_value = [(student, self.target)]
        self.db.execute = AsyncMock(return_value=rows)
        result = await list_removed_students(self.user, self.db)
        self.assertEqual(result[0]["status"], "archived")
        self.assertNotIn("temporary_password", result[0])
        params = self.db.execute.await_args.args[0].compile().params
        self.assertEqual(params["organization_id_1"], self.user.organization_id)
        self.assertEqual(params["status_1"], "archived")

    async def test_generic_unblock_reset_and_transfer_cannot_bypass_explicit_restore(self):
        self.target.status = "archived"
        self.db.get = AsyncMock(return_value=self.target)
        with (
            patch("services.accounts.admin_update_auth_user", new=AsyncMock()) as auth_update,
            patch("services.accounts.require_classroom_management", new=AsyncMock(return_value=self.classroom)),
        ):
            operations = (
                (set_account_blocked, {"target_profile_id": 4, "blocked": False}),
                (reset_temporary_password, {"target_profile_id": 4}),
                (transfer_student, {"student_profile_id": 4, "target_classroom_id": 7}),
            )
            for operation, kwargs in operations:
                with self.assertRaises(AuthServiceError) as error:
                    await operation(self.user, db=self.db, **kwargs)
                self.assertEqual(error.exception.status_code, 409)
            auth_update.assert_not_awaited()
        self.assertEqual(self.target.status, "archived")
