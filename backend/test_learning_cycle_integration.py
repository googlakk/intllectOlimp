"""Opt-in real PostgreSQL learning-cycle coverage. Never connects to production.

LEARNING_CYCLE_TEST_DATABASE_URL must explicitly select localhost/learning_test.
The test creates missing tables and dedicated fixture rows, without deleting data.
"""
import os
import unittest
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import Base
from models import GeneratedLesson, LessonAttempt, LessonVersion, Progress, Section, Student, Subject, Teacher, Topic
from objectives import decompose_objectives
from routes.progress import ProgressInput
from services.auth import AuthPrincipal
from services.lessons import (LessonServiceError, clear_lesson_manifest_cache, create_lesson_draft,
    get_student_lesson_manifest, publish_lesson, update_lesson_blocks, delete_lesson_record)
from services.progress import ProgressServiceError, list_attempts, restart_progress_record, save_progress_record
from services.topics import create_topic, set_topic_archived

TEST_URL = os.getenv("LEARNING_CYCLE_TEST_DATABASE_URL")
MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/20260924122116_learning_cycle.sql"


def validated_test_url(value):
    parsed = make_url(value)
    if parsed.host not in {"127.0.0.1", "localhost", "::1"} or parsed.database != "learning_test":
        raise ValueError("Integration tests require an isolated localhost database named learning_test")
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("Integration tests require PostgreSQL")
    return parsed.set(drivername="postgresql+asyncpg")


