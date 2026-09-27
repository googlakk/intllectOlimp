import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services.curriculum_graph import (
    CurriculumGraphError,
    canonical_skill_key,
    cached_curriculum_map,
    clear_curriculum_map_cache,
    enrich_ktp_draft,
    infer_topic_contract,
    mastery_label,
    mastery_score_from_progress,
    progression_access_from_progress,
    get_student_curriculum_map,
    require_curriculum_topic_access,
    supports_cross_subject_transfer,
    subject_profile,
)


class CurriculumContractTests(unittest.TestCase):
    def test_missing_objective_is_recovered_for_subject_and_grade(self):
        contract = infer_topic_contract(
            subject_name="Математика",
            grade=7,
            topic_name="Линейные уравнения",
            learning_objectives="",
        )

        self.assertEqual(contract["objective_source"], "inferred")
        self.assertIn("Линейные уравнения", contract["learning_objectives"])
        self.assertIn("7 класса", contract["learning_objectives"])
        self.assertNotIn("Логическое рассуждение", contract["skills"])
        self.assertTrue(all(not item.startswith("Освоение темы:") for item in contract["skills"]))

    def test_roots_have_concrete_measurable_skills(self):
        contract = infer_topic_contract(subject_name="Математика", grade=7, topic_name="Квадраты и квадратные корни")
        self.assertIn("Вычислять квадраты чисел", contract["skills"])
        self.assertIn("Находить квадратные корни из полных квадратов", contract["skills"])

    def test_supplied_objective_is_preserved(self):
        contract = infer_topic_contract(
            subject_name="Литература",
            grade=8,
            topic_name="Образ героя",
            learning_objectives="Сопоставлять поступки героев.",
            skills=["Сравнение"],
        )

        self.assertEqual(contract["objective_source"], "ktp")
        self.assertEqual(contract["learning_objectives"], "Сопоставлять поступки героев.")
        self.assertIn("Сравнение", contract["skills"])
        self.assertIn("Сопоставлять поступки героев.", contract["skills"])

    def test_draft_marks_inferred_objectives_for_teacher_review(self):
        draft = {
            "subject_name": "Биология",
            "grade": 9,
            "sections": [{"name": "Клетка", "topics": [{"name": "Деление клетки", "learning_objectives": "", "skills": []}]}],
        }

        result = enrich_ktp_draft(draft)

        self.assertEqual(result["inferred_objectives_count"], 1)
        self.assertEqual(result["sections"][0]["topics"][0]["objective_source"], "inferred")
        self.assertTrue(result["warnings"])

    def test_transferable_skill_has_same_key_across_subjects(self):
        self.assertEqual(
            canonical_skill_key("transferable", "Анализ причин и следствий"),
            canonical_skill_key("transferable", "анализ причин и следствий"),
        )
        self.assertEqual(subject_profile("Физика").transferable_skill, subject_profile("Химия").transferable_skill)

    def test_cross_domain_taxonomy_is_subject_agnostic(self):
        math = infer_topic_contract(
            subject_name="Математика",
            grade=7,
            topic_name="Графики функций",
        )
        literature = infer_topic_contract(
            subject_name="Литература",
            grade=8,
            topic_name="Сюжет и композиция произведения",
        )

        self.assertTrue(math["skills"])
        self.assertNotEqual(math["skills"], literature["skills"])

    def test_cross_subject_transfer_requires_compatible_subject_families(self):
        self.assertTrue(
            supports_cross_subject_transfer(
                "Интерпретация данных и источников", "Математика", "География"
            )
        )
        self.assertTrue(
            supports_cross_subject_transfer(
                "Причинно-следственное объяснение", "Литература", "История"
            )
        )
        self.assertFalse(
            supports_cross_subject_transfer(
                "Анализ структуры и взаимосвязей", "Математика", "Литература"
            )
        )
        self.assertFalse(
            supports_cross_subject_transfer(
                "Самостоятельное рассуждение", "Математика", "Физика"
            )
        )


