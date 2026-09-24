import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import GeneratedLesson, Progress, LessonAttempt, LessonVersion, Student, Topic
from lesson_contracts import flatten_lesson_document
from services.assessment import grade_assessment
from objectives import calculate_objective_mastery, quality_report
from services.grade_access import GradeAccessError, require_topic_access
from services.curriculum_graph import (
    CurriculumGraphError,
    mastery_score_from_progress,
    require_curriculum_topic_access,
    refresh_student_access,
    update_topic_skill_mastery,
)


class ProgressServiceError(ApplicationError):
    pass


def progress_json_literal(column_name: str, value: dict[str, Any]):
    return literal(value, type_=getattr(Progress.__table__.c, column_name).type)


def derive_canonical_mastery(
    blocks: list[dict],
    raw_objectives: str | None,
    answers: dict,
    attempts_by_step: dict,
    *,
    lesson_completed: bool,
):
    canonical = quality_report(blocks, raw_objectives)
    objectives = canonical["objectives"]
    normalized_blocks = canonical["normalized_blocks"]
    has_objective_mappings = any(
        isinstance(block.get("content"), dict)
        and bool(block["content"].get("objective_ids"))
        for block in normalized_blocks
        if isinstance(block, dict)
    )
    if not objectives or not has_objective_mappings:
        return None
    return calculate_objective_mastery(
        normalized_blocks,
        objectives,
        answers,
        attempts_by_step,
        lesson_completed=lesson_completed,
    )


def derive_mastery_status(
    objective_mastery: dict[str, Any] | None,
    fallback: str | None,
) -> str | None:
    if not objective_mastery:
        return fallback
    statuses = [
        item.get("status")
        for item in objective_mastery.values()
        if isinstance(item, dict)
    ]
    if statuses and all(status == "mastered" for status in statuses):
        return "mastered"
    if any(status == "needs_practice" for status in statuses):
        return "needs_practice"
    return "in_progress"


