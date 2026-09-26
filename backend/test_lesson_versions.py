from copy import deepcopy
from types import SimpleNamespace
from functools import wraps
import asyncio

import pytest

from lesson_contracts import adapt_legacy_blocks
from models import GeneratedLesson, LessonVersion
from objectives import quality_report
from services.lessons import (
    LessonServiceError, get_student_lesson_manifest, preserve_published_version,
    require_available_student_lesson, serialize_lesson, student_version_payload,
    clear_lesson_manifest_cache, remember_lesson_manifest, remember_student_manifest_state,
    update_lesson_blocks, publish_lesson, create_lesson_draft,
)
from test_objectives import FakeLessonSession, complete_single_objective_blocks
from models import Topic, Teacher


def async_test(function):
    @wraps(function)
    def run():
        return asyncio.run(function())
    return run


class VersionSession(FakeLessonSession):
    def __init__(self):
        topic = Topic(id=1, section_id=1, name="Сложение", learning_objectives="Складывать числа", lesson_type="study")
        blocks = complete_single_objective_blocks(topic.learning_objectives)
        lesson = GeneratedLesson(id=2, topic_id=1, blocks=deepcopy(blocks), status="published",
                                 lesson_metadata={"learning_objectives": topic.learning_objectives},
                                 active_version_id=10, published_version_id=10)
        super().__init__(Teacher(id=3, name="Учитель"), lesson, topic)
        self.versions = {10: LessonVersion(id=10, lesson_id=2, version_number=1,
            blueprint=deepcopy(lesson.lesson_metadata), lesson_document=adapt_legacy_blocks(blocks, lesson.lesson_metadata))}
        self.pending = []

    async def get(self, model, row_id):
        if model is LessonVersion:
            return self.versions.get(row_id)
        return await super().get(model, row_id)

    async def scalar(self, statement):
        if "max(" in str(statement):
            return max(v.version_number for v in self.versions.values())
        return self.lesson

    async def scalars(self, statement):
        return SimpleNamespace(all=lambda: [])

    def add(self, value):
        self.pending.append(value)

    async def flush(self):
        for value in self.pending:
            if isinstance(value, LessonVersion) and value.id is None:
                value.id = max(self.versions) + 1
                self.versions[value.id] = value
        self.pending = []


@async_test
async def test_draft_edit_preserves_published_content_until_explicit_publish():
    db = VersionSession()
    old = deepcopy(db.versions[10].lesson_document)
    blocks = deepcopy(db.lesson.blocks)
    blocks[1]["content"]["text"] = "Изменённый черновик"
    lesson = await update_lesson_blocks(2, blocks, db)
    assert lesson.active_version_id == 11
    assert lesson.published_version_id == 10
    assert lesson.status == "published"
    assert db.versions[10].lesson_document == old
    assert serialize_lesson(lesson)["has_unpublished_changes"]
    student = await student_version_payload(serialize_lesson(lesson), None, db)
    assert student["active_version_id"] == 10
    assert student["lesson_document"] == old
    await publish_lesson(2, 3, True, db)
    assert lesson.published_version_id == 11
    assert not serialize_lesson(lesson)["has_unpublished_changes"]
    ongoing = await student_version_payload(serialize_lesson(lesson), {"lesson_version_id": 10}, db)
    assert ongoing["lesson_document"] == old


@async_test
async def test_pinned_cache_response_cannot_leak_into_other_students():
    clear_lesson_manifest_cache()
    db = VersionSession()
    base = serialize_lesson(db.lesson)
    base["active_version_id"] = 11
    base["published_version_id"] = 11
    remember_lesson_manifest(1, {"lesson": base, "subject_grade": 7, "has_graph": False})
    remember_student_manifest_state(4, 1, {"student_grade": 7, "progress": {"lesson_version_id": 10}})
    remember_student_manifest_state(5, 1, {"student_grade": 7, "progress": None})
    pinned = await get_student_lesson_manifest(topic_id=1, student_id=4, db=db)
    fresh = await get_student_lesson_manifest(topic_id=1, student_id=5, db=db)
    assert pinned["lesson"]["active_version_id"] == 10
    assert fresh["lesson"]["active_version_id"] == 11
    clear_lesson_manifest_cache()


@async_test
async def test_foreign_version_is_rejected():
    db = VersionSession()
    db.versions[10].lesson_id = 500
    with pytest.raises(LessonServiceError):
        await student_version_payload({"id": 2, "active_version_id": 11}, {"lesson_version_id": 10}, db)


@pytest.mark.parametrize("progress", [None, {"status": "not_started"}, {"status": "in_progress"}])
def test_archived_lesson_rejects_new_or_ongoing_attempt(progress):
    with pytest.raises(LessonServiceError):
        require_available_student_lesson(True, progress)


def test_archived_completed_attempt_remains_readable():
    require_available_student_lesson(True, {"status": "completed"})


def test_assessment_requires_only_final_evidence_and_supported_components():
    blocks = complete_single_objective_blocks("Складывать числа")
    checks = [b for b in blocks if b["component"] == "MasteryCheck"]
    contract = {"lesson_type": "assessment"}
    report = quality_report(checks, "Складывать числа", contract)
    assert report["quality_report"]["publishable"]
    assert not quality_report(checks, "Складывать числа")["quality_report"]["publishable"]
    invalid = quality_report(blocks, "Складывать числа", contract)
    assert any(e["code"] == "assessment_unsupported_component" for e in invalid["quality_report"]["errors"])


