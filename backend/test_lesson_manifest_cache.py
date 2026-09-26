import unittest

from models import GeneratedLesson
from services.lessons import (
    cached_lesson_manifest,
    cached_student_manifest_state,
    clear_lesson_manifest_cache,
    clear_student_manifest_state_cache,
    clear_lesson_manifest_cache_for_version,
    get_student_lesson_manifest,
    remember_lesson_manifest,
    remember_student_manifest_state,
)


class FakeExecuteResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeManifestSession:
    def __init__(self):
        lesson = GeneratedLesson(
            id=10,
            topic_id=2,
            blocks=[{"component": "ShortExplanation", "content": {"text": "Cached"}}],
            lesson_metadata={"objectives": [], "quality_report": {}},
            status="published",
        )
        self.rows = [
            (lesson, 7, 7, "available", False, None, None),
            (7, "available", None),
        ]
        self.execute_calls = 0
        self.scalars_calls = 0

    async def execute(self, _statement):
        self.execute_calls += 1
        return FakeExecuteResult(self.rows.pop(0))

    async def scalars(self, _statement):
        self.scalars_calls += 1
        return FakeScalarResult([])

    async def get(self, _model, _id):
        return None


class FakeLockedManifestSession(FakeManifestSession):
    def __init__(self):
        lesson = GeneratedLesson(
            id=10,
            topic_id=2,
            blocks=[{"component": "ShortExplanation", "content": {"text": "Soft gate"}}],
            lesson_metadata={"objectives": [], "quality_report": {}},
            status="published",
        )
        self.rows = [
            # Закрытый урок не кэшируется: второй запрос снова идёт в базу и снова получает отказ.
            (lesson, 7, 7, "locked", True, None, None),
            (lesson, 7, 7, "locked", True, None, None),
        ]
        self.execute_calls = 0
        self.scalars_calls = 0


class FakeVersionLookupSession:
    def __init__(self, topic_id):
        self.topic_id = topic_id
        self.scalar_calls = 0

    async def scalar(self, _statement):
        self.scalar_calls += 1
        return self.topic_id


class LessonManifestCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        clear_lesson_manifest_cache()

    async def asyncTearDown(self):
        clear_lesson_manifest_cache()

    async def test_repeated_manifest_uses_cached_lesson_payload(self):
        db = FakeManifestSession()

        first = await get_student_lesson_manifest(topic_id=2, student_id=7, db=db)  # type: ignore[arg-type]
        second = await get_student_lesson_manifest(topic_id=2, student_id=7, db=db)  # type: ignore[arg-type]

        self.assertEqual(first["lesson"]["id"], 10)
        self.assertEqual(second["lesson"]["id"], 10)
        self.assertEqual(db.execute_calls, 1)
        self.assertEqual(db.scalars_calls, 0)
        self.assertEqual(second["lesson"]["blocks"][0]["content"]["text"], "Cached")

    async def test_locked_topic_is_not_served_even_from_cache(self):
        # Темы открываются строго по порядку: закрытую не отдаём и по прямой ссылке.
        from services.lessons import LessonServiceError

        db = FakeLockedManifestSession()
        for _ in range(2):
            with self.assertRaises(LessonServiceError) as ctx:
                await get_student_lesson_manifest(topic_id=2, student_id=7, db=db)  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.status_code, 403)

    async def test_student_manifest_state_cache_can_be_cleared_per_student_topic(self):
        remember_student_manifest_state(7, 2, {
            "student_grade": 7,
            "access_state": "available",
            "progress": {"status": "in_progress"},
        })
        self.assertIsNotNone(cached_student_manifest_state(7, 2))

        clear_student_manifest_state_cache(7, 2)

        self.assertIsNone(cached_student_manifest_state(7, 2))

    async def test_cache_can_be_cleared_from_active_version_id(self):
        remember_lesson_manifest(2, {"lesson": {"id": 10}, "subject_grade": 7, "has_graph": False})
        self.assertIsNotNone(cached_lesson_manifest(2))

        db = FakeVersionLookupSession(topic_id=2)
        await clear_lesson_manifest_cache_for_version(99, db)  # type: ignore[arg-type]

        self.assertEqual(db.scalar_calls, 1)
        self.assertIsNone(cached_lesson_manifest(2))


if __name__ == "__main__":
    unittest.main()
