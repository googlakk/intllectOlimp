import asyncio
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from models import GeneratedLesson, Section, Teacher, Topic
from services import lesson_generation_batches as batches
from services import lesson_generation_jobs as jobs
from services.auth import AuthServiceError
from services.lessons import LessonServiceError
from test_lesson_generation_jobs import SessionContext


def topic(topic_id):
    return Topic(id=topic_id, section_id=2, name=f"Тема {topic_id}", learning_objectives="Объяснять", archived_at=None)


def row(topic_id, status="queued", batch_id="batch-one", topic_ids=None):
    return GeneratedLesson(id=topic_id + 100, topic_id=topic_id, status="draft", blocks=[], lesson_metadata={
        "generation_job": {"batch_id": batch_id, "job_id": f"job-{topic_id}", "status": status,
            "topic_ids": topic_ids or [1, 2], "topic_names": {"1": "Тема 1", "2": "Тема 2"},
            "created_at": "2026-10-12T00:00:00+00:00", "worker_token": jobs.WORKER_TOKEN,
            "deadline_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
            "base_version_id": None, "base_published_version_id": None}})


class BatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = []
        self.topics = {1: topic(1), 2: topic(2)}
        self.db = SimpleNamespace(commit=AsyncMock(), add=Mock(), scalar=AsyncMock(return_value=object()),
                                  get=AsyncMock(side_effect=lambda model, ident: Teacher(id=4) if model is Teacher else Section(id=2, subject_id=1)))
        self.user = SimpleNamespace(role="admin")
        self.stack = ExitStack()
        self.stack.enter_context(patch("llm.catalog.resolve_lesson_choice", return_value=None))
        self.stack.enter_context(patch.object(batches, "require_subject_management", AsyncMock()))
        self.access = self.stack.enter_context(patch.object(batches, "require_topic_management", AsyncMock(side_effect=lambda user, ident, db: self.topics[ident])))
        self.stack.enter_context(patch.object(batches, "subject_batch_rows", AsyncMock(side_effect=lambda *args: self.rows)))
        self.locked = self.stack.enter_context(patch.object(jobs, "locked_lesson", AsyncMock(side_effect=lambda ident, db: next((item for item in self.rows if item.topic_id == ident), None))))
        self.dispatch = self.stack.enter_context(patch.object(jobs, "dispatch_generation_job"))

    def tearDown(self):
        self.stack.close()

    async def start(self, **kwargs):
        return await batches.start_generation_batch(1, kwargs.pop("topic_ids", [2, 1]), 4, kwargs.pop("request_id", "batch-one"), self.user, self.db, **kwargs)

    async def test_atomic_reservation_authorizes_all_then_dispatches_after_commit(self):
        events = []
        self.db.commit.side_effect = lambda: events.append("commit")
        self.dispatch.side_effect = lambda *args: events.append("dispatch")
        result = await self.start()
        self.assertEqual([item["topic_id"] for item in result["items"]], [2, 1])
        self.assertEqual(result["counts"]["queued"], 2)
        self.assertEqual(events, ["commit", "dispatch", "dispatch"])
        self.assertEqual([call.args[0] for call in self.locked.await_args_list], [1, 2])
        self.assertEqual(self.access.await_count, 2)

    async def test_unauthorized_selection_has_no_reservations_or_provider_calls(self):
        self.access.side_effect = [self.topics[2], AuthServiceError(404, "not assigned")]
        with self.assertRaises(AuthServiceError):
            await self.start()
        self.locked.assert_not_awaited()
        self.db.commit.assert_not_awaited()
        self.dispatch.assert_not_called()

    async def test_invalid_selection_model_and_language_fail_without_commit(self):
        for ids in ([], [1, 1], [0], list(range(1, 32))):
            with self.assertRaises(LessonServiceError):
                await self.start(topic_ids=ids)
        with self.assertRaises(LessonServiceError):
            await self.start(content_language="xx")
        from llm.catalog import ModelChoiceError
        with patch("llm.catalog.resolve_lesson_choice", side_effect=ModelChoiceError("Bad model")):
            with self.assertRaises(LessonServiceError):
                await self.start()
        self.db.commit.assert_not_awaited()
        self.dispatch.assert_not_called()

    async def test_missing_objectives_published_and_materials_reject_all_before_write(self):
        for reason in ("objectives", "published", "materials", "active"):
            with self.subTest(reason=reason):
                current = row(2, "failed")
                self.rows = [current]
                self.topics[2].learning_objectives = "" if reason == "objectives" else "Объяснять"
                if reason == "published":
                    current.published_version_id = 10
                if reason == "materials":
                    current.blocks = [{"old": True}]
                if reason == "active":
                    jobs.write_marker(current, {**jobs.marker_for(current), "status": "running"})
                with self.assertRaises(LessonServiceError):
                    await self.start(request_id="new-request")
                self.db.add.assert_not_called()
                self.db.commit.assert_not_awaited()
                self.dispatch.assert_not_called()

    async def test_draft_replacement_is_explicit_preserves_materials_and_history(self):
        current = row(2, "succeeded")
        current.blocks = [{"old": True}]
        self.rows = [current]
        await self.start(request_id="new-request", replace_existing_drafts=True)
        self.assertEqual(current.blocks, [{"old": True}])
        self.assertEqual(current.lesson_metadata["generation_batch_history"]["batch-one"]["status"], "succeeded")

    async def test_replacing_expired_batch_archives_failed_instead_of_forever_running(self):
        current = row(2, "running")
        jobs.write_marker(current, {**jobs.marker_for(current), "worker_token": "previous-server"})
        self.rows = [current]
        await self.start(request_id="new-request")
        self.assertEqual(current.lesson_metadata["generation_batch_history"]["batch-one"]["status"], "failed")

    async def test_mixed_subject_selection_does_not_reserve_or_dispatch(self):
        self.db.get.side_effect = lambda model, ident: Teacher(id=4) if model is Teacher else Section(id=2, subject_id=9)
        with self.assertRaises(LessonServiceError) as error:
            await self.start()
        self.assertEqual(error.exception.status_code, 422)
        self.locked.assert_not_awaited()
        self.dispatch.assert_not_called()

    async def test_archived_topic_rejects_all_before_write(self):
        self.locked.side_effect = [None, LessonServiceError(409, "restore archived topic")]
        with self.assertRaises(LessonServiceError):
            await self.start()
        self.db.add.assert_not_called()
        self.db.commit.assert_not_awaited()
        self.dispatch.assert_not_called()

    async def test_same_request_reloads_existing_without_dispatch_even_after_completion(self):
        await self.start()
        self.rows = [call.args[0] for call in self.db.add.call_args_list]
        self.dispatch.reset_mock()
        for item in self.rows:
            jobs.write_marker(item, {**jobs.marker_for(item), "status": "succeeded"})
        result = await self.start(topic_ids=[1, 2])
        self.assertEqual(result["status"], "succeeded")
        self.dispatch.assert_not_called()
        with self.assertRaises(LessonServiceError) as error:
            await self.start(content_language="ky")
        self.assertEqual(error.exception.status_code, 409)

    async def test_commit_failure_never_dispatches(self):
        self.db.commit.side_effect = RuntimeError("DB unavailable")
        with self.assertRaises(RuntimeError):
            await self.start()
        self.dispatch.assert_not_called()

    async def test_cancel_only_queued_and_preserves_running_and_completed(self):
        self.rows = [row(1), row(2, "running")]
        self.db.scalar.side_effect = self.rows
        result = await batches.cancel_generation_batch("batch-one", 1, self.user, self.db)
        self.assertEqual([item["status"] for item in result["items"]], ["cancelled", "running"])
        self.assertEqual(result["status"], "running")
        self.dispatch.assert_not_called()

    async def test_cancel_race_does_not_overwrite_running_claim(self):
        queued = row(1, topic_ids=[1])
        self.rows = [queued]
        claimed = row(1, "running", topic_ids=[1])
        self.db.scalar.return_value = claimed
        await batches.cancel_generation_batch("batch-one", 1, self.user, self.db)
        self.assertEqual(jobs.marker_for(claimed)["status"], "running")

    async def test_restart_expires_jobs_without_retry_and_reload_reconstructs_partial_result(self):
        self.rows = [row(1), row(2, "succeeded")]
        jobs.write_marker(self.rows[0], {**jobs.marker_for(self.rows[0]), "worker_token": "previous-server"})
        self.db.scalar.return_value = self.rows[0]
        result = await batches.list_generation_batches(1, self.user, self.db)
        self.assertEqual(result[0]["status"], "partial_failed")
        self.assertEqual(result[0]["counts"]["failed"], 1)
        self.dispatch.assert_not_called()

    async def test_list_keeps_all_active_and_three_recent_terminal_without_losing_old_replay(self):
        first, second = row(1, "queued", batch_id="active-one", topic_ids=[1]), row(2, "running", batch_id="active-two", topic_ids=[2])
        history = {}
        for index in range(6):
            marker = jobs.marker_for(row(1, "succeeded", batch_id=f"old-{index}", topic_ids=[1]))
            marker.update(created_at=f"2026-10-0{index + 1}T00:00:00+00:00", request={
                "topic_ids": [1], "teacher_id": 4, "model": None,
                "content_language": None, "replace_existing_drafts": False})
            history[f"old-{index}"] = jobs.compact_batch_marker(marker)
        first.lesson_metadata = {**first.lesson_metadata, "generation_batch_history": history}
        self.rows = [first, second]
        with patch.object(batches, "batch_markers", wraps=batches.batch_markers) as scan:
            result = await batches.list_generation_batches(1, self.user, self.db)
        self.assertEqual(scan.call_count, 2)  # One grouping pass, not one scan per batch.
        self.assertEqual({item["batch_id"] for item in result[:2]}, {"active-one", "active-two"})
        self.assertEqual([item["batch_id"] for item in result[2:]], ["old-5", "old-4", "old-3"])
        self.assertEqual(len(first.lesson_metadata["generation_batch_history"]), 6)
        replay = await self.start(topic_ids=[1], request_id="old-0")
        self.assertEqual(replay["status"], "succeeded")
        self.dispatch.assert_not_called()

    def test_archived_markers_keep_identity_but_drop_worker_fences(self):
        current = row(1, "succeeded")
        jobs.write_marker(current, {"job_id": "new-single", "status": "queued"})
        archived = current.lesson_metadata["generation_batch_history"]["batch-one"]
        self.assertEqual(archived["batch_id"], "batch-one")
        self.assertEqual(archived["topic_ids"], [1, 2])
        for private_key in ("worker_token", "deadline_at", "base_version_id", "base_published_version_id"):
            self.assertNotIn(private_key, archived)

    def test_history_survives_new_single_job_and_missing_topic_is_failed(self):
        current = row(1, "succeeded")
        jobs.write_marker(current, {"job_id": "single-new", "status": "running"})
        result = batches.batch_payload("batch-one", 1, [current])
        self.assertEqual(result["counts"], {"queued": 0, "running": 0, "succeeded": 1, "failed": 1, "cancelled": 0})


class QueueWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_metadata_keeps_old_batch_history_and_current_completion(self):
        from models import Subject
        from services.lessons import generate_lesson_draft
        from test_objectives import FakeGenerateSession, complete_single_objective_blocks
        current = row(1, "succeeded", batch_id="older-batch", topic_ids=[1])
        marker = {**jobs.marker_for(current), "job_id": "new-job", "batch_id": "new-batch", "status": "running"}
        jobs.write_marker(current, marker)
        current_topic = Topic(id=1, section_id=2, name="Сложение", learning_objectives="Складывать числа", skills=[], hours=1, lesson_type="study")
        db = FakeGenerateSession(Teacher(id=4), current_topic, Section(id=2, subject_id=1),
                                 Subject(id=1, name="Математика", grade=7, instruction_language="ru"), current)
        provider = AsyncMock(return_value=complete_single_objective_blocks(current_topic.learning_objectives))
        with patch("services.textbook_context.load_textbook_context", AsyncMock(return_value=None)), patch("llm.catalog.resolve_lesson_choice", return_value=None):
            await generate_lesson_draft(1, 4, db, lesson_generator=provider, generation_job_id="new-job")
        self.assertEqual(jobs.marker_for(current)["status"], "succeeded")
        self.assertEqual(current.lesson_metadata["generation_batch_history"]["older-batch"]["status"], "succeeded")
        self.assertEqual(db.commits, 1)

    async def test_cancelled_replaced_expired_and_edited_jobs_never_claim_provider_slot(self):
        for reason in ("cancelled", "replaced", "expired", "edited"):
            current = row(1)
            if reason == "cancelled":
                jobs.write_marker(current, {**jobs.marker_for(current), "status": "cancelled"})
            elif reason == "replaced":
                jobs.write_marker(current, {**jobs.marker_for(current), "job_id": "other"})
            elif reason == "expired":
                jobs.write_marker(current, {**jobs.marker_for(current), "worker_token": "previous-server"})
            else:
                current.active_version_id = 10
            db = SimpleNamespace(commit=AsyncMock())
            with patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(db)), patch.object(jobs, "locked_lesson", AsyncMock(return_value=current)):
                self.assertFalse(await jobs.claim_generation_job("job-1", 1), reason)

    async def test_claim_sets_timeout_from_actual_start_after_queue_wait(self):
        current = row(1)
        db = SimpleNamespace(commit=AsyncMock())
        with patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(db)), patch.object(jobs, "locked_lesson", AsyncMock(return_value=current)):
            self.assertTrue(await jobs.claim_generation_job("job-1", 1))
            self.assertFalse(await jobs.claim_generation_job("job-1", 1))
        marker = jobs.marker_for(current)
        self.assertEqual(marker["status"], "running")
        self.assertLess(datetime.fromisoformat(marker["deadline_at"]) - datetime.now(timezone.utc), timedelta(minutes=16))

    async def test_single_and_batch_workers_share_two_slots_and_failure_does_not_block_queue(self):
        active = 0
        peak = 0
        completed = []
        async def work(job_id, *args):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.01)
            completed.append(job_id)
            active -= 1
        with patch.object(jobs, "_generation_slots", asyncio.Semaphore(2)), patch.object(jobs, "_run_generation_job", work):
            await asyncio.gather(*(jobs.run_generation_job(str(index), index, 4, None, None) for index in range(6)))
        self.assertEqual(peak, 2)
        self.assertEqual(len(completed), 6)

    async def test_cancelled_claim_does_not_call_paid_generator(self):
        with patch.object(jobs, "claim_generation_job", AsyncMock(return_value=False)), patch.object(jobs, "generate_lesson_draft", AsyncMock()) as provider:
            await jobs.run_generation_job("job-1", 1, 4, None, None)
        provider.assert_not_awaited()

    async def test_one_provider_failure_does_not_retry_or_stop_other_workers(self):
        completed = []
        async def provider(*args, generation_job_id, **kwargs):
            if generation_job_id == "bad-job":
                raise RuntimeError("secret provider response")
            completed.append(generation_job_id)
        with patch.object(jobs, "_generation_slots", asyncio.Semaphore(2)), patch.object(jobs, "claim_generation_job", AsyncMock(return_value=True)), patch.object(jobs, "AsyncSessionLocal", return_value=SessionContext(object())), patch.object(jobs, "generate_lesson_draft", AsyncMock(side_effect=provider)) as generator, patch.object(jobs, "fail_generation_job", AsyncMock()) as fail:
            await asyncio.gather(*(jobs.run_generation_job(ident, index, 4, None, None) for index, ident in enumerate(["good-one", "bad-job", "good-two"])))
        self.assertEqual(completed, ["good-one", "good-two"])
        self.assertEqual(generator.await_count, 3)
        fail.assert_awaited_once()
        self.assertNotIn("secret", fail.call_args.args[2])

    async def test_queued_lesson_deletion_is_rejected(self):
        from services.lessons import delete_lesson_record
        current = row(1)
        with patch("services.lessons.get_lesson_or_error", AsyncMock(return_value=current)):
            with self.assertRaises(LessonServiceError) as error:
                await delete_lesson_record(current.id, SimpleNamespace())
        self.assertEqual(error.exception.status_code, 409)

    async def test_batch_routes_precede_dynamic_routes_and_require_educator(self):
        from routes.lessons import GenerateBatchInput, router
        from test_auth_dependencies import principal
        paths = [route.path for route in router.routes]
        for route in router.routes:
            if "/generate/batch" not in route.path:
                continue
            self.assertLess(paths.index(route.path), paths.index("/api/lessons/{topic_id}"))
            dep = next(item for item in route.dependant.dependencies if item.name == "user")
            with self.assertRaises(Exception) as error:
                await dep.call(principal(role="student"))
            self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(ValueError):
            GenerateBatchInput(subject_id=1, topic_ids=list(range(31)), teacher_id=4, request_id="e5d81df9-f631-4fcf-baf3-387d0ef46f97")
