import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from models import GeneratedLesson, Section, Subject, Teacher, Topic
from services import lesson_generation_jobs as jobs
from services.lessons import LessonServiceError, generate_lesson_draft


def lesson(status="running", request_id="request-one"):
    return GeneratedLesson(id=3, topic_id=7, blocks=[{"original": True}], status="draft", lesson_metadata={
        "original": "retained", "generation_job": {
            "job_id": "job-one", "request_id": request_id, "status": status,
            "deadline_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        },
    })


class SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return False


class GenerationJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_commits_marker_before_dispatch_and_preserves_draft(self):
        row = lesson("failed")
        db = SimpleNamespace(get=AsyncMock(return_value=Teacher(id=4)), commit=AsyncMock(), add=Mock())
        gate = asyncio.Event()
        async def runner(*args):
            await gate.wait()
        with patch.object(jobs, "locked_lesson", AsyncMock(return_value=row)), patch.object(jobs, "run_generation_job", runner), patch("llm.catalog.resolve_lesson_choice", return_value=None):
            result = await jobs.start_generation_job(7, 4, db, request_id="new-request")
            self.assertEqual(result["status"], "running")
            self.assertEqual(row.blocks, [{"original": True}])
            self.assertEqual(row.lesson_metadata["original"], "retained")
            self.assertEqual(jobs.marker_for(row)["request_id"], "new-request")
            db.commit.assert_awaited_once()
            self.assertEqual(len(jobs._tasks), 1)
            gate.set()
            await asyncio.gather(*jobs._tasks)
            await asyncio.sleep(0)

    async def test_active_topic_and_completed_request_are_deduplicated(self):
        for status, request in (("running", "different-request"), ("failed", "request-one"), ("succeeded", "request-one")):
            row = lesson(status)
            db = SimpleNamespace(get=AsyncMock(return_value=Teacher(id=4)), commit=AsyncMock())
            with patch.object(jobs, "locked_lesson", AsyncMock(return_value=row)), patch.object(jobs, "run_generation_job", AsyncMock()) as runner, patch("llm.catalog.resolve_lesson_choice", return_value=None), patch.object(jobs, "serialize_lesson", return_value={"id": 3}), patch.object(jobs, "attach_lesson_document", AsyncMock()):
                result = await jobs.start_generation_job(7, 4, db, request_id=request)
            self.assertEqual(result["job_id"], "job-one")
            runner.assert_not_called()

    async def test_invalid_inputs_do_not_commit_or_dispatch(self):
        db = SimpleNamespace(get=AsyncMock(return_value=None), commit=AsyncMock())
        with self.assertRaises(LessonServiceError) as error:
            await jobs.start_generation_job(7, 4, db, content_language="xx")
        self.assertEqual(error.exception.status_code, 422)
        with patch("llm.catalog.resolve_lesson_choice", return_value=None):
            with self.assertRaises(LessonServiceError) as error:
                await jobs.start_generation_job(7, 4, db)
        self.assertEqual(error.exception.status_code, 404)
        db.commit.assert_not_awaited()

    async def test_stale_status_fails_without_provider_retry(self):
        row = lesson()
        row.lesson_metadata["generation_job"]["deadline_at"] = "2000-01-01T00:00:00+00:00"
        db = SimpleNamespace(scalar=AsyncMock(return_value=row), commit=AsyncMock())
        with patch.object(jobs, "locked_lesson", AsyncMock(return_value=row)), patch.object(jobs, "run_generation_job", AsyncMock()) as runner:
            result = await jobs.generation_job_status("job-one", 7, db)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(row.blocks, [{"original": True}])
        runner.assert_not_called()
        db.commit.assert_awaited_once()

    async def test_wrong_job_is_404(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=lesson()))
        with self.assertRaises(LessonServiceError) as error:
            await jobs.generation_job_status("other-job", 7, db)
        self.assertEqual(error.exception.status_code, 404)

    async def test_success_status_loads_authoritative_draft_document(self):
        row = lesson("succeeded")
        db = SimpleNamespace(scalar=AsyncMock(return_value=row))
        with patch.object(jobs, "attach_lesson_document", AsyncMock()) as attach, patch.object(jobs, "serialize_lesson", return_value={"id": 3, "lesson_document": {"schema_version": 2}}):
            result = await jobs.generation_job_status("job-one", 7, db)
        attach.assert_awaited_once_with(row, db, hydrate_assets=False)
        self.assertEqual(result["lesson"]["lesson_document"]["schema_version"], 2)

    async def test_failure_marker_cannot_overwrite_a_new_job(self):
        row = lesson()
        db = SimpleNamespace(scalar=AsyncMock(return_value=row), commit=AsyncMock())
        with patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(db)):
            await jobs.fail_generation_job("old-job", 7, "Failed")
        db.commit.assert_not_awaited()
        self.assertEqual(jobs.marker_for(row)["status"], "running")

    async def test_worker_uses_independent_session_and_sanitizes_provider_error(self):
        db = object()
        generator = AsyncMock(side_effect=RuntimeError("secret-provider-response"))
        fail = AsyncMock()
        with patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(db)), patch.object(jobs, "generate_lesson_draft", generator), patch.object(jobs, "fail_generation_job", fail):
            await jobs.run_generation_job("job-one", 7, 4, None, "ru")
        self.assertIs(generator.call_args.args[2], db)
        self.assertEqual(generator.call_args.kwargs["generation_job_id"], "job-one")
        self.assertNotIn("secret", fail.call_args.args[2])
        generator.assert_awaited_once()

    async def test_timeout_stops_worker_without_retry(self):
        async def generator(*args, **kwargs):
            await asyncio.sleep(60)
        with patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(object())), patch.object(jobs, "generate_lesson_draft", generator), patch.object(jobs, "GENERATION_TIMEOUT_SECONDS", .001), patch.object(jobs, "fail_generation_job", AsyncMock()) as fail:
            await jobs.run_generation_job("job-one", 7, 4, None, None)
        self.assertIn("слишком много времени", fail.call_args.args[2])

    async def test_sync_reservation_refuses_existing_running_job(self):
        db = SimpleNamespace(get=AsyncMock(return_value=Teacher(id=4)), commit=AsyncMock())
        with patch.object(jobs, "locked_lesson", AsyncMock(return_value=lesson())), patch("llm.catalog.resolve_lesson_choice", return_value=None):
            with self.assertRaises(LessonServiceError) as error:
                await jobs.start_generation_job(7, 4, db, dispatch=False)
        self.assertEqual(error.exception.status_code, 409)
        db.commit.assert_not_awaited()

    async def test_completion_fences_new_job_revision_expiry_and_archival(self):
        from test_objectives import FakeGenerateSession
        for change in ("new_job", "revision", "publication", "expiry", "archive"):
            row = lesson()
            row.active_version_id = 10
            row.published_version_id = 9
            row.lesson_metadata["generation_job"].update(base_version_id=10, base_published_version_id=9)
            topic = Topic(id=7, section_id=2, name="Сложение", learning_objectives="Складывать числа", skills=[], hours=1, lesson_type="study")
            subject = Subject(id=1, name="Математика", grade=7, instruction_language="ru")
            db = FakeGenerateSession(Teacher(id=4), topic, Section(id=2, subject_id=1), subject, row)
            async def generator(**kwargs):
                if change == "new_job":
                    row.lesson_metadata["generation_job"]["job_id"] = "new-job"
                elif change == "revision":
                    row.active_version_id = 11
                elif change == "publication":
                    row.published_version_id = 10
                elif change == "expiry":
                    row.lesson_metadata["generation_job"]["deadline_at"] = "2000-01-01T00:00:00+00:00"
                else:
                    topic.archived_at = datetime.now(timezone.utc)
                return []
            with patch("services.textbook_context.load_textbook_context", AsyncMock(return_value=None)), patch("llm.catalog.resolve_lesson_choice", return_value=None):
                with self.assertRaises(LessonServiceError) as error:
                    await generate_lesson_draft(7, 4, db, lesson_generator=generator, generation_job_id="job-one")
            self.assertEqual(error.exception.status_code, 409, change)
            self.assertEqual(row.blocks, [{"original": True}], change)
            self.assertEqual(db.commits, 0, change)

    async def test_generation_routes_precede_dynamic_topic_and_require_educator(self):
        from routes.lessons import router
        from test_auth_dependencies import principal
        paths = [route.path for route in router.routes]
        for path in ("/api/lessons/generate/start", "/api/lessons/generate/status/{job_id}"):
            self.assertLess(paths.index(path), paths.index("/api/lessons/{topic_id}"))
            route = next(route for route in router.routes if route.path == path)
            dependency = next(item for item in route.dependant.dependencies if item.name == "user")
            with self.assertRaises(Exception) as error:
                await dependency.call(principal(role="student"))
            self.assertEqual(error.exception.status_code, 403)

    def test_malformed_or_naive_deadline_is_expired(self):
        for value in (None, "nonsense", "2026-10-11T00:00:00"):
            self.assertTrue(jobs.marker_expired({"deadline_at": value}))


if __name__ == "__main__":
    unittest.main()
