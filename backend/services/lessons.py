from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import GeneratedLesson, Section, Subject, Teacher, Topic
from objectives import quality_report

LessonGenerator = Callable[..., Awaitable[list[dict[str, Any]]]]


class LessonServiceError(ApplicationError):
    pass


async def get_lesson_or_error(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await db.get(GeneratedLesson, lesson_id)
    if lesson is None:
        raise LessonServiceError(status_code=404, detail="Урок не найден")
    return lesson


def serialize_lesson(lesson: GeneratedLesson) -> dict[str, Any]:
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


def lesson_needs_quality_refresh(lesson: GeneratedLesson) -> bool:
    metadata = lesson.lesson_metadata or {}
    return not isinstance(metadata.get("objectives"), list) or not isinstance(
        metadata.get("quality_report"), dict
    )


async def get_lesson_by_topic(
    topic_id: int,
    role: str | None,
    db: AsyncSession,
) -> GeneratedLesson:
    statement = select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id)
    if role == "student":
        statement = statement.where(GeneratedLesson.status == "published")
    lesson = await db.scalar(statement)
    if lesson is None:
        detail = "Опубликованный урок пока не готов" if role == "student" else "Урок не найден"
        raise LessonServiceError(status_code=404, detail=detail)
    if lesson_needs_quality_refresh(lesson):
        await refresh_quality_contract(lesson, db)
    return lesson


async def refresh_quality_contract(lesson: GeneratedLesson, db: AsyncSession) -> dict[str, Any]:
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    report = quality_report(lesson.blocks or [], topic.learning_objectives)
    metadata = dict(lesson.lesson_metadata or {})
    metadata["objectives"] = report["objectives"]
    metadata["quality_report"] = report["quality_report"]
    lesson.lesson_metadata = metadata
    lesson.blocks = report["normalized_blocks"]
    return report


async def update_lesson_blocks(
    lesson_id: int,
    blocks: list[dict[str, Any]],
    db: AsyncSession,
) -> GeneratedLesson:
    lesson = await get_lesson_or_error(lesson_id, db)
    quality = await refresh_quality_contract_for_blocks(lesson, blocks, db)
    metadata = dict(lesson.lesson_metadata or {})
    metadata["objectives"] = quality["objectives"]
    metadata["quality_report"] = quality["quality_report"]
    lesson.lesson_metadata = metadata
    lesson.blocks = quality["normalized_blocks"]
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def refresh_quality_contract_for_blocks(
    lesson: GeneratedLesson,
    blocks: list[dict[str, Any]],
    db: AsyncSession,
) -> dict[str, Any]:
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    return quality_report(blocks, topic.learning_objectives)


async def get_lesson_quality(lesson_id: int, db: AsyncSession) -> dict[str, Any]:
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")
    return quality_report(lesson.blocks or [], topic.learning_objectives)


async def unpublish_lesson(lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await get_lesson_or_error(lesson_id, db)
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def delete_lesson_record(lesson_id: int, db: AsyncSession) -> dict[str, str]:
    lesson = await get_lesson_or_error(lesson_id, db)
    await db.delete(lesson)
    await db.commit()
    return {"message": "Урок удалён"}


async def generate_lesson_draft(
    topic_id: int,
    teacher_id: int,
    db: AsyncSession,
    lesson_generator: LessonGenerator | None = None,
) -> GeneratedLesson:
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(status_code=404, detail="Преподаватель не найден")

    row = (
        await db.execute(
            select(Topic, Section, Subject)
            .join(Section, Topic.section_id == Section.id)
            .join(Subject, Section.subject_id == Subject.id)
            .where(Topic.id == topic_id)
        )
    ).first()
    if row is None:
        raise LessonServiceError(status_code=404, detail="Тема не найдена")
    topic, _section, subject = row

    from ai.generator import MODEL, classify_subject, generate_lesson, select_archetype

    generator = lesson_generator or generate_lesson
    try:
        blocks = await generator(
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
        raise LessonServiceError(
            status_code=502,
            detail=f"Не удалось сгенерировать урок: {exc}",
        ) from exc

    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    if lesson is None:
        lesson = GeneratedLesson(topic_id=topic.id)
        db.add(lesson)

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
        "teacher_id": teacher_id,
    }
    lesson.status = "draft"
    lesson.published_at = None
    lesson.published_by = None
    lesson.generated_at = datetime.now(timezone.utc)
    lesson.model_used = MODEL
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def publish_lesson(
    lesson_id: int,
    teacher_id: int,
    acknowledge_warnings: bool,
    db: AsyncSession,
) -> GeneratedLesson:
    if await db.get(Teacher, teacher_id) is None:
        raise LessonServiceError(status_code=404, detail="Преподаватель не найден")
    lesson = await get_lesson_or_error(lesson_id, db)
    topic = await db.get(Topic, lesson.topic_id)
    if topic is None:
        raise LessonServiceError(status_code=404, detail="Тема урока не найдена")

    quality = quality_report(lesson.blocks or [], topic.learning_objectives)
    if not quality["quality_report"]["publishable"]:
        raise LessonServiceError(
            status_code=422,
            detail={
                "message": "Урок нельзя опубликовать: исправьте покрытие целей и ошибки ответов",
                "quality_report": quality,
            },
        )

    warnings = quality["quality_report"]["warnings"]
    if warnings and not acknowledge_warnings:
        raise LessonServiceError(
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
        "teacher_id": teacher_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_warning_codes": [
            item.get("code") for item in warnings if isinstance(item, dict)
        ],
    }
    lesson.blocks = quality["normalized_blocks"]
    lesson.lesson_metadata = metadata
    lesson.status = "published"
    lesson.published_at = datetime.now(timezone.utc)
    lesson.published_by = teacher_id
    await db.commit()
    await db.refresh(lesson)
    return lesson
