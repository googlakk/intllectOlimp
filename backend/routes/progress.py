from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Progress, Student, Topic

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ProgressInput(BaseModel):
    student_id: int
    topic_id: int
    score: int | None = Field(default=None, ge=0, le=100)
    mastery_level: str | None = Field(default=None, min_length=1)
    time_spent_sec: int = Field(default=0, ge=0)
    current_step: int = Field(default=0, ge=0)
    max_opened_step: int = Field(default=0, ge=0)
    answers: dict = Field(default_factory=dict)
    attempts_by_step: dict = Field(default_factory=dict)
    elapsed_time_sec: int = Field(default=0, ge=0)
    status: str = Field(default="completed", pattern="^(in_progress|completed)$")


def serialize_progress(row: Progress) -> dict:
    return {column.name: getattr(row, column.name) for column in Progress.__table__.columns}


@router.post("")
async def save_progress(payload: ProgressInput, db: AsyncSession = Depends(get_db)):
    if await db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    if await db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    if payload.status == "in_progress" and payload.current_step > payload.max_opened_step:
        raise HTTPException(status_code=422, detail="Текущий шаг ещё не открыт")

    now = datetime.now(timezone.utc)
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
        raise HTTPException(status_code=500, detail="Не удалось сохранить прогресс")
    return serialize_progress(row)


@router.get("/{student_id}")
async def by_student(student_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Progress).where(Progress.student_id == student_id))).all()
    return [serialize_progress(row) for row in rows]


@router.get("/{student_id}/{topic_id}")
async def by_student_topic(
    student_id: int, topic_id: int, db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(
        select(Progress).where(
            Progress.student_id == student_id, Progress.topic_id == topic_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Сессия урока не найдена")
    return serialize_progress(row)