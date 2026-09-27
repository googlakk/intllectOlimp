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
        # Ученик вне классов учителя не находится запросом с проверкой доступа — дальше отчёт не читается.
        db = SimpleNamespace(scalar=AsyncMock(return_value=None), execute=AsyncMock())
        with self.assertRaises(ApplicationError) as denied:
            await get_student_learning_report(2, db, user=SimpleNamespace(role='teacher', teacher_id=5))
        self.assertEqual(denied.exception.status_code, 404)
        db.execute.assert_not_awaited()

    def test_multiple_students_cannot_exceed_one_hundred_percent(self):
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=6)['average_progress'], 100)
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=2)['average_progress'], 33.3)


class OverviewQueryCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_overview_is_a_single_query(self):
        from unittest.mock import AsyncMock, MagicMock
        from services.dashboard import get_dashboard_overview
        result = MagicMock()
        result.one.return_value = SimpleNamespace(students=2, subjects=1, topics=4, published=3, completed=4)
        db = SimpleNamespace(execute=AsyncMock(return_value=result), scalar=AsyncMock(), scalars=AsyncMock())
        overview = await get_dashboard_overview(db, user=SimpleNamespace(role="teacher", teacher_id=5))
        self.assertEqual(db.execute.await_count, 1)
        db.scalar.assert_not_awaited()
        db.scalars.assert_not_awaited()
        self.assertEqual(overview["average_progress"], 50.0)