async def save_progress_record(payload: Any, db: AsyncSession) -> Progress:
    try:
        topic = await require_topic_access(payload.student_id, payload.topic_id, db)
    except GradeAccessError as exc:
        raise ProgressServiceError(status_code=exc.status_code, detail=exc.detail) from exc
    if hasattr(db, "execute"):
        try:
            await require_curriculum_topic_access(payload.student_id, payload.topic_id, db)
        except CurriculumGraphError as exc:
            raise ProgressServiceError(status_code=exc.status_code, detail=exc.detail) from exc
    if payload.status == "in_progress" and payload.current_step > payload.max_opened_step:
        raise ProgressServiceError(status_code=422, detail="Текущий шаг ещё не открыт")

    # Serialize updates per learner, including first-save and restart races.
    await db.scalar(select(Student.id).where(Student.id == payload.student_id).with_for_update())
    previous = await db.scalar(select(Progress).where(
        Progress.student_id == payload.student_id, Progress.topic_id == payload.topic_id))
    if previous is not None and previous.status == "completed":
        await db.commit()
        return previous
    if getattr(topic, "archived_at", None) is not None:
        raise ProgressServiceError(status_code=409, detail="Урок убран из программы. Результаты сохранены в истории.")
    now = datetime.now(timezone.utc)
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == payload.topic_id))
    if lesson is None or (lesson.status != "published" and previous is None):
        raise ProgressServiceError(status_code=409, detail="Урок ещё не опубликован")
    lesson_version_id = (getattr(previous, "lesson_version_id", None)
                         or getattr(lesson, "published_version_id", None))
    requested_version = getattr(payload, "lesson_version_id", None)
    if requested_version and requested_version != lesson_version_id:
        raise ProgressServiceError(status_code=409, detail="Версия урока изменилась. Обновите страницу.")
    version = await db.get(LessonVersion, lesson_version_id) if lesson_version_id else None
    if lesson_version_id and (version is None or version.lesson_id != lesson.id):
        raise ProgressServiceError(status_code=409, detail="Сохранённая версия урока недоступна")
    document = version.lesson_document if version is not None else {}
    blocks = flatten_lesson_document(document) if document else lesson.blocks or []
    raw_objectives = ((version.blueprint or {}).get("learning_objectives") if version is not None else None) or topic.learning_objectives
    responses = getattr(payload, "responses", {})
    lesson_type = ((version.blueprint or {}).get("lesson_type") if version is not None else None) or topic.lesson_type
    if lesson_type == "assessment":
        payload.answers, payload.score = grade_assessment(blocks, responses) if payload.status == "completed" else ({}, None)
    objective_mastery, objective_evidence, mastery_status = {}, {}, "not_assessed"
    derived = derive_canonical_mastery(blocks, raw_objectives, payload.answers, payload.attempts_by_step,
                                      lesson_completed=payload.status == "completed")
    if derived is not None:
        objective_mastery, objective_evidence, mastery_status = derived
    mastery_status = derive_mastery_status(objective_mastery, mastery_status)

    insert_mastery_status = mastery_status or "not_assessed"
    insert_objective_evidence = objective_evidence or {}
    insert_objective_mastery = objective_mastery or {}
    answers_update = progress_json_literal("answers", payload.answers)
    attempts_by_step_update = progress_json_literal("attempts_by_step", payload.attempts_by_step)
    objective_evidence_update = (
        Progress.objective_evidence
        if objective_evidence is None
        else progress_json_literal("objective_evidence", objective_evidence)
    )
    objective_mastery_update = (
        Progress.objective_mastery
        if objective_mastery is None
        else progress_json_literal("objective_mastery", objective_mastery)
    )
    mastery_status_update = (
        Progress.mastery_status if mastery_status is None else mastery_status
    )
    status_update = case(
        (Progress.status == "completed", "completed"),
        else_=payload.status,
    )
    completed_at_update = case(
        (Progress.status == "completed", Progress.completed_at),
        else_=now if payload.status == "completed" else None,
    )
    score_update = case(
        (Progress.status == "completed", Progress.score),
        else_=payload.score,
    )
    mastery_update = case(
        (Progress.status == "completed", Progress.mastery_level),
        else_=payload.mastery_level,
    )
    statement = (
        insert(Progress)
        .values(
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            status=payload.status,
            score=payload.score,
            mastery_level=payload.mastery_level,
            time_spent_sec=payload.time_spent_sec,
            started_at=now,
            completed_at=now if payload.status == "completed" else None,
            attempts=1 if payload.status == "completed" else 0,
            current_step=payload.current_step,
            max_opened_step=payload.max_opened_step,
            answers=payload.answers,
            responses=responses,
            attempts_by_step=payload.attempts_by_step,
            elapsed_time_sec=payload.elapsed_time_sec,
            objective_evidence=insert_objective_evidence,
            objective_mastery=insert_objective_mastery,
            mastery_status=insert_mastery_status,
            lesson_version_id=lesson_version_id,
            current_episode_id=getattr(payload, "current_episode_id", None),
            current_scene_id=getattr(payload, "current_scene_id", None),
            avatar_enabled=getattr(payload, "avatar_enabled", True),
            audio_enabled=getattr(payload, "audio_enabled", True),
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[Progress.student_id, Progress.topic_id],
            set_={
                "status": status_update,
                "responses": literal(responses, type_=Progress.__table__.c.responses.type),
                "score": score_update,
                "mastery_level": mastery_update,
                # A completed attempt is a snapshot. Reviewing its answers must
                # not silently turn it back into a partially completed attempt.
                "time_spent_sec": case(
                    (Progress.status == "completed", Progress.time_spent_sec),
                    else_=payload.time_spent_sec,
                ),
                "completed_at": completed_at_update,
                "current_step": case(
                    (Progress.status == "completed", Progress.current_step),
                    else_=payload.current_step,
                ),
                "max_opened_step": case(
                    (Progress.status == "completed", Progress.max_opened_step),
                    else_=payload.max_opened_step,
                ),
                "answers": case(
                    (Progress.status == "completed", Progress.answers),
                    else_=answers_update,
                ),
                "attempts_by_step": case(
                    (Progress.status == "completed", Progress.attempts_by_step),
                    else_=attempts_by_step_update,
                ),
                "elapsed_time_sec": case(
                    (Progress.status == "completed", Progress.elapsed_time_sec),
                    else_=payload.elapsed_time_sec,
                ),
                "objective_evidence": case(
                    (Progress.status == "completed", Progress.objective_evidence),
                    else_=objective_evidence_update,
                ),
                "objective_mastery": case(
                    (Progress.status == "completed", Progress.objective_mastery),
                    else_=objective_mastery_update,
                ),
                "mastery_status": case(
                    (Progress.status == "completed", Progress.mastery_status),
                    else_=mastery_status_update,
                ),
                "lesson_version_id": case(
                    (Progress.status == "completed", Progress.lesson_version_id),
                    else_=lesson_version_id,
                ),
                "current_episode_id": case(
                    (Progress.status == "completed", Progress.current_episode_id),
                    else_=getattr(payload, "current_episode_id", None),
                ),
                "current_scene_id": case(
                    (Progress.status == "completed", Progress.current_scene_id),
                    else_=getattr(payload, "current_scene_id", None),
                ),
                "avatar_enabled": getattr(payload, "avatar_enabled", True),
                "audio_enabled": getattr(payload, "audio_enabled", True),
                "updated_at": now,
                # Re-saving a completed session is idempotent. An attempt is
                # counted only when an in-progress row first becomes complete.
                "attempts": case(
                    (Progress.status == "completed", Progress.attempts),
                    else_=Progress.attempts + (1 if payload.status == "completed" else 0),
                ),
            },
        )
        .returning(Progress)
        .execution_options(populate_existing=True)
    )
    row = await db.scalar(statement)
    if row is None:
        await db.rollback()
        raise ProgressServiceError(status_code=500, detail="Не удалось сохранить прогресс")
    warp_gates: list[dict[str, Any]] = []
    if payload.status == "completed" and await snapshot_attempt(row, db):
        skill_score = mastery_score_from_progress(
            status=payload.status,
            mastery_status=mastery_status,
            score=payload.score,
        )
        await update_topic_skill_mastery(
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            score=skill_score,
            evidence={
                "progress_id": getattr(row, "id", None),
                "objective_skill_map": (version.blueprint or {}).get("objective_skill_map") if version else None,
                "objective_mastery": insert_objective_mastery,
                "objective_evidence": insert_objective_evidence,
                "score": payload.score,
            },
            db=db,
        )
        warp_gates = await refresh_student_access(
            payload.student_id,
            db,
            source_topic_id=payload.topic_id,
        )
    await db.commit()
    from services.curriculum_graph import clear_curriculum_map_cache
    from services.lessons import clear_student_manifest_state_cache

    clear_curriculum_map_cache(payload.student_id)
    clear_student_manifest_state_cache(payload.student_id, payload.topic_id)
    row._warp_gates = warp_gates
    return row


