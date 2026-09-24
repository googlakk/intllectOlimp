import unittest
from unittest.mock import AsyncMock, patch

from models import GeneratedLesson
from services.auth import AuthServiceError
from services.media_access import require_lesson_version_media_access
from test_auth_dependencies import principal


class MediaAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_media_access_uses_assigned_grade_scope(self):
        db = AsyncMock()
        with patch(
            "services.media_access.require_lesson_version_management",
            new=AsyncMock(),
        ) as management:
            await require_lesson_version_media_access(principal(role="teacher"), 7, db)
        management.assert_awaited_once_with(principal(role="teacher"), 7, db)

    async def test_student_can_only_read_active_lesson_version(self):
        lesson = GeneratedLesson(id=3, topic_id=9, status="published", active_version_id=7)
        db = AsyncMock()
        db.scalar.return_value = lesson
        with patch("services.media_access.get_lesson_by_topic", new=AsyncMock(return_value=lesson)) as check_lesson:
            await require_lesson_version_media_access(principal(role="student"), 7, db)
        check_lesson.assert_awaited_once_with(9, "student", db, student_id=1)

    async def test_student_cannot_read_stale_lesson_version(self):
        lesson = GeneratedLesson(id=3, topic_id=9, status="published", active_version_id=8)
        db = AsyncMock()
        db.scalar.return_value = lesson
        with patch("services.media_access.get_lesson_by_topic", new=AsyncMock(return_value=lesson)):
            with self.assertRaises(AuthServiceError) as error:
                await require_lesson_version_media_access(principal(role="student"), 7, db)
        self.assertEqual(error.exception.status_code, 404)

    async def test_student_can_read_pinned_version_when_teacher_edits(self):
        lesson = GeneratedLesson(id=3, topic_id=9, status="published", active_version_id=9, published_version_id=8)
        lesson._served_version_id = 7
        db = AsyncMock()
        db.scalar.return_value = lesson
        with patch("services.media_access.get_lesson_by_topic", new=AsyncMock(return_value=lesson)):
            await require_lesson_version_media_access(principal(role="student"), 7, db)
            with self.assertRaises(AuthServiceError):
                await require_lesson_version_media_access(principal(role="student"), 9, db)


if __name__ == "__main__":
    unittest.main()
