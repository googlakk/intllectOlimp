"""Authorization checks for lesson media served outside JSON API responses."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import GeneratedLesson, GenerationJob, LessonVersion
from services.auth import AuthPrincipal, AuthServiceError
from services.educator_access import require_lesson_version_management
from services.lessons import get_lesson_by_topic


async def require_lesson_version_media_access(
    user: AuthPrincipal,
    lesson_version_id: int,
    db: AsyncSession,
) -> None:
    if user.role == "admin":
        return
    if user.role == "teacher":
        await require_lesson_version_management(user, lesson_version_id, db)
        return
    lesson = await db.scalar(
        select(GeneratedLesson)
        .join(LessonVersion, LessonVersion.lesson_id == GeneratedLesson.id)
        .where(LessonVersion.id == lesson_version_id)
    )
    if lesson is None or user.student_id is None:
        raise AuthServiceError(status_code=404, detail="Медиа урока не найдено.")
    available_lesson = await get_lesson_by_topic(lesson.topic_id, "student", db, student_id=user.student_id)
    selected_version_id = getattr(available_lesson, "_served_version_id", available_lesson.published_version_id or available_lesson.active_version_id)
    if selected_version_id != lesson_version_id:
        raise AuthServiceError(status_code=404, detail="Медиа не относится к версии вашей попытки.")


async def require_generation_job_media_access(
    user: AuthPrincipal,
    external_job_id: str,
    db: AsyncSession,
    *,
    provider: str | None = None,
) -> GenerationJob:
    statement = select(GenerationJob).where(GenerationJob.external_job_id == external_job_id)
    if provider is not None:
        statement = statement.where(GenerationJob.provider == provider)
    job = await db.scalar(statement)
    if job is None:
        raise AuthServiceError(status_code=404, detail="Видео урока не найдено.")
    await require_lesson_version_media_access(user, job.lesson_version_id, db)
    return job
