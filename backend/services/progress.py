from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import GeneratedLesson, Progress, Student, Topic
from objectives import calculate_objective_mastery, quality_report


class ProgressServiceError(ApplicationError):
    pass


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
    if await db.get(Student, payload.student_id) is None:
        raise ProgressServiceError(status_code=404, detail="Ученик не найден")
    topic = await db.get(Topic, payload.topic_id)
    if topic is None:
        raise ProgressServiceError(status_code=404, detail="Тема не найдена")
    if payload.status == "in_progress" and payload.current_step > payload.max_opened_step:
        raise ProgressServiceError(status_code=422, detail="Текущий шаг ещё не открыт")

    now = datetime.now(timezone.utc)
    objective_mastery = payload.objective_mastery
    objective_evidence = payload.objective_evidence
    mastery_status = payload.mastery_status
    lesson = await db.scalar(
        select(GeneratedLesson).where(GeneratedLesson.topic_id == payload.topic_id)
    )
    if lesson is not None:
        derived = derive_canonical_mastery(
            lesson.blocks or [],
            topic.learning_objectives,
            payload.answers,
            payload.attempts_by_step,
            lesson_completed=payload.status == "completed",
        )
        if derived is not None:
            objective_mastery, objective_evidence, mastery_status = derived
    mastery_status = derive_mastery_status(objective_mastery, mastery_status)

    insert_mastery_status = mastery_status or "not_assessed"
    insert_objective_evidence = objective_evidence or {}
    insert_objective_mastery = objective_mastery or {}
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
            attempts_by_step=payload.attempts_by_step,
            elapsed_time_sec=payload.elapsed_time_sec,
            objective_evidence=insert_objective_evidence,
            objective_mastery=insert_objective_mastery,
            mastery_status=insert_mastery_status,
        )
        .on_conflict_do_update(
            index_elements=[Progress.student_id, Progress.topic_id],
            set_={
                "status": status_update,
                "score": score_update,
                "mastery_level": mastery_update,
                "time_spent_sec": payload.time_spent_sec,
                "completed_at": completed_at_update,
                "current_step": payload.current_step,
                "max_opened_step": payload.max_opened_step,
                "answers": payload.answers,
                "attempts_by_step": payload.attempts_by_step,
                "elapsed_time_sec": payload.elapsed_time_sec,
                "objective_evidence": (
                    Progress.objective_evidence
                    if objective_evidence is None
                    else objective_evidence
                ),
                "objective_mastery": (
                    Progress.objective_mastery
                    if objective_mastery is None
                    else objective_mastery
                ),
                "mastery_status": (
                    Progress.mastery_status
                    if mastery_status is None
                    else mastery_status
                ),
                # Re-saving a completed session is idempotent. An attempt is
                # counted only when an in-progress row first becomes complete.
                "attempts": case(
                    (Progress.status == "completed", Progress.attempts),
                    else_=Progress.attempts + (1 if payload.status == "completed" else 0),
                ),
            },
        )
        .returning(Progress)
    )
    row = await db.scalar(statement)
    await db.commit()
    if row is None:
        raise ProgressServiceError(status_code=500, detail="Не удалось сохранить прогресс")
    return row


def serialize_progress(row: Progress) -> dict:
    return {column.name: getattr(row, column.name) for column in Progress.__table__.columns}


async def list_student_progress(student_id: int, db: AsyncSession) -> list[dict]:
    rows = (
        await db.scalars(select(Progress).where(Progress.student_id == student_id))
    ).all()
    return [serialize_progress(row) for row in rows]


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