async def restart_progress_record(student_id: int, topic_id: int, db: AsyncSession) -> Progress:
    """Start a new attempt without mutating the completed attempt implicitly."""
    try:
        topic = await require_topic_access(student_id, topic_id, db)
    except GradeAccessError as exc:
        raise ProgressServiceError(status_code=exc.status_code, detail=exc.detail) from exc
    if hasattr(db, "execute"):
        try:
            await require_curriculum_topic_access(student_id, topic_id, db)
        except CurriculumGraphError as exc:
            raise ProgressServiceError(status_code=exc.status_code, detail=exc.detail) from exc

    if getattr(topic, "archived_at", None) is not None:
        raise ProgressServiceError(status_code=409, detail="Урок убран из программы. Новая попытка недоступна.")
    await db.scalar(select(Student.id).where(Student.id == student_id).with_for_update())
    previous = await db.scalar(select(Progress).where(Progress.student_id == student_id, Progress.topic_id == topic_id))
    if previous is None:
        raise ProgressServiceError(status_code=404, detail="Сессия урока не найдена")
    if previous.status != "completed":
        await db.commit()
        return previous
    await snapshot_attempt(previous, db)
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id))
    if lesson is None or lesson.status != "published":
        raise ProgressServiceError(status_code=409, detail="Урок ещё не опубликован")
    now = datetime.now(timezone.utc)
    row = await db.scalar(
        update(Progress)
        .where(Progress.student_id == student_id, Progress.topic_id == topic_id)
        .values(
            status="in_progress",
            score=None,
            mastery_level=None,
            time_spent_sec=0,
            started_at=now,
            completed_at=None,
            current_step=0,
            max_opened_step=0,
            answers={},
            responses={},
            lesson_version_id=lesson.published_version_id,
            attempts_by_step={},
            elapsed_time_sec=0,
            objective_evidence={},
            objective_mastery={},
            mastery_status="not_assessed",
            current_episode_id=None,
            current_scene_id=None,
            updated_at=now,
        )
        .returning(Progress)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise ProgressServiceError(status_code=404, detail="Сессия урока не найдена")
    await db.commit()
    from services.curriculum_graph import clear_curriculum_map_cache
    from services.lessons import clear_student_manifest_state_cache

    clear_curriculum_map_cache(student_id)
    clear_student_manifest_state_cache(student_id, topic_id)
    return row


def serialize_progress(row: Progress) -> dict:
    payload = {column.name: getattr(row, column.name, None) for column in Progress.__table__.columns}
    if hasattr(row, "_warp_gates"):
        payload["warp_gates"] = row._warp_gates
    return payload


async def list_student_progress(student_id: int, db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Progress, Topic.name, Topic.archived_at)
                            .join(Topic, Topic.id == Progress.topic_id)
                            .where(Progress.student_id == student_id))).all()
    return [{**serialize_progress(row), "topic_name": name, "archived_at": archived_at}
            for row, name, archived_at in rows]


