import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from datetime import datetime

from models import Classroom, ClassroomStudent, Profile, Student
from services.accounts import set_account_blocked, transfer_student
from services.auth import AuthServiceError
from test_auth_dependencies import principal


def profile(*, role: str, student_id: int | None = None) -> Profile:
    return Profile(
        id=4,
        auth_user_id=UUID("00000000-0000-0000-0000-000000000004"),
        organization_id=1,
        role=role,
        login_name="target.user",
        display_name="Target User",
        status="active",
        must_change_password=False,
        student_id=student_id,
    )


class AccountServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_can_block_only_visible_student(self):
        target = profile(role="student", student_id=9)
        db = MagicMock()
        db.get = AsyncMock(return_value=target)
        db.commit = AsyncMock()
        with (
            patch("services.accounts.require_student_visibility", new=AsyncMock()) as visibility,
            patch("services.accounts.admin_update_auth_user", new=AsyncMock()) as update_auth,
        ):
            await set_account_blocked(principal(role="teacher"), target_profile_id=4, blocked=True, db=db)
        visibility.assert_awaited_once_with(principal(role="teacher"), 9, db)
        update_auth.assert_awaited_once_with(str(target.auth_user_id), {"ban_duration": "876000h"})
        self.assertEqual(target.status, "blocked")
        db.commit.assert_awaited_once()

    async def test_teacher_cannot_block_teacher_account(self):
        db = MagicMock()
        db.get = AsyncMock(return_value=profile(role="teacher"))
        with self.assertRaises(AuthServiceError) as error:
            await set_account_blocked(principal(role="teacher"), target_profile_id=4, blocked=True, db=db)
        self.assertEqual(error.exception.status_code, 403)

    async def test_transfer_preserves_history_and_recalculates_current_access(self):
        target = Classroom(id=8, organization_id=1, name="8А", grade=8, academic_year="2026-2027")
        target_profile = profile(role="student", student_id=9)
        current = ClassroomStudent(id=20, classroom_id=7, student_id=9)
        student = Student(id=9, name="Student", grade=7)
        db = MagicMock()
        db.get = AsyncMock(side_effect=lambda model, row_id: {
            (Profile, 4): target_profile,
            (Student, 9): student,
        }.get((model, row_id)))
        db.scalar = AsyncMock(return_value=current)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        with (
            patch("services.accounts.require_classroom_management", new=AsyncMock(return_value=target)) as access,
            patch("services.accounts.refresh_student_access", new=AsyncMock(return_value=[])) as refresh,
        ):
            await transfer_student(
                principal(role="admin"),
                student_profile_id=4,
                target_classroom_id=8,
                db=db,
            )

        self.assertIsInstance(current.left_at, datetime)
        self.assertEqual(student.grade, 8)
        access.assert_any_await(principal(role="admin"), 8, db)
        access.assert_any_await(principal(role="admin"), 7, db)
        db.flush.assert_awaited_once()
        refresh.assert_awaited_once_with(9, db)
        db.commit.assert_awaited_once()

    async def test_transfer_to_current_class_is_rejected(self):
        target = Classroom(id=7, organization_id=1, name="7А", grade=7, academic_year="2026-2027")
        target_profile = profile(role="student", student_id=9)
        current = ClassroomStudent(id=20, classroom_id=7, student_id=9)
        db = MagicMock()
        db.get = AsyncMock(return_value=target_profile)
        db.scalar = AsyncMock(return_value=current)

        with patch("services.accounts.require_classroom_management", new=AsyncMock(return_value=target)):
            with self.assertRaises(AuthServiceError) as error:
                await transfer_student(
                    principal(role="admin"),
                    student_profile_id=4,
                    target_classroom_id=7,
                    db=db,
                )

        self.assertEqual(error.exception.status_code, 409)
        self.assertIsNone(current.left_at)


if __name__ == "__main__":
    unittest.main()
