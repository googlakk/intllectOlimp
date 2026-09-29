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

    async def _report(self, user, subject_rows):
        from unittest.mock import AsyncMock, MagicMock
        from services.dashboard import get_student_learning_report
        assignments, skills, lessons = MagicMock(), MagicMock(), MagicMock()
        assignments.all.return_value = subject_rows
        skills.all.return_value = []
        progress = SimpleNamespace(status="completed", mastery_status="mastered", score=90.0, completed_at=None)
        topic = SimpleNamespace(id=31, name="Дроби", archived_at=None)
        subject = SimpleNamespace(id=12, name="Математика", grade=7)
        lessons.all.return_value = [(progress, topic, subject)]
        results = ([assignments] if user.role != "admin" else []) + [skills, lessons]
        db = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(name="Аня")), execute=AsyncMock(side_effect=results))
        report = await get_student_learning_report(2, db, user=user)
        queries = [str(call.args[0].compile(compile_kwargs={"literal_binds": True})) for call in db.execute.await_args_list]
        return report, queries

    async def test_teacher_report_lists_only_assigned_subjects(self):
        report, queries = await self._report(SimpleNamespace(role="teacher", teacher_id=5, organization_id=1), [(12,)])
        skills_query, lessons_query = queries[-2], queries[-1]
        self.assertIn("sections.subject_id IN (12)", skills_query)
        self.assertIn("subjects.id IN (12)", lessons_query)
        self.assertEqual(report["lessons"][0]["subject_name"], "Математика")
        self.assertEqual(report["lessons"][0]["subject_grade"], 7)

    async def test_admin_report_is_not_limited_by_subject(self):
        report, queries = await self._report(SimpleNamespace(role="admin"), [])
        self.assertEqual(len(queries), 2)
        self.assertNotIn("subjects.id IN", queries[1])
        self.assertNotIn("topic_skills", queries[0])
        self.assertEqual(report["lessons"][0]["subject_id"], 12)

    async def test_teacher_student_list_counts_only_own_subjects(self):
        from unittest.mock import AsyncMock, MagicMock
        from services.dashboard import get_dashboard_students
        assignments, rows = MagicMock(), MagicMock()
        assignments.all.return_value = [(12,)]
        rows.all.return_value = []
        db = SimpleNamespace(execute=AsyncMock(side_effect=[assignments, rows]))
        await get_dashboard_students(db, user=SimpleNamespace(role="teacher", teacher_id=5, organization_id=1))
        query = str(db.execute.await_args_list[1].args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("sections.subject_id IN (12)", query)
        # Условие в соединении, а не в WHERE: ученик без уроков по предмету остаётся в списке.
        progress_join = query[query.index("LEFT OUTER JOIN progress"):query.index("LEFT OUTER JOIN topics")]
        self.assertIn("sections.subject_id IN (12)", progress_join)

    def test_multiple_students_cannot_exceed_one_hundred_percent(self):
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=6)['average_progress'], 100)
        self.assertEqual(build_dashboard_overview(students=2, subjects=1, topics=3, published_lessons=3, completed_lessons=2)['average_progress'], 33.3)


class OverviewQueryCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_overview_uses_assignments_then_scoped_counters(self):
        from unittest.mock import AsyncMock, MagicMock
        from services.dashboard import get_dashboard_overview
        result = MagicMock()
        result.one.return_value = SimpleNamespace(students=2, subjects=1, topics=4, published=3, completed=4)
        assignments = MagicMock()
        assignments.all.return_value = [(12,)]
        db = SimpleNamespace(execute=AsyncMock(side_effect=[assignments, result]), scalar=AsyncMock(), scalars=AsyncMock())
        overview = await get_dashboard_overview(db, user=SimpleNamespace(role="teacher", teacher_id=5, organization_id=1))
        self.assertEqual(db.execute.await_count, 2)
        scope_query = str(db.execute.await_args_list[0].args[0])
        self.assertIn("teacher_subject_assignments.organization_id", scope_query)
        count_query = str(db.execute.await_args_list[1].args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertEqual(count_query.count("subjects.id IN (12)"), 4)
        self.assertNotIn("subjects.grade <=", count_query)
        db.scalar.assert_not_awaited()
        db.scalars.assert_not_awaited()
        self.assertEqual(overview["average_progress"], 50.0)
