from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import GeneratedLesson, Section, Subject, Topic


def serialize_model(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def serialize_subject(row: Subject) -> dict[str, Any]:
    return {**serialize_model(row), "progress": 0}


async def list_subjects(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(Subject).order_by(Subject.name))).all()
    return [serialize_subject(row) for row in rows]


async def list_sections(subject_id: int, db: AsyncSession) -> list[dict[str, Any]]:
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
    payload["lesson_id"] = lesson_id
    payload["lesson_status"] = lesson_status
    return payload


async def list_topics(section_id: int, db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(Topic)
            .where(Topic.section_id == section_id)
            .order_by(Topic.sort_order, Topic.id)
        )
    ).all()
    return [serialize_model(row) for row in rows]


async def list_subject_outline(subject_id: int, db: AsyncSession) -> list[dict[str, Any]]:
    sections = (
        await db.scalars(
            select(Section)
            .where(Section.subject_id == subject_id)
            .order_by(Section.sort_order)
        )
    ).all()
    if not sections:
        return []

    section_ids = [section.id for section in sections]
    topic_rows = (
        await db.execute(
            select(Topic, GeneratedLesson.id, GeneratedLesson.status)
            .outerjoin(GeneratedLesson, GeneratedLesson.topic_id == Topic.id)
            .where(Topic.section_id.in_(section_ids))
            .order_by(Topic.section_id, Topic.sort_order, Topic.id)
        )
    ).all()

    topics_by_section: dict[int, list[dict[str, Any]]] = {section.id: [] for section in sections}
    for topic, lesson_id, lesson_status in topic_rows:
        topics_by_section[topic.section_id].append(
            serialize_topic(topic, lesson_id=lesson_id, lesson_status=lesson_status)
        )

    return [
        {
            **serialize_model(section),
            "topics": topics_by_section.get(section.id, []),
        }
        for section in sections
    ]
