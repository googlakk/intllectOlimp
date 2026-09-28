import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from services.auth import AuthServiceError
from services.educator_access import require_grade_management, require_subject_management
from services.teacher_assignments import teacher_subject_ids
from test_auth_dependencies import principal


class EducatorAccessTests(unittest.IsolatedAsyncioTestCase):
    def database(self, subject_ids, *, subject_id=12, grade=8):
        result = MagicMock()
        result.all.return_value = [(value,) for value in subject_ids]
        return SimpleNamespace(
            execute=AsyncMock(return_value=result),
            get=AsyncMock(return_value=SimpleNamespace(id=subject_id, grade=grade)),
        )

    async def test_admin_can_manage_every_grade_and_subject_without_assignments(self):
        db = self.database([])
        await require_grade_management(principal(role="admin"), 8, db)
        subject = await require_subject_management(principal(role="admin"), 12, db)
        self.assertEqual(subject.id, 12)
        db.execute.assert_not_awaited()

    async def test_teacher_can_manage_assigned_subject_without_classroom(self):
        db = self.database([12])
        subject = await require_subject_management(principal(role="teacher"), 12, db)
        self.assertEqual(subject.id, 12)
        query = str(db.execute.await_args.args[0])
        self.assertIn("teacher_subject_assignments.organization_id", query)
        self.assertNotIn("classroom", query)

    async def test_teacher_cannot_manage_other_subject_even_at_same_or_lower_grade(self):
        for grade in (8, 7):
            with self.subTest(grade=grade):
                db = self.database([11], grade=grade)
                with self.assertRaises(AuthServiceError) as denied:
                    await require_subject_management(principal(role="teacher"), 12, db)
                self.assertEqual(denied.exception.status_code, 404)

    async def test_teacher_without_assignments_gets_empty_scope_and_cannot_manage_subject(self):
        db = self.database([])
        self.assertEqual(await teacher_subject_ids(principal(role="teacher"), db), [])
        with self.assertRaises(AuthServiceError) as denied:
            await require_subject_management(principal(role="teacher"), 12, db)
        self.assertEqual(denied.exception.status_code, 404)

    async def test_teacher_cannot_create_curriculum_even_for_assigned_grade(self):
        db = self.database([12])
        with self.assertRaises(AuthServiceError) as denied:
            await require_grade_management(principal(role="teacher"), 8, db)
        self.assertEqual(denied.exception.status_code, 403)
        db.execute.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
