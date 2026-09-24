import unittest
from types import SimpleNamespace
from decimal import Decimal

from services.dashboard import build_dashboard_overview, serialize_student_summary


class DashboardOverviewTests(unittest.TestCase):
    def test_average_progress_is_percentage_of_completed_topics(self):
        self.assertEqual(
            build_dashboard_overview(
                students=12,
                subjects=3,
                topics=8,
                published_lessons=5,
                completed_lessons=3,
            ),
            {
                "students": 12,
                "subjects": 3,
                "topics": 8,
                "published_lessons": 5,
                "average_progress": 3.1,
            },
        )

    def test_average_progress_is_zero_without_topics(self):
        self.assertEqual(
            build_dashboard_overview(
                students=0,
                subjects=0,
                topics=0,
                published_lessons=0,
                completed_lessons=10,
            )["average_progress"],
            0,
        )


class StudentSummaryTests(unittest.TestCase):
    def test_serializes_database_row_shape(self):
        row = SimpleNamespace(
            id=7,
            name="Айдана",
            grade=8,
            completed_topics=4,
            average_score=Decimal("86.5"),
        )

        self.assertEqual(
            serialize_student_summary(row),
            {
                "id": 7,
                "name": "Айдана",
                "grade": 8,
                "completed_topics": 4,
                "average_score": 86.5,
            },
        )


if __name__ == "__main__":
    unittest.main()


class LearningReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_denies_students_outside_teacher_scope(self):
        from unittest.mock import AsyncMock, patch
        from services.dashboard import get_student_learning_report
        from errors import ApplicationError
        db = SimpleNamespace(get=AsyncMock())
        with patch('services.dashboard._visible_student_ids', AsyncMock(return_value=[1])):
            with self.assertRaises(ApplicationError):
                await get_student_learning_report(2, db, user=SimpleNamespace(role='teacher'))
        db.get.assert_not_awaited()

    def test_multiple_students_cannot_exceed_one_hundred_percent(self):
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=6)['average_progress'], 100)
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=2)['average_progress'], 33.3)
