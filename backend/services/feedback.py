"""Отзывы учеников об уроке: приём в конце урока и список для администратора."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from feedback.models import LessonFeedback
from models import GeneratedLesson, Section, Student, Subject, Topic
from services.auth import AuthPrincipal

logger = logging.getLogger(__name__)

COMMENT_LIMIT = 2000
LIST_LIMIT = 200


def clean_feedback(rating: int | None, had_errors: bool | None, comment: str | None) -> dict[str, Any] | None:
    """Проверенные поля отзыва; None — ученик ничего не заполнил (отзыв необязателен)."""
    if rating is not None and not 1 <= rating <= 5:
        raise ApplicationError(422, "Оценка — от 1 до 5.")
    text = (comment or "").strip()[:COMMENT_LIMIT] or None
    if rating is None and had_errors is None and text is None:
        return None
    return {"rating": rating, "had_errors": had_errors, "comment": text}


async def submit_lesson_feedback(
    user: AuthPrincipal, db: AsyncSession, *, topic_id: int, rating: int | None, had_errors: bool | None, comment: str | None,
) -> dict[str, Any]:
    if user.student_id is None:
        raise ApplicationError(403, "Отзыв об уроке оставляет ученик.")
    fields = clean_feedback(rating, had_errors, comment)
    if fields is None:
        return {"saved": False}
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic_id))
    if lesson is None:
        raise ApplicationError(404, "Урок не найден.")
    db.add(LessonFeedback(
        organization_id=user.organization_id,
        student_id=user.student_id,
        topic_id=topic_id,
        lesson_version_id=lesson.published_version_id or lesson.active_version_id,
        **fields,
    ))
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        # Таблица ещё не создана миграцией — урок ученика от этого не ломается.
        logger.warning("Lesson feedback unavailable: %s", exc.__class__.__name__)
        await db.rollback()
        raise ApplicationError(503, "Отзывы пока не включены.") from exc
    return {"saved": True}


def serialize_feedback(row: Any) -> dict[str, Any]:
    feedback = row.LessonFeedback
    return {
        "id": feedback.id,
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "rating": feedback.rating,
        "had_errors": feedback.had_errors,
        "comment": feedback.comment,
        "student_id": feedback.student_id,
        "student_name": row.student_name,
        "topic_id": feedback.topic_id,
        "topic_name": row.topic_name,
        "subject_id": row.subject_id,
        "subject_name": row.subject_name,
        "grade": row.grade,
        "lesson_version_id": feedback.lesson_version_id,
    }


async def list_lesson_feedback(
    user: AuthPrincipal, db: AsyncSession, *, only_errors: bool = False, subject_id: int | None = None,
) -> dict[str, Any]:
    """Отзывы организации: сначала свежие, со сводкой (средняя оценка, сколько сообщили об ошибках)."""
    scope = LessonFeedback.organization_id == user.organization_id
    statement = (
        select(
            LessonFeedback,
            Student.name.label("student_name"),
            Topic.name.label("topic_name"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Subject.grade.label("grade"),
        )
        .join(Student, Student.id == LessonFeedback.student_id)
        .join(Topic, Topic.id == LessonFeedback.topic_id)
        .join(Section, Section.id == Topic.section_id)
        .join(Subject, Subject.id == Section.subject_id)
        .where(scope)
        .order_by(LessonFeedback.created_at.desc(), LessonFeedback.id.desc())
        .limit(LIST_LIMIT)
    )
    if only_errors:
        statement = statement.where(LessonFeedback.had_errors.is_(True))
    if subject_id is not None:
        statement = statement.where(Subject.id == subject_id)
    summary_statement = select(
        func.count(LessonFeedback.id),
        func.avg(LessonFeedback.rating),
        func.count(LessonFeedback.id).filter(LessonFeedback.had_errors.is_(True)),
    ).where(scope)
    try:
        rows = (await db.execute(statement)).all()
        total, average, with_errors = (await db.execute(summary_statement)).one()
    except SQLAlchemyError as exc:
        logger.warning("Lesson feedback list unavailable: %s", exc.__class__.__name__)
        await db.rollback()
        return {"available": False, "summary": {"total": 0, "average_rating": None, "with_errors": 0}, "items": []}
    return {
        "available": True,
        "summary": {
            "total": int(total or 0),
            "average_rating": round(float(average), 1) if average is not None else None,
            "with_errors": int(with_errors or 0),
        },
        "items": [serialize_feedback(row) for row in rows],
    }
