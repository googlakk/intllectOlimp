from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.http_errors import raise_http_error
from services.progress import (
    ProgressServiceError,
    get_student_topic_progress,
    list_student_progress,
    save_progress_record,
    serialize_progress,
)

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
    objective_evidence: dict | None = None
    objective_mastery: dict | None = None
    mastery_status: str | None = Field(default=None, pattern="^(not_assessed|in_progress|mastered|needs_practice)$")


@router.post("")
async def save_progress(payload: ProgressInput, db: AsyncSession = Depends(get_db)):
    try:
        row = await save_progress_record(payload, db)
    except ProgressServiceError as exc:
        raise_http_error(exc)
    return serialize_progress(row)


@router.get("/{student_id}")
async def by_student(student_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await list_student_progress(student_id, db)
    except ProgressServiceError as exc:
        raise_http_error(exc)


@router.get("/{student_id}/{topic_id}")
async def by_student_topic(
    student_id: int, topic_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_student_topic_progress(student_id, topic_id, db)
    except ProgressServiceError as exc:
        raise_http_error(exc)
