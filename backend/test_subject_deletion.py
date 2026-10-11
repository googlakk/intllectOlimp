import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy.exc import IntegrityError

from models import Subject
from services.catalog import cached_subject_outline, remember_subject_outline
from services.subject_deletion import HISTORY_MESSAGE, SubjectDeletionError, delete_subject


def session(*, history=False, active_job=False, optional_tables=()):
    db = AsyncMock()
    db.scalar.side_effect = [Subject(id=4), history, active_job]
    results = []
    for values in ([11], [21], [31], [41], optional_tables, []):
        result = unittest.mock.Mock()
        result.all.return_value = values
        results.append(result)
    db.scalars.side_effect = results
    return db


class SubjectDeletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_program_returns_404_without_mutation(self):
        db = session()
        db.scalar.side_effect = [None]
        with self.assertRaises(SubjectDeletionError) as error:
            await delete_subject(4, db)
        self.assertEqual(error.exception.status_code, 404)
        db.execute.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_awaited_once()

    async def test_history_blocks_all_mutations(self):
        db = session(history=True, optional_tables=["tutor_turns", "lesson_feedback"])
        with self.assertRaises(SubjectDeletionError) as error:
            await delete_subject(4, db)
        self.assertEqual(error.exception.detail, HISTORY_MESSAGE)
        history_sql = str(db.scalar.call_args_list[1].args[0])
        for table in ("progress", "lesson_attempts", "student_skill_mastery", "student_topic_access", "warp_gate_events", "tutor_turns", "lesson_feedback"):
            self.assertIn(table, history_sql)
        db.execute.assert_not_called()
        db.commit.assert_not_called()

    async def test_active_generation_blocks_deletion(self):
        db = session(active_job=True)
        with self.assertRaises(SubjectDeletionError) as error:
            await delete_subject(4, db)
        self.assertEqual(error.exception.status_code, 409)
        db.execute.assert_not_called()

    async def test_delete_detaches_books_and_teacher_and_clears_cache_after_commit(self):
        db = session(optional_tables=["textbooks"])
        remember_subject_outline(4, [{"id": 11}])
        with patch("services.lessons.clear_lesson_manifest_cache") as manifest, patch("services.curriculum_graph.clear_curriculum_map_cache") as curriculum:
            result = await delete_subject(4, db)
        self.assertEqual(result, {"deleted": True})
        statements = [str(call.args[0]) for call in db.execute.call_args_list]
        self.assertTrue(statements[0].startswith("UPDATE teachers"))
        self.assertTrue(statements[1].startswith("UPDATE textbooks"))
        self.assertTrue(statements[2].startswith("DELETE FROM subjects"))
        db.commit.assert_awaited_once()
        db.rollback.assert_not_called()
        self.assertIsNone(cached_subject_outline(4))
        manifest.assert_called_once_with(21)
        curriculum.assert_called_once_with()
        for call in db.scalars.call_args_list[:4]:
            self.assertIn("FOR UPDATE", str(call.args[0]))

    async def test_foreign_key_conflict_rolls_back_and_keeps_cache(self):
        db = session()
        db.commit.side_effect = IntegrityError("delete", {}, Exception("FK"))
        remember_subject_outline(4, [{"id": 11}])
        with self.assertRaises(SubjectDeletionError) as error:
            await delete_subject(4, db)
        self.assertEqual(error.exception.status_code, 409)
        db.rollback.assert_awaited_once()
        self.assertIsNotNone(cached_subject_outline(4))

    async def test_endpoint_requires_admin(self):
        from routes.subjects import router
        route = next(route for route in router.routes if route.path == "/api/subjects/{subject_id}" and "DELETE" in route.methods)
        dependency = next(item for item in route.dependant.dependencies if item.name == "_user")
        from test_auth_dependencies import principal
        for role in ("teacher", "student"):
            with self.assertRaises(Exception) as error:
                await dependency.call(principal(role=role))
            self.assertEqual(error.exception.status_code, 403)
        self.assertEqual((await dependency.call(principal(role="admin"))).role, "admin")


if __name__ == "__main__":
    unittest.main()