class MasteryProjectionTests(unittest.TestCase):
    def test_mastered_completion_crosses_gate_threshold(self):
        score = mastery_score_from_progress(status="completed", mastery_status="mastered", score=92)
        self.assertEqual(score, 0.92)
        self.assertEqual(mastery_label(score), "mastered")

    def test_needs_practice_stays_below_mastery_gate_threshold(self):
        score = mastery_score_from_progress(status="completed", mastery_status="needs_practice", score=90)
        self.assertLess(score, 0.8)
        self.assertEqual(mastery_label(score), "developing")


class ProgressionAccessTests(unittest.TestCase):
    def test_completed_needs_practice_soft_unlocks_next_lesson(self):
        access = progression_access_from_progress(status="completed", mastery_status="needs_practice")

        self.assertIsNotNone(access)
        assert access is not None
        readiness, reason = access
        self.assertGreater(readiness, 0)
        self.assertLess(readiness, 1.0)
        self.assertIn("Можно продолжить", reason)

    def test_in_progress_does_not_unlock_next_lesson(self):
        access = progression_access_from_progress(status="in_progress", mastery_status=None)

        self.assertIsNone(access)


class FakeAccessSession:
    def __init__(self, scalar_values):
        self.scalar_values = list(scalar_values)
        self.commits = 0

    async def scalar(self, _statement):
        if not self.scalar_values:
            return None
        return self.scalar_values.pop(0)

    async def commit(self):
        self.commits += 1


class FakeScalarRows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeExecuteRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeCurriculumMapSession:
    def __init__(self, *, materialized_access):
        topic = SimpleNamespace(id=2, name="Тема", hours=1)
        section = SimpleNamespace(id=3, name="Раздел", sort_order=1)
        subject = SimpleNamespace(id=4, name="Математика", grade=7)
        access = SimpleNamespace(
            state="available",
            readiness_score=1.0,
            reason="Доступно.",
            unlocked_by_topic_id=None,
        )
        progress = SimpleNamespace(mastery_status="in_progress", attempts=1)
        self.materialized_access = materialized_access
        self.rows = [(
            topic,
            section,
            subject,
            access if materialized_access is not None else None,
            "published",
            progress,
        )]
        self.flushes = 0
        self.commits = 0

    async def get(self, _model, _id):
        return SimpleNamespace(id=7, grade=7)

    async def scalar(self, _statement):
        return self.materialized_access

    async def execute(self, _statement):
        return FakeExecuteRows(self.rows)

    async def scalars(self, _statement):
        return FakeScalarRows([])

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


class CurriculumAccessGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_available_materialized_access_skips_graph_refresh(self):
        db = FakeAccessSession([1, SimpleNamespace(state="available")])

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()) as refresh:
            await require_curriculum_topic_access(7, 2, db)  # type: ignore[arg-type]

        refresh.assert_not_awaited()
        self.assertEqual(db.commits, 0)

    async def test_locked_access_rejects_progress_after_fresh_recount(self):
        # Темы открываются строго по порядку: «закрыто» перепроверяется пересчётом, потом отказ.
        db = FakeAccessSession([1, SimpleNamespace(state="locked"), None, "locked"])

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()) as refresh:
            with self.assertRaises(CurriculumGraphError) as ctx:
                await require_curriculum_topic_access(7, 2, db)  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 403)
        refresh.assert_awaited_once()

    async def test_stale_locked_access_opens_after_recount(self):
        db = FakeAccessSession([1, SimpleNamespace(state="locked"), None, "available"])

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()):
            await require_curriculum_topic_access(7, 2, db)  # type: ignore[arg-type]

    async def test_started_topic_is_never_rejected(self):
        db = FakeAccessSession([1, SimpleNamespace(state="locked"), 55])

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()) as refresh:
            await require_curriculum_topic_access(7, 2, db)  # type: ignore[arg-type]

        refresh.assert_not_awaited()
        self.assertEqual(db.commits, 0)

    async def test_missing_materialized_access_refreshes_without_hard_rejecting(self):
        db = FakeAccessSession([1, None])

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()) as refresh:
            await require_curriculum_topic_access(7, 2, db)  # type: ignore[arg-type]

        refresh.assert_awaited_once()
        self.assertEqual(db.commits, 1)


class CurriculumMapFastPathTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        clear_curriculum_map_cache()

    async def asyncTearDown(self):
        clear_curriculum_map_cache()

    async def test_materialized_access_skips_refresh_by_default(self):
        db = FakeCurriculumMapSession(materialized_access=1)

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock()) as refresh:
            result = await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]

        refresh.assert_not_awaited()
        self.assertEqual(db.flushes, 0)
        self.assertEqual(result["topics"][0]["state"], "available")

    async def test_missing_materialized_access_refreshes_once(self):
        db = FakeCurriculumMapSession(materialized_access=None)

        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock(return_value=[])) as refresh:
            result = await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]

        refresh.assert_awaited_once()
        self.assertEqual(db.flushes, 1)
        self.assertEqual(result["topics"][0]["state"], "locked")
        self.assertIn("закрыта", result["topics"][0]["reason"])

    async def test_curriculum_map_uses_short_lived_cache(self):
        db = FakeCurriculumMapSession(materialized_access=1)

        first = await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]
        second = await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]

        self.assertEqual(first, second)
        self.assertEqual(db.commits, 1)
        self.assertIsNotNone(cached_curriculum_map(7, 4))

    async def test_curriculum_map_cache_can_be_cleared_by_student(self):
        db = FakeCurriculumMapSession(materialized_access=1)
        await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]
        self.assertIsNotNone(cached_curriculum_map(7, 4))

        clear_curriculum_map_cache(7)

        self.assertIsNone(cached_curriculum_map(7, 4))


if __name__ == "__main__":
    unittest.main()


class FakeGraphSession:
    def __init__(self, topics, authored=()):
        from models import Subject, Section
        self.subject = Subject(id=1, name='Математика', grade=7)
        self.section = Section(id=1, subject_id=1, name='Числа')
        self.topics = topics
        self.authored = authored
        self.statements = []
        self.inserts = {}

    async def get(self, _model, _identifier):
        return self.subject

    async def execute(self, statement):
        from sqlalchemy.sql.dml import Insert, Delete
        self.statements.append(statement)
        if isinstance(statement, Delete):
            return FakeExecuteRows([])
        if isinstance(statement, Insert):
            params = statement.compile().params
            count = len([key for key in params if key.startswith(('canonical_key_m', 'topic_id_m', 'from_topic_id_m'))])
            values = [{key.rsplit('_m', 1)[0]: value for key, value in params.items() if key.endswith(f'_m{index}')} for index in range(count)]
            self.inserts[statement.table.name] = values
            if statement.table.name == 'skills':
                return FakeExecuteRows([(row['canonical_key'], index + 10) for index, row in enumerate(values)])
            return FakeExecuteRows([])
        names = [item['name'] for item in statement.column_descriptions]
        if names == ['Topic', 'Section']:
            return FakeExecuteRows([(topic, self.section) for topic in self.topics])
        if names == ['TopicSkill', 'Skill']:
            return FakeExecuteRows(self.authored)
        return FakeExecuteRows([])

    async def flush(self):
        pass


class GraphRebuildTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_shares_source_skill_and_maps_its_own_objective(self):
        from models import Topic
        from objectives import decompose_objectives
        from services.curriculum_graph import rebuild_subject_graph
        study = Topic(id=1, section_id=1, name='Корни', lesson_type='study', sort_order=1,
                      learning_objectives='Вычислять квадратные корни', skills=[], covered_topic_ids=[])
        review = Topic(id=2, section_id=1, name='Повторение', lesson_type='review', sort_order=2,
                       learning_objectives='', skills=[], covered_topic_ids=[1])
        empty = Topic(id=3, section_id=1, name='Разбор', lesson_type='reflection', sort_order=3,
                      learning_objectives='', skills=[], covered_topic_ids=[], source_assessment_topic_id=2)
        db = FakeGraphSession([study, review, empty])
        await rebuild_subject_graph(1, db)
        outcomes = [row for row in db.inserts['topic_skills'] if row['role'] == 'outcome']
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0]['skill_id'], outcomes[1]['skill_id'])
        self.assertEqual(outcomes[1]['objective_id'], decompose_objectives(review.learning_objectives)[0]['id'])
        self.assertEqual(empty.covered_topic_ids, [])
        self.assertEqual(empty.skills, [])
        self.assertTrue(empty.review_required)
        cross_select = next(stmt for stmt in db.statements if len(getattr(stmt, 'column_descriptions', [])) == 5)
        self.assertIn('topics.archived_at IS NULL', str(cross_select))

    async def test_authored_links_are_preserved_on_conflict_and_shared(self):
        from models import Topic, TopicSkill, Skill
        from services.curriculum_graph import rebuild_subject_graph
        study = Topic(id=1, section_id=1, name='Корни', lesson_type='study', sort_order=1,
                      learning_objectives='Вычислять квадратные корни', skills=[], covered_topic_ids=[])
        review = Topic(id=2, section_id=1, name='Контрольная', lesson_type='assessment', sort_order=2,
                       learning_objectives='', skills=[], covered_topic_ids=[1])
        authored_skill = Skill(id=9, canonical_key='teacher:special', name='Сравнивать корни', normalized_name='сравнивать корни',
                               subject_family='mathematics', grade_min=7, grade_max=9, metadata_json={})
        link = TopicSkill(topic_id=1, skill_id=9, role='outcome', source='teacher', objective_id='custom')
        db = FakeGraphSession([study, review], [(link, authored_skill)])
        await rebuild_subject_graph(1, db)
        self.assertIn('Сравнивать корни', review.skills)
        self.assertEqual(link.source, 'teacher')
        self.assertEqual(link.objective_id, 'custom')
        inserts = [str(stmt) for stmt in db.statements if getattr(getattr(stmt, 'table', None), 'name', None) in {'topic_skills', 'topic_edges'} and str(stmt).startswith('INSERT')]
        self.assertTrue(inserts)
        self.assertTrue(all('DO NOTHING' in sql for sql in inserts))

    def test_generic_skill_cannot_be_certified_even_if_objective_text_matches(self):
        from services.curriculum_graph import objective_id_for_skill
        self.assertIsNone(objective_id_for_skill('Логическое мышление', 'Логическое мышление'))
        self.assertIsNone(objective_id_for_skill('Сравнение', 'Сравнение'))
        self.assertIsNotNone(objective_id_for_skill('Сравнивать дроби', 'Сравнивать дроби'))

    def test_assessment_without_scope_does_not_invent_administrative_objectives(self):
        contract = infer_topic_contract(subject_name='Физика', grade=7, topic_name='Контрольная №1', lesson_type='assessment')
        self.assertEqual(contract['learning_objectives'], '')
        self.assertEqual(contract['skills'], [])


class AuthoredGoalTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_keeps_authored_goal_even_with_old_template_prefix(self):
        from models import Topic
        from services.curriculum_graph import rebuild_subject_graph
        goal = 'Объяснять математическую идею отрицательного числа на примере температуры'
        topic = Topic(id=1, section_id=1, name='Повторение', lesson_type='review', sort_order=1,
                      learning_objectives=goal, skills=['Сравнение'], covered_topic_ids=[])
        db = FakeGraphSession([topic])
        await rebuild_subject_graph(1, db)
        self.assertEqual(topic.learning_objectives, goal)
        self.assertEqual(topic.skills, [])
        self.assertNotIn('topic_skills', db.inserts)


class AccessRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_student_access_is_locked_and_written_in_one_statement(self):
        from sqlalchemy.sql.dml import Insert
        from models import Section, Student, Subject, Topic
        from services.curriculum_graph import refresh_student_access

        subject = Subject(id=1, name='История', grade=8)
        section = Section(id=1, subject_id=1, name='Новое время', sort_order=1)
        topics = [Topic(id=index, section_id=1, name=f'Тема {index}', sort_order=index) for index in range(1, 41)]

        class Session:
            def __init__(self):
                self.statements = []

            async def get(self, _model, _identifier):
                return Student(id=9, grade=8)

            async def execute(self, statement, params=None):
                self.statements.append((statement, params))
                names = [item['name'] for item in getattr(statement, 'column_descriptions', [])]
                if names == ['Topic', 'Section', 'Subject']:
                    return FakeExecuteRows([(topic, section, subject) for topic in topics])
                return FakeExecuteRows([])

            async def scalars(self, _statement):
                return FakeExecuteRows([])

        session = Session()
        await refresh_student_access(9, session)
        self.assertIn('pg_advisory_xact_lock', str(session.statements[0][0]))
        access = [statement for statement, _ in session.statements
                  if isinstance(statement, Insert) and statement.table.name == 'student_topic_access']
        self.assertEqual(len(access), 1)
        self.assertEqual(len(access[0].compile().params) // 8, 40)
        # Граф не построен — темы не закрываются навсегда.
        states = {value for key, value in access[0].compile().params.items() if key.startswith('state_m')}
        self.assertEqual(states, {'available'})


class StaleLockTests(unittest.TestCase):
    def test_locked_topic_after_completed_one_is_stale(self):
        from services.curriculum_graph import _has_stale_lock

        subject = SimpleNamespace(id=4)
        done = SimpleNamespace(status="completed")
        locked = SimpleNamespace(state="locked")
        available = SimpleNamespace(state="available")
        self.assertTrue(_has_stale_lock([(1, 1, subject, available, "published", done), (2, 1, subject, locked, "published", None)]))
        self.assertFalse(_has_stale_lock([(1, 1, subject, available, "published", None), (2, 1, subject, locked, "published", None)]))


class ConfirmedLockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from services import curriculum_graph
        clear_curriculum_map_cache()
        curriculum_graph._confirmed_locks.clear()

    async def test_lock_that_survives_recount_is_not_recounted_again(self):
        from services import curriculum_graph
        db = FakeCurriculumMapSession(materialized_access=1)
        subject = db.rows[0][2]
        done = SimpleNamespace(status="completed", mastery_status="mastered", attempts=1)
        locked = SimpleNamespace(state="locked", readiness_score=0.0, reason="Закрыто.", unlocked_by_topic_id=None)
        first_topic = SimpleNamespace(id=1, name="Первая", hours=1)
        second_topic = SimpleNamespace(id=2, name="Вторая", hours=1)
        db.rows = [
            (first_topic, db.rows[0][1], subject, SimpleNamespace(state="mastered", readiness_score=1.0, reason="", unlocked_by_topic_id=None), "published", done),
            (second_topic, db.rows[0][1], subject, locked, "published", None),
        ]
        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock(return_value=[])) as refresh:
            await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]
            clear_curriculum_map_cache()
            await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]
        refresh.assert_awaited_once()
        # Прогресс изменился — строки другие, пересчёт снова нужен.
        db.rows[1] = (second_topic, db.rows[1][1], subject, locked, "published", SimpleNamespace(status="in_progress", mastery_status=None, attempts=1))
        db.rows[0] = (first_topic, db.rows[0][1], subject, db.rows[0][3], "published", SimpleNamespace(status="completed", mastery_status="mastered", attempts=2))
        clear_curriculum_map_cache()
        curriculum_graph._confirmed_locks[(7, 4)] = ("другие строки",)
        with patch("services.curriculum_graph.refresh_student_access", new=AsyncMock(return_value=[])) as refresh:
            await get_student_curriculum_map(7, db, subject_id=4)  # type: ignore[arg-type]
        refresh.assert_awaited_once()
