import unittest

from models import Section, Subject, Topic
from services.catalog import (
    cached_subject_outline,
    clear_subject_outline_cache,
    clear_subject_outline_cache_for_topic,
    list_subject_outline,
    serialize_model,
    serialize_subject,
    serialize_topic,
)


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeOutlineSession:
    def __init__(self):
        self.section = Section(id=3, subject_id=1, name="Алгебра", sort_order=1, total_hours=12)
        self.topic = Topic(
            id=5,
            section_id=3,
            ktp_number="1.1",
            name="Линейные уравнения",
            hours=2,
            lesson_type="study",
            learning_objectives="Решать линейные уравнения.",
            skills=["вычисление"],
            resources="Учебник",
            sort_order=1,
        )
        self.scalar_calls = 0
        self.execute_calls = 0

    async def scalars(self, _statement):
        self.scalar_calls += 1
        return FakeScalarResult([self.section])

    async def execute(self, _statement):
        self.execute_calls += 1
        return FakeExecuteResult([(self.section, self.topic, 42, "published")])

    async def scalar(self, _statement):
        return self.section.subject_id


class CatalogSerializationTests(unittest.TestCase):
    def test_subject_serialization_adds_progress_placeholder(self):
        subject = Subject(
            id=1,
            name="Математика",
            grade=7,
            hours_per_week=1.5,
            hours_per_year=51,
            source_info="КТП",
            instruction_language="ru",
        )

        self.assertEqual(
            serialize_subject(subject),
            {
                "id": 1,
                "name": "Математика",
                "grade": 7,
                "hours_per_week": 1.5,
                "hours_per_year": 51,
                "source_info": "КТП",
                "instruction_language": "ru",
                "created_at": None,
                "progress": 0,
            },
        )

    def test_section_serialization_uses_declared_columns_only(self):
        section = Section(
            id=3,
            subject_id=1,
            name="Алгебра",
            sort_order=2,
            total_hours=12,
        )
        section.transient_value = "not api"

        self.assertEqual(
            serialize_model(section),
            {
                "id": 3,
                "subject_id": 1,
                "name": "Алгебра",
                "sort_order": 2,
                "total_hours": 12,
            },
        )

    def test_topic_serialization_preserves_optional_fields(self):
        topic = Topic(
            id=5,
            section_id=3,
            ktp_number=None,
            name="Линейные уравнения",
            hours=2,
            lesson_type="study",
            learning_objectives=None,
            skills=[],
            resources=None,
            sort_order=4,
        )

        self.assertEqual(
            serialize_model(topic),
            {
                "id": 5,
                "section_id": 3,
                "ktp_number": None,
                "name": "Линейные уравнения",
                "hours": 2,
                "lesson_type": "study",
                "learning_objectives": None,
                "skills": [],
                "resources": None,
                "sort_order": 4,
                "covered_topic_ids": None,
                "source_assessment_topic_id": None,
                "archived_at": None,
                "review_required": None,
            },
        )

    def test_topic_list_summary_excludes_lesson_payload(self):
        topic = Topic(
            id=5,
            section_id=3,
            ktp_number=None,
            name="Линейные уравнения",
            hours=2,
            lesson_type="study",
            learning_objectives=None,
            skills=[],
            resources=None,
            sort_order=4,
        )

        payload = serialize_topic(topic, lesson_id=42, lesson_status="published")

        self.assertEqual(payload["lesson_id"], 42)
        self.assertEqual(payload["lesson_status"], "published")
        self.assertNotIn("blocks", payload)
        self.assertNotIn("lesson_document", payload)
        self.assertNotIn("lesson_metadata", payload)


class CatalogOutlineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        clear_subject_outline_cache()

    async def asyncTearDown(self):
        clear_subject_outline_cache()

    async def test_subject_outline_returns_compact_lesson_status_only(self):
        db = FakeOutlineSession()

        outline = await list_subject_outline(1, db)  # type: ignore[arg-type]

        self.assertEqual(db.scalar_calls, 0)
        self.assertEqual(db.execute_calls, 1)
        topic = outline[0]["topics"][0]
        self.assertEqual(topic["lesson_id"], 42)
        self.assertEqual(topic["lesson_status"], "published")
        self.assertNotIn("blocks", topic)
        self.assertNotIn("lesson_document", topic)
        self.assertNotIn("lesson_metadata", topic)

    async def test_subject_outline_uses_short_lived_cache(self):
        db = FakeOutlineSession()

        first = await list_subject_outline(1, db)  # type: ignore[arg-type]
        second = await list_subject_outline(1, db)  # type: ignore[arg-type]

        self.assertEqual(first, second)
        self.assertEqual(db.scalar_calls, 0)
        self.assertEqual(db.execute_calls, 1)

    async def test_subject_outline_cache_can_be_cleared_from_topic(self):
        db = FakeOutlineSession()
        await list_subject_outline(1, db)  # type: ignore[arg-type]
        self.assertIsNotNone(cached_subject_outline(1))

        await clear_subject_outline_cache_for_topic(5, db)  # type: ignore[arg-type]

        self.assertIsNone(cached_subject_outline(1))


if __name__ == "__main__":
    unittest.main()