@unittest.skipUnless(TEST_URL, "Set LEARNING_CYCLE_TEST_DATABASE_URL for isolated PostgreSQL tests")
class LearningCycleIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(validated_test_url(TEST_URL))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute("""DO $$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
            END $$;""")
        self.db = self.sessions()
        self.teacher = Teacher(name=f"Integration teacher {uuid4().hex[:8]}")
        self.student = Student(name="Integration learner", grade=7)
        self.other = Student(name="Integration new learner", grade=7)
        self.subject = Subject(name="Математика", grade=7, hours_per_week=1, hours_per_year=1)
        self.db.add_all([self.teacher, self.student, self.other, self.subject])
        await self.db.flush()
        self.section = Section(subject_id=self.subject.id, name="Числа", sort_order=1, total_hours=1)
        self.db.add(self.section)
        await self.db.commit()
        self.admin = AuthPrincipal(profile_id=1, auth_user_id=uuid4(), organization_id=1, role="admin",
            login_name="integration", display_name="Integration", must_change_password=False,
            teacher_id=self.teacher.id, student_id=None, grade=None, access_token="test")
        clear_lesson_manifest_cache()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()
        clear_lesson_manifest_cache()

    async def migrate(self):
        await self.db.commit()
        async with self.engine.begin() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(MIGRATION.read_text())

    async def create_assessment(self):
        study = await create_topic(self.section.id, {"name": "Сложение", "learning_objectives": "Складывать числа"}, self.admin, self.db)
        assessment = await create_topic(self.section.id, {"name": "Контрольная работа", "lesson_type": "assessment"}, self.admin, self.db)
        self.assertEqual(assessment["covered_topic_ids"], [study["id"]])
        topic = await self.db.get(Topic, assessment["id"])
        self.assertNotIn("Освоение", topic.learning_objectives)
        objectives = decompose_objectives(topic.learning_objectives)
        self.assertTrue(objectives)
        blocks = [{"component": "MasteryCheck", "content": {
            "title": "Контрольная", "objective_ids": [o["id"] for o in objectives], "evidence_stage": "assessment",
            "questions": [{"id": f"q{i}", "question": "Сколько будет 2 + 2?", "type": "numeric",
                "correct_answer": "4", "explanation": "Два и два дают четыре", "objective_ids": [o["id"]]}
                for i, o in enumerate(objectives)],
        }}]
        lesson = await create_lesson_draft(topic.id, self.teacher.id, self.db)
        self.assertEqual(lesson.blocks, [])
        self.assertEqual((await create_lesson_draft(topic.id, self.teacher.id, self.db)).id, lesson.id)
        await update_lesson_blocks(lesson.id, blocks, self.db)
        await publish_lesson(lesson.id, self.teacher.id, True, self.db)
        return topic, lesson, blocks

    async def test_learning_cycle_preserves_versions_and_history(self):
        await self.migrate()
        topic, lesson, blocks = await self.create_assessment()
        first_version = lesson.published_version_id
        self.assertIsNotNone(first_version)
        manifest = await get_student_lesson_manifest(topic_id=topic.id, student_id=self.student.id, db=self.db)
        self.assertEqual(manifest["lesson"]["active_version_id"], first_version)
        responses = {f"0_q{i}": "4" for i in range(len(blocks[0]["content"]["questions"]))}
        payload = ProgressInput(student_id=self.student.id, topic_id=topic.id, status="completed",
            lesson_version_id=first_version, responses=responses)
        result = await save_progress_record(payload, self.db)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(len(await list_attempts(self.student.id, topic.id, self.db)), 1)
        duplicate = await save_progress_record(payload, self.db)
        self.assertEqual(duplicate.attempts, 1)
        self.assertEqual(len(await list_attempts(self.student.id, topic.id, self.db)), 1)
        restarted = await restart_progress_record(student_id=self.student.id, topic_id=topic.id, db=self.db)
        self.assertEqual(restarted.status, "in_progress")
        self.assertEqual(restarted.lesson_version_id, first_version)
        revised = deepcopy(blocks)
        revised[0]["content"]["questions"][0]["question"] = "Новая версия: 3 + 1?"
        await update_lesson_blocks(lesson.id, revised, self.db)
        self.assertEqual(lesson.published_version_id, first_version)
        self.assertNotEqual(lesson.active_version_id, first_version)
        await publish_lesson(lesson.id, self.teacher.id, True, self.db)
        second_version = lesson.published_version_id
        pinned = await get_student_lesson_manifest(topic_id=topic.id, student_id=self.student.id, db=self.db)
        fresh = await get_student_lesson_manifest(topic_id=topic.id, student_id=self.other.id, db=self.db)
        self.assertEqual(pinned["lesson"]["active_version_id"], first_version)
        self.assertEqual(fresh["lesson"]["active_version_id"], second_version)
        completed = await save_progress_record(payload, self.db)
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.attempts, 2)
        self.assertEqual(completed.lesson_version_id, first_version)
        self.assertEqual(len(await list_attempts(self.student.id, topic.id, self.db)), 2)
        await set_topic_archived(topic.id, True, self.admin, self.db)
        history = await get_student_lesson_manifest(topic_id=topic.id, student_id=self.student.id, db=self.db)
        self.assertEqual(history["lesson"]["active_version_id"], first_version)
        with self.assertRaises(LessonServiceError):
            await get_student_lesson_manifest(topic_id=topic.id, student_id=self.other.id, db=self.db)
        with self.assertRaises(ProgressServiceError):
            await restart_progress_record(student_id=self.student.id, topic_id=topic.id, db=self.db)
        with self.assertRaises(LessonServiceError):
            await delete_lesson_record(lesson.id, self.db)
        await set_topic_archived(topic.id, False, self.admin, self.db)
        self.assertEqual(lesson.status, "draft")
        self.assertIsNone(lesson.published_version_id)
        self.assertEqual(len(await list_attempts(self.student.id, topic.id, self.db)), 2)
        with self.assertRaises(LessonServiceError):
            await get_student_lesson_manifest(topic_id=topic.id, student_id=self.other.id, db=self.db)

    async def test_migration_backfills_without_changing_authored_content(self):
        topic, lesson, blocks = await self.create_assessment()
        version_id = lesson.active_version_id
        original_document = deepcopy((await self.db.get(LessonVersion, version_id)).lesson_document)
        lesson.published_version_id = None
        old_result = Progress(student_id=self.student.id, topic_id=topic.id, status="completed", score=73,
            attempts=2, answers={"0_q0": False}, lesson_version_id=None)
        self.db.add(old_result)
        reflection = Topic(section_id=self.section.id, name="Анализ контрольной работы", lesson_type="assessment",
            sort_order=99, learning_objectives="Авторская цель", skills=["Авторский навык"])
        self.db.add(reflection)
        await self.db.commit()
        await self.migrate()
        await self.db.refresh(lesson)
        await self.db.refresh(old_result)
        await self.db.refresh(reflection)
        self.assertEqual(lesson.published_version_id, version_id)
        self.assertEqual(old_result.lesson_version_id, version_id)
        self.assertEqual(old_result.score, 73)
        attempts = await list_attempts(self.student.id, topic.id, self.db)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["snapshot"]["score"], 73)
        self.assertEqual(reflection.lesson_type, "reflection")
        self.assertEqual(reflection.learning_objectives, "Авторская цель")
        self.assertEqual(reflection.skills, ["Авторский навык"])
        self.assertEqual((await self.db.get(LessonVersion, version_id)).lesson_document, original_document)
        await self.migrate()
        self.assertEqual(len(await list_attempts(self.student.id, topic.id, self.db)), 1)

    async def test_first_legacy_edit_pins_existing_results_before_replacing_blocks(self):
        from services.lessons import preserve_published_version
        topic, lesson, blocks = await self.create_assessment()
        lesson.active_version_id = None
        lesson.published_version_id = None
        progress = Progress(student_id=self.student.id, topic_id=topic.id, status="completed", score=50,
            attempts=1, lesson_version_id=None)
        history = LessonAttempt(student_id=self.student.id, topic_id=topic.id, attempt_number=1,
            lesson_version_id=None, snapshot={"score": 50})
        self.db.add_all([progress, history])
        await self.db.commit()
        await preserve_published_version(lesson, self.db)
        pinned_id = lesson.published_version_id
        self.assertIsNotNone(pinned_id)
        revised = deepcopy(blocks)
        revised[0]["content"]["questions"][0]["question"] = "Новое задание"
        await update_lesson_blocks(lesson.id, revised, self.db)
        await self.db.refresh(progress)
        await self.db.refresh(history)
        self.assertEqual(progress.lesson_version_id, pinned_id)
        self.assertEqual(history.lesson_version_id, pinned_id)
        self.assertNotEqual(lesson.active_version_id, pinned_id)
        self.assertEqual(progress.score, 50)
        self.assertNotIn("Новое задание", str((await self.db.get(LessonVersion, pinned_id)).lesson_document))


def test_integration_url_guard_rejects_production():
    with unittest.TestCase().assertRaises(ValueError):
        validated_test_url("postgresql+asyncpg://user:password@production.example/learning_test")
    with unittest.TestCase().assertRaises(ValueError):
        validated_test_url("postgresql+asyncpg://user:password@127.0.0.1/postgres")
