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
                "average_progress": 37.5,
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
