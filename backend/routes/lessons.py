from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.generator import MODEL, classify_subject, generate_lesson, select_archetype
from database import get_db
from deps import current_teacher, current_user, require_staff
from curriculum import MAX_LESSON_PARTS, lesson_parts
from models import GeneratedLesson, Section, Student, Subject, Teacher, Topic, TopicDelivery, User
from objectives import quality_report

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class GenerateInput(BaseModel):
    topic_id: int
    # Batch «generate quarter» sets this so existing drafts/published lessons are never overwritten.
    skip_existing: bool = False


class BlocksInput(BaseModel):
    blocks: list[dict[str, Any]]


class PublishInput(BaseModel):
    acknowledge_warnings: bool = False


def block_part(block: dict[str, Any]) -> int:
    content = block.get("content") if isinstance(block, dict) else None
    try:
        return max(1, int((content or {}).get("lesson_part") or 1))
    except (TypeError, ValueError):
        return 1


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


async def lesson_topic(topic: Topic, db: AsyncSession) -> Topic:
    """The row that owns the lesson for a (possibly repeated) KTP row."""
    if topic.lesson_topic_id is None:
        return topic
    return await db.get(Topic, topic.lesson_topic_id) or topic


async def group_rows(primary: Topic, db: AsyncSession) -> list[Topic]:
    rows = await db.scalars(
        select(Topic).where(or_(Topic.id == primary.id, Topic.lesson_topic_id == primary.id))
    )
    return list(rows)


def previous_topics_query(primary: Topic, section: Section, limit: int = 3) -> Any:
    return (
        select(Topic.name, Topic.learning_objectives)
        .join(Section, Topic.section_id == Section.id)
        .where(
            Section.subject_id == section.subject_id,
            Topic.lesson_topic_id.is_(None),
            Topic.sort_number < (primary.sort_number or 0),
        )
        .order_by(Topic.sort_number.desc())
        .limit(limit)
    )


async def unlocked_parts_for(user: User, primary: Topic, total_parts: int, db: AsyncSession) -> int:
    """Lesson parts open to a student: one per «Проведено» mark of the topic in the student's class."""
    if user.role != "student":
        return total_parts
    student = await db.scalar(select(Student).where(Student.user_id == user.id))
    if student is None or student.class_id is None:
        return total_parts  # no class assigned yet: nothing to gate by
    row_ids = [row.id for row in await group_rows(primary, db)]
    delivered = await db.scalar(
        select(func.count(TopicDelivery.id)).where(
            TopicDelivery.class_id == student.class_id, TopicDelivery.topic_id.in_(row_ids)
        )
    )
    return max(1, min(total_parts, delivered or 0))


