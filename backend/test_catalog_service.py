import unittest

from models import Section, Subject, Topic
from services.catalog import serialize_model, serialize_subject


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
            },
        )


if __name__ == "__main__":
    unittest.main()
