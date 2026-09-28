from typing import Any
from copy import deepcopy
from time import monotonic

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import GeneratedLesson, Section, Subject, Topic
from services.grade_access import (
    get_student_for_access,
    require_section_access,
    require_subject_access,
)

SUBJECT_OUTLINE_CACHE_TTL_SEC = 120
_subject_outline_cache: dict[int, tuple[float, list[dict[str, Any]]]] = {}


def clear_subject_outline_cache(subject_id: int | None = None) -> None:
    if subject_id is None:
        _subject_outline_cache.clear()
    else:
        _subject_outline_cache.pop(subject_id, None)


def cached_subject_outline(subject_id: int) -> list[dict[str, Any]] | None:
    cached = _subject_outline_cache.get(subject_id)
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= monotonic():
        _subject_outline_cache.pop(subject_id, None)
        return None
    return deepcopy(payload)


def remember_subject_outline(subject_id: int, payload: list[dict[str, Any]]) -> None:
    _subject_outline_cache[subject_id] = (
        monotonic() + SUBJECT_OUTLINE_CACHE_TTL_SEC,
        deepcopy(payload),
    )


async def clear_subject_outline_cache_for_topic(topic_id: int | None, db: AsyncSession) -> None:
    if topic_id is None:
        return
    subject_id = await db.scalar(
        select(Section.subject_id)
        .join(Topic, Topic.section_id == Section.id)
        .where(Topic.id == topic_id)
    )
    if isinstance(subject_id, int):
        clear_subject_outline_cache(subject_id)


def serialize_model(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def serialize_subject(row: Subject) -> dict[str, Any]:
    return {**serialize_model(row), "progress": 0}


async def list_subjects(
    db: AsyncSession,
    student_id: int | None = None,
    subject_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    statement = select(Subject)
    if subject_ids is not None:
        statement = statement.where(Subject.id.in_(subject_ids))
    if student_id is not None:
        student = await get_student_for_access(student_id, db)
        statement = statement.where(Subject.grade == student.grade)
    rows = (await db.scalars(statement.order_by(Subject.grade, Subject.name))).all()
    return [serialize_subject(row) for row in rows]


async def list_sections(
    subject_id: int,
    db: AsyncSession,
    student_id: int | None = None,
) -> list[dict[str, Any]]:
    if student_id is not None:
        await require_subject_access(student_id, subject_id, db)
    rows = (
        await db.scalars(
            select(Section)
            .where(Section.subject_id == subject_id)
            .order_by(Section.sort_order)
        )
    ).all()
    return [serialize_model(row) for row in rows]


def serialize_topic(row: Topic, lesson_id: int | None = None, lesson_status: str | None = None) -> dict[str, Any]:
    payload = serialize_model(row)
    payload["covered_topic_ids"] = payload.get("covered_topic_ids") or []
    payload["review_required"] = bool(payload.get("review_required"))
    payload["lesson_id"] = lesson_id
    payload["lesson_status"] = lesson_status
    return payload


async def list_topics(
    section_id: int,
    db: AsyncSession,
    student_id: int | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    if student_id is not None:
        await require_section_access(student_id, section_id, db)
    rows = (
        await db.scalars(
            select(Topic)
            .where(Topic.section_id == section_id, *([] if include_archived and student_id is None else [Topic.archived_at.is_(None)]))
            .order_by(Topic.sort_order, Topic.id)
        )
    ).all()
    return [serialize_model(row) for row in rows]


async def list_subject_outline(
    subject_id: int,
    db: AsyncSession,
    student_id: int | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    if student_id is not None:
        await require_subject_access(student_id, subject_id, db)
    include_archived = include_archived and student_id is None
    cached = None if include_archived else cached_subject_outline(subject_id)
    if cached is not None:
        return cached
    rows = (
        await db.execute(
            select(Section, Topic, GeneratedLesson.id, GeneratedLesson.status)
            .outerjoin(Topic, and_(Topic.section_id == Section.id, *([] if include_archived else [Topic.archived_at.is_(None)])))
            .outerjoin(GeneratedLesson, GeneratedLesson.topic_id == Topic.id)
            .where(Section.subject_id == subject_id)
            .order_by(Section.sort_order, Section.id, Topic.sort_order, Topic.id)
        )
    ).all()
    if not rows:
        return []

    sections_by_id: dict[int, dict[str, Any]] = {}
    for section, topic, lesson_id, lesson_status in rows:
        section_payload = sections_by_id.setdefault(section.id, {
            **serialize_model(section),
            "topics": [],
        })
        if topic is None:
            continue
        section_payload["topics"].append(
            serialize_topic(topic, lesson_id=lesson_id, lesson_status=lesson_status)
        )

    payload = list(sections_by_id.values())
    if not include_archived:
        remember_subject_outline(subject_id, payload)
    return payload
