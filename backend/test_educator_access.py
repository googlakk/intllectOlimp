import unittest
from unittest.mock import AsyncMock, MagicMock

from services.auth import AuthServiceError
from services.educator_access import require_grade_management, teacher_max_grade
from test_auth_dependencies import principal


class EducatorAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_has_unbounded_grade_scope(self):
        db = MagicMock()
        self.assertIsNone(await teacher_max_grade(principal(role="admin"), db))

    async def test_teacher_scope_comes_from_highest_assigned_class(self):
        db = MagicMock()
        db.scalar = AsyncMock(return_value=9)
        self.assertEqual(await teacher_max_grade(principal(role="teacher"), db), 9)
        await require_grade_management(principal(role="teacher"), 8, db)

    async def test_teacher_cannot_manage_higher_grade(self):
        db = MagicMock()
        db.scalar = AsyncMock(return_value=7)
        with self.assertRaises(AuthServiceError) as error:
            await require_grade_management(principal(role="teacher"), 8, db)
        self.assertEqual(error.exception.status_code, 404)

    async def test_teacher_without_class_cannot_manage_curriculum(self):
        db = MagicMock()
        db.scalar = AsyncMock(return_value=None)
        with self.assertRaises(AuthServiceError) as error:
            await teacher_max_grade(principal(role="teacher"), db)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
