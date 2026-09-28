"""Scope teacher content operations to explicitly assigned subject/grade courses."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Classroom, ClassroomTeacher, GeneratedLesson, LessonVersion, Section, Subject, Topic
from services.auth import AuthPrincipal, AuthServiceError
from services.teacher_assignments import teacher_subject_ids


async def teacher_max_grade(user: AuthPrincipal, db: AsyncSession) -> int | None:
    if user.role == "admin":
        return None
    if user.role != "teacher" or user.teacher_id is None:
        raise AuthServiceError(status_code=403, detail="Доступ учителя не настроен.")
    grade = await db.scalar(
        select(func.max(Classroom.grade))
        .join(ClassroomTeacher, ClassroomTeacher.classroom_id == Classroom.id)
        .where(
            ClassroomTeacher.teacher_id == user.teacher_id,
            Classroom.status == "active",
        )
    )
    if grade is None:
        raise AuthServiceError(status_code=403, detail="Учителю пока не назначен ни один класс.")
    return int(grade)


async def require_grade_management(user: AuthPrincipal, grade: int, db: AsyncSession) -> None:
    if user.role != "admin":
        raise AuthServiceError(status_code=403, detail="Новые программы и КТП добавляет администратор.")


async def require_subject_management(user: AuthPrincipal, subject_id: int, db: AsyncSession) -> Subject:
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise AuthServiceError(status_code=404, detail="Предмет не найден.")
    if user.role != "admin" and subject_id not in await teacher_subject_ids(user, db):
        raise AuthServiceError(status_code=404, detail="Предмет не назначен этому учителю.")
    return subject


async def require_section_management(user: AuthPrincipal, section_id: int, db: AsyncSession) -> Section:
    section = await db.get(Section, section_id)
    if section is None:
        raise AuthServiceError(status_code=404, detail="Раздел не найден.")
    await require_subject_management(user, section.subject_id, db)
    return section


async def require_topic_management(user: AuthPrincipal, topic_id: int, db: AsyncSession) -> Topic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise AuthServiceError(status_code=404, detail="Тема не найдена.")
    await require_section_management(user, topic.section_id, db)
    return topic


async def require_lesson_management(user: AuthPrincipal, lesson_id: int, db: AsyncSession) -> GeneratedLesson:
    lesson = await db.get(GeneratedLesson, lesson_id)
    if lesson is None:
        raise AuthServiceError(status_code=404, detail="Урок не найден.")
    await require_topic_management(user, lesson.topic_id, db)
    return lesson


async def require_lesson_version_management(
    user: AuthPrincipal,
    lesson_version_id: int,
    db: AsyncSession,
) -> LessonVersion:
    version = await db.get(LessonVersion, lesson_version_id)
    if version is None:
        raise AuthServiceError(status_code=404, detail="Версия урока не найдена.")
    await require_lesson_management(user, version.lesson_id, db)
    return version
