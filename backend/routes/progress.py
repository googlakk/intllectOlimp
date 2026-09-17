from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Progress, Student, Topic

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ProgressInput(BaseModel):
    student_id: int
    topic_id: int
    score: int = Field(ge=0, le=100)
    mastery_level: str = Field(min_length=1)
    time_spent_sec: int = Field(default=0, ge=0)


def serialize_progress(row: Progress) -> dict:
    return {column.name: getattr(row, column.name) for column in Progress.__table__.columns}


@router.post("")
async def save_progress(payload: ProgressInput, db: AsyncSession = Depends(get_db)):
    if await db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    if await db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")

    now = datetime.now(timezone.utc)
    statement = (
        insert(Progress)
        .values(
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            status="completed",
            score=payload.score,
            mastery_level=payload.mastery_level,
            time_spent_sec=payload.time_spent_sec,
            started_at=now,
            completed_at=now,
            attempts=1,
        )
        .on_conflict_do_update(
            index_elements=[Progress.student_id, Progress.topic_id],
            set_={
                "status": "completed",
                "score": payload.score,
                "mastery_level": payload.mastery_level,
                "time_spent_sec": payload.time_spent_sec,
                "completed_at": now,
                "attempts": Progress.attempts + 1,
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