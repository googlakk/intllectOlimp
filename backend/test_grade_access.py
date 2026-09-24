import asyncio
import unittest

from models import Section, Student, Subject, Topic
from services.grade_access import GradeAccessError, require_topic_access


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, *, student_grade: int, subject_grade: int):
        self.student = Student(id=1, name="Ученик", grade=student_grade)
        self.subject = Subject(
            id=2,
            name="Математика",
            grade=subject_grade,
            hours_per_week=4,
            hours_per_year=136,
            source_info=None,
            instruction_language="ru",
        )
        self.section = Section(id=3, subject_id=2, name="Алгебра", sort_order=1, total_hours=10)
        self.topic = Topic(id=4, section_id=3, name="Дроби", hours=1, sort_order=1)

    async def get(self, model, row_id):
        rows = {
            (Student, self.student.id): self.student,
            (Subject, self.subject.id): self.subject,
            (Section, self.section.id): self.section,
            (Topic, self.topic.id): self.topic,
        }
        return rows.get((model, row_id))


class GradeAccessTests(unittest.TestCase):
    def test_allows_topic_from_students_grade(self):
        db = FakeSession(student_grade=7, subject_grade=7)

        topic = run(require_topic_access(1, 4, db))

        self.assertEqual(topic.id, 4)

    def test_allows_younger_curriculum_for_older_student(self):
        db = FakeSession(student_grade=9, subject_grade=7)

        topic = run(require_topic_access(1, 4, db))

        self.assertEqual(topic.id, 4)

    def test_hides_older_curriculum_from_younger_student(self):
        db = FakeSession(student_grade=7, subject_grade=8)

        with self.assertRaises(GradeAccessError) as ctx:
            run(require_topic_access(1, 4, db))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Предмет недоступен для класса ученика")


if __name__ == "__main__":
    unittest.main()