@async_test
async def test_manual_draft_creation_reuses_existing_lesson():
    db = VersionSession()
    lesson = await create_lesson_draft(1, 3, db)
    assert lesson is db.lesson
    assert db.commits == 0


@async_test
async def test_media_generation_forks_published_version_and_reuses_draft():
    from services.lessons import ensure_lesson_media_draft
    db = VersionSession()
    old = deepcopy(db.versions[10].lesson_document)
    draft_id = await ensure_lesson_media_draft(10, db)
    assert draft_id == 11
    assert db.lesson.published_version_id == 10
    assert db.lesson.active_version_id == 11
    assert db.versions[10].lesson_document == old
    assert await ensure_lesson_media_draft(11, db) == 11
    with pytest.raises(LessonServiceError):
        await ensure_lesson_media_draft(10, db)


@async_test
async def test_media_completion_after_publish_forks_again():
    from services.lessons import ensure_lesson_media_draft
    db = VersionSession()
    draft_id = await ensure_lesson_media_draft(10, db)
    db.lesson.published_version_id = draft_id
    db.versions[draft_id].status = "published"
    next_draft = await ensure_lesson_media_draft(draft_id, db)
    assert next_draft == 12
    assert db.lesson.published_version_id == 11


@async_test
async def test_cold_manifest_returns_published_blocks_and_metadata():
    clear_lesson_manifest_cache()
    db = VersionSession()
    published_document = deepcopy(db.versions[10].lesson_document)
    db.lesson.active_version_id = 11
    db.lesson.blocks = [{"component": "ShortExplanation", "content": {"text": "SECRET DRAFT"}}]
    db.lesson.lesson_metadata = {"topic_name": "SECRET DRAFT"}
    db.execute = lambda statement: async_row((db.lesson, 7, 7, "available", False, published_document, None))
    result = await get_student_lesson_manifest(topic_id=1, student_id=7, db=db)
    assert result["lesson"]["active_version_id"] == 10
    assert "SECRET DRAFT" not in str(result)
    clear_lesson_manifest_cache()


async def async_row(value):
    return SimpleNamespace(first=lambda: value)


@async_test
async def test_topic_edit_creates_draft_without_changing_published_metadata():
    from services.lessons import refresh_lesson_topic_draft
    db = VersionSession()
    old = deepcopy(db.versions[10].lesson_document)
    db.topic.name = "Повторение сложения"
    db.topic.lesson_type = "review"
    await refresh_lesson_topic_draft(db.topic, db)
    assert db.lesson.active_version_id == 11
    assert db.lesson.published_version_id == 10
    assert db.versions[10].lesson_document == old
    assert db.versions[11].blueprint["lesson_type"] == "review"
    assert db.versions[11].lesson_document["title"] == "Повторение сложения"


@async_test
async def test_delete_protects_published_and_historical_lessons():
    from services.lessons import delete_lesson_record
    from unittest.mock import AsyncMock
    db = VersionSession()
    with pytest.raises(LessonServiceError) as published:
        await delete_lesson_record(2, db)
    assert published.value.status_code == 409
    db.lesson.status = "draft"
    db.lesson.published_version_id = None
    db.scalar = AsyncMock(return_value=True)
    with pytest.raises(LessonServiceError) as history:
        await delete_lesson_record(2, db)
    assert history.value.status_code == 409
    assert db.deleted == []


@async_test
async def test_teacher_can_publish_over_any_errors_after_confirming():
    db = VersionSession()
    blocks = deepcopy(db.lesson.blocks)
    objective_ids = next(b["content"]["objective_ids"] for b in blocks if b["content"].get("objective_ids"))
    # Мягкий недочёт: у цели нет итоговой проверки.
    await update_lesson_blocks(2, [b for b in blocks if b["component"] != "MasteryCheck"], db)
    report = quality_report(db.lesson.blocks, db.topic.learning_objectives)["quality_report"]
    assert not report["publishable"] and report["overridable"]
    with pytest.raises(LessonServiceError):
        await publish_lesson(2, 3, True, db)
    lesson = await publish_lesson(2, 3, True, db, override_errors=True)
    assert lesson.lesson_metadata["quality_review"]["overridden_error_codes"]

    # Сломанный интерактив — тоже под ответственность учителя.
    broken_solver = {"component": "StepSolver", "content": {"objective_ids": objective_ids, "evidence_stage": "practice",
                                                             "start": "Упростите выражение", "final_answer": ["1"]}}
    await update_lesson_blocks(2, blocks[:-1] + [broken_solver] + blocks[-1:], db)
    assert quality_report(db.lesson.blocks, db.topic.learning_objectives)["quality_report"]["overridable"]
    with pytest.raises(LessonServiceError):
        await publish_lesson(2, 3, True, db)
    lesson = await publish_lesson(2, 3, True, db, override_errors=True)
    assert "step_solver_invalid" in lesson.lesson_metadata["quality_review"]["overridden_error_codes"]