async def get_student_topic_progress(
    student_id: int,
    topic_id: int,
    db: AsyncSession,
) -> dict:
    row = await db.scalar(
        select(Progress).where(
            Progress.student_id == student_id,
            Progress.topic_id == topic_id,
        )
    )
    if row is None:
        raise ProgressServiceError(status_code=404, detail="Сессия урока не найдена")
    return serialize_progress(row)


async def snapshot_attempt(row: Progress, db: AsyncSession) -> bool:
    snapshot = json.loads(json.dumps(serialize_progress(row), default=str))
    result = await db.scalar(insert(LessonAttempt).values(
        student_id=row.student_id, topic_id=row.topic_id, attempt_number=max(1, row.attempts or 1),
        lesson_version_id=row.lesson_version_id, snapshot=snapshot,
        completed_at=row.completed_at or datetime.now(timezone.utc),
    ).on_conflict_do_nothing(index_elements=[LessonAttempt.student_id, LessonAttempt.topic_id,
                                            LessonAttempt.attempt_number]).returning(LessonAttempt.id))
    return result is not None


async def list_attempts(student_id: int, topic_id: int, db: AsyncSession) -> list[dict]:
    rows = (await db.scalars(select(LessonAttempt).where(
        LessonAttempt.student_id == student_id, LessonAttempt.topic_id == topic_id
    ).order_by(LessonAttempt.attempt_number.desc()))).all()
    return [{"id": row.id, "attempt_number": row.attempt_number, "completed_at": row.completed_at,
             "lesson_version_id": row.lesson_version_id, "snapshot": row.snapshot} for row in rows]