async def get_lesson_or_404(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await db.get(GeneratedLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


@router.post("/generate")
async def generate(
    payload: GenerateInput,
    teacher: Teacher = Depends(current_teacher),
    db: AsyncSession = Depends(get_db),
):

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
    topic, section, subject = row
    topic = await lesson_topic(topic, db)
    existing = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    if existing is not None and payload.skip_existing:
        raise HTTPException(status_code=409, detail="У темы уже есть урок — пропущено")
    rows = await group_rows(topic, db)
    total_hours = max(1, sum(max(row.hours or 1, 1) for row in rows))
    previous = [
        {"name": name, "learning_objectives": objectives}
        for name, objectives in (await db.execute(previous_topics_query(topic, section))).all()
    ]

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
            section_name=section.name,
            quarter=topic.quarter,
            sort_number=topic.sort_number,
            total_hours=total_hours,
            previous_topics=previous,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось сгенерировать урок: {exc}") from exc

    lesson = existing
    if lesson is None:
        lesson = GeneratedLesson(topic_id=topic.id)
        db.add(lesson)
    # Parts must be contiguous so unlocking a part only appends blocks: saved progress is index-based.
    blocks = sorted(blocks, key=block_part)
    quality = quality_report(blocks, topic.learning_objectives)
    lesson.blocks = quality["normalized_blocks"]
    profile = classify_subject(subject.name)
    archetype = select_archetype(
        str(profile["family"]),
        topic.name,
        topic.lesson_type,
        topic.learning_objectives,
    )
    lesson.lesson_metadata = {
        "subject_name": subject.name,
        "subject_grade": subject.grade,
        "content_language": subject.instruction_language,
        "subject_family": profile["family"],
        "subject_family_label": profile["family_label"],
        "lesson_archetype": archetype,
        "teacher_review_required": profile["teacher_review_required"],
        "topic_name": topic.name,
        "lesson_type": topic.lesson_type,
        "learning_objectives": topic.learning_objectives,
        "objectives": quality["objectives"],
        "quality_report": quality["quality_report"],
        "skills": topic.skills or [],
        "teacher_id": teacher.id,
        "section_name": section.name,
        "quarter": topic.quarter,
        "sort_number": topic.sort_number,
        "total_hours": total_hours,
        "ktp_rows": [row.id for row in rows],
        "lesson_parts": lesson_parts(total_hours),
        "previous_topics": [item["name"] for item in previous],
    }
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    lesson.generated_at = datetime.now(timezone.utc)
    lesson.model_used = MODEL
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.get("/quarter-plan")
async def quarter_plan(
    subject_id: int,
    quarter: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_staff),
):
    """Learning topics of one quarter in KTP order, with whether a lesson already exists."""
    rows = (
        await db.execute(
            select(Topic.id, Topic.name, Topic.sort_number, GeneratedLesson.status)
            .join(Section, Topic.section_id == Section.id)
            .outerjoin(GeneratedLesson, GeneratedLesson.topic_id == Topic.id)
            .where(Section.subject_id == subject_id, Topic.quarter == quarter, Topic.lesson_topic_id.is_(None))
            .order_by(Topic.sort_number, Topic.id)
        )
    ).all()
    return [
        {"topic_id": r.id, "name": r.name, "sort_number": r.sort_number, "lesson_status": r.status}
        for r in rows
    ]


@router.get("/{topic_id}")
async def by_topic(
    topic_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    role = user.role
    requested = await db.get(Topic, topic_id)
    primary = await lesson_topic(requested, db) if requested is not None else None
    statement = select(GeneratedLesson).where(GeneratedLesson.topic_id == (primary.id if primary else topic_id))
    if role == "student":
        statement = statement.where(GeneratedLesson.status == "published")
    lesson = await db.scalar(statement)
    if lesson is None:
        detail = "Опубликованный урок пока не готов" if role == "student" else "Урок не найден"
        raise HTTPException(status_code=404, detail=detail)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is not None:
        metadata = dict(lesson.lesson_metadata or {})
        report = quality_report(lesson.blocks or [], topic.learning_objectives)
        metadata["objectives"] = report["objectives"]
        metadata["quality_report"] = report["quality_report"]
        # Legacy lessons remain drafts/review-required, but consumers receive
        # the same canonical contract without rewriting historical rows.
        lesson.lesson_metadata = metadata
        lesson.blocks = report["normalized_blocks"]
    data = serialize_lesson(lesson)
    parts = sorted({block_part(block) for block in data["blocks"]})
    total_parts = min(MAX_LESSON_PARTS, max(parts)) if parts else 1
    data["total_parts"] = total_parts
    data["unlocked_parts"] = await unlocked_parts_for(user, topic or primary, total_parts, db) if (topic or primary) else total_parts
    if role == "student" and len(parts) > 1:
        # Locked parts are not sent at all, so answers can't be read ahead.
        data["blocks"] = [
            block for block in data["blocks"] if block_part(block) <= data["unlocked_parts"]
        ]
    return data


@router.put("/{lesson_id}/blocks")
async def update_blocks(
    lesson_id: int,
    payload: BlocksInput,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_staff),
):
    lesson = await get_lesson_or_404(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема урока не найдена")
    quality = quality_report(payload.blocks, topic.learning_objectives)
    lesson.blocks = quality["normalized_blocks"]
    metadata = dict(lesson.lesson_metadata or {})
    metadata["objectives"] = quality["objectives"]
    metadata["quality_report"] = quality["quality_report"]
    lesson.lesson_metadata = metadata
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.get("/{lesson_id}/quality")
async def lesson_quality(
    lesson_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_staff)
):
    lesson = await get_lesson_or_404(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема урока не найдена")
    return quality_report(lesson.blocks or [], topic.learning_objectives)


@router.put("/{lesson_id}/publish")
async def publish(
    lesson_id: int,
    payload: PublishInput,
    db: AsyncSession = Depends(get_db),
    teacher: Teacher = Depends(current_teacher),
):
    lesson = await get_lesson_or_404(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема урока не найдена")
    quality = quality_report(lesson.blocks or [], topic.learning_objectives)
    if not quality["quality_report"]["publishable"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Урок нельзя опубликовать: исправьте покрытие целей и ошибки ответов",
                "quality_report": quality,
            },
        )
    warnings = quality["quality_report"]["warnings"]
    if warnings and not payload.acknowledge_warnings:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Подтвердите некритические предупреждения перед публикацией",
                "warnings": warnings,
            },
        )
    metadata = dict(lesson.lesson_metadata or {})
    metadata["objectives"] = quality["objectives"]
    metadata["quality_report"] = quality["quality_report"]
    metadata["quality_review"] = {
        "teacher_id": teacher.id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_warning_codes": [
            item.get("code") for item in warnings if isinstance(item, dict)
        ],
    }
    lesson.blocks = quality["normalized_blocks"]
    lesson.lesson_metadata = metadata
    lesson.status = "published"
    lesson.published_at = datetime.now(timezone.utc)
    lesson.published_by = teacher.id
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/unpublish")
async def unpublish(
    lesson_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_staff)
):
    lesson = await get_lesson_or_404(lesson_id, db)
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    await db.commit()
    await db.refresh(lesson)
    return serialize_lesson(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson(
    lesson_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_staff)
):
    lesson = await get_lesson_or_404(lesson_id, db)
    await db.delete(lesson)
    await db.commit()
    return {"message": "Урок удалён"}