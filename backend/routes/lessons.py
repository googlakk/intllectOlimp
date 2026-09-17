from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.generator import MODEL, classify_subject, generate_lesson
from database import get_db
from models import GeneratedLesson, Section, Subject, Teacher, Topic

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class GenerateInput(BaseModel):
    topic_id: int
    teacher_id: int


class BlocksInput(BaseModel):
    blocks: list[dict[str, Any]]


class PublishInput(BaseModel):
    teacher_id: int


def serialize_lesson(lesson: GeneratedLesson) -> dict:
    return {
        "id": lesson.id,
        "topic_id": lesson.topic_id,
        "blocks": lesson.blocks or [],
        "lesson_metadata": lesson.lesson_metadata or {},
        "status": lesson.status,
        "generated_at": lesson.generated_at,
        "published_at": lesson.published_at,
        "published_by": lesson.published_by,
        "model_used": lesson.model_used,
    }


async def get_lesson_or_404(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await db.get(GeneratedLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


@router.post("/generate")
async def generate(payload: GenerateInput, db: AsyncSession = Depends(get_db)):
    if await db.get(Teacher, payload.teacher_id) is None:
        raise HTTPException(status_code=404, detail="Преподаватель не найден")

    row = (
        await db.execute(
            select(Topic, Section, Subject)
            .join(Section, Topic.section_id == Section.id)
            .join(Subject, Section.subject_id == Subject.id)
            .where(Topic.id == payload.topic_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    topic, _section, subject = row

    try:
        blocks = await generate_lesson(
            topic_name=topic.name,
            subject_name=subject.name,
            learning_objectives=topic.learning_objectives,
            skills=topic.skills,
            resources=topic.resources,
            grade=subject.grade,
            lesson_type=topic.lesson_type,
            content_language=subject.instruction_language,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось сгенерировать урок: {exc}") from exc

    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    if lesson is None:
        lesson = GeneratedLesson(topic_id=topic.id)
        db.add(lesson)
    lesson.blocks = blocks
    profile = classify_subject(subject.name)
    lesson.lesson_metadata = {
        "subject_name": subject.name,
        "subject_grade": subject.grade,
        "content_language": subject.instruction_language,
        "subject_family": profile["family"],
        "subject_family_label": profile["family_label"],
        "lesson_archetype": profile["archetype"],
        "teacher_review_required": profile["teacher_review_required"],
        "topic_name": topic.name,
        "lesson_type": topic.lesson_type,
        "learning_objectives": topic.learning_objectives,
        "skills": topic.skills or [],
        "teacher_id": payload.teacher_id,
    }
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    lesson.generated_at = datetime.now(timezone.utc)
    lesson.model_used = MODEL
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.get("/{topic_id}")
async def by_topic(
    topic_id: int,
    role: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    statement = select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id)
    if role == "student":
        statement = statement.where(GeneratedLesson.status == "published")
    lesson = await db.scalar(statement)
    if lesson is None:
        detail = "Опубликованный урок пока не готов" if role == "student" else "Урок не найден"
        raise HTTPException(status_code=404, detail=detail)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/blocks")
async def update_blocks(
    lesson_id: int,
    payload: BlocksInput,
    db: AsyncSession = Depends(get_db),
):
    lesson = await get_lesson_or_404(lesson_id, db)
    lesson.blocks = payload.blocks
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/publish")
async def publish(
    lesson_id: int,
    payload: PublishInput,
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Teacher, payload.teacher_id) is None:
        raise HTTPException(status_code=404, detail="Преподаватель не найден")
    lesson = await get_lesson_or_404(lesson_id, db)
    lesson.status = "published"
    lesson.published_at = datetime.now(timezone.utc)
    lesson.published_by = payload.teacher_id
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/unpublish")
async def unpublish(lesson_id: int, db: AsyncSession = Depends(get_db)):
    lesson = await get_lesson_or_404(lesson_id, db)
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    lesson = await get_lesson_or_404(lesson_id, db)
    await db.delete(lesson)
    await db.commit()
    return {"message": "Урок удалён"}