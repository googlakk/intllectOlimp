from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.http_errors import raise_http_error
from services.lessons import (
    LessonServiceError,
    delete_lesson_record,
    generate_lesson_draft,
    get_lesson_by_topic,
    get_lesson_quality,
    publish_lesson,
    serialize_lesson,
    unpublish_lesson,
    update_lesson_blocks,
)

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class GenerateInput(BaseModel):
    topic_id: int
    teacher_id: int


class BlocksInput(BaseModel):
    blocks: list[dict[str, Any]]


class PublishInput(BaseModel):
    teacher_id: int
    acknowledge_warnings: bool = False


@router.post("/generate")
async def generate(payload: GenerateInput, db: AsyncSession = Depends(get_db)):
    try:
        lesson = await generate_lesson_draft(
            topic_id=payload.topic_id,
            teacher_id=payload.teacher_id,
            db=db,
        )
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.get("/{topic_id}")
async def by_topic(
    topic_id: int,
    role: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await get_lesson_by_topic(topic_id, role, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/blocks")
async def update_blocks(
    lesson_id: int,
    payload: BlocksInput,
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await update_lesson_blocks(lesson_id, payload.blocks, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.get("/{lesson_id}/quality")
async def lesson_quality(lesson_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await get_lesson_quality(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.put("/{lesson_id}/publish")
async def publish(
    lesson_id: int,
    payload: PublishInput,
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await publish_lesson(
            lesson_id=lesson_id,
            teacher_id=payload.teacher_id,
            acknowledge_warnings=payload.acknowledge_warnings,
            db=db,
        )
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/unpublish")
async def unpublish(lesson_id: int, db: AsyncSession = Depends(get_db)):
    try:
        lesson = await unpublish_lesson(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await delete_lesson_record(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
