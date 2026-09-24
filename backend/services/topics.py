"""Teacher-owned topic lifecycle. Archive never removes learning history."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import GeneratedLesson, Section, Subject, Topic
from services.auth import AuthPrincipal
from services.catalog import clear_subject_outline_cache, serialize_topic
from services.curriculum_graph import clear_curriculum_map_cache, infer_topic_contract, rebuild_subject_graph
from services.educator_access import require_section_management, require_subject_management, require_topic_management
from topic_semantics import CONSOLIDATION_TYPES


async def _apply_scope(topic: Topic, values: dict[str, Any], section: Section, db: AsyncSession, *, creating: bool = False) -> None:
    siblings = (await db.scalars(select(Topic).join(Section, Topic.section_id == Section.id).where(
        Section.subject_id == section.subject_id,
    ).order_by(Section.sort_order, Section.id, Topic.sort_order, Topic.id))).all()
    # Rows are ordered by curriculum position; the new topic has already been flushed.
    current_index = next((i for i, row in enumerate(siblings) if row.id == topic.id), len(siblings))
    preserved_ids = set(topic.covered_topic_ids or []) | {topic.source_assessment_topic_id}
    eligible = [row for row in siblings[:current_index] if row.archived_at is None or row.id in preserved_ids]
    by_id = {row.id: row for row in eligible}
    if topic.lesson_type not in CONSOLIDATION_TYPES:
        topic.covered_topic_ids = []
        topic.source_assessment_topic_id = None
        topic.review_required = False
        return
    covered = values.get("covered_topic_ids")
    if covered is None:
        covered = ([row.id for row in eligible if row.archived_at is None and row.section_id == section.id and row.lesson_type in {"study", "project"}]
                   if creating else list(topic.covered_topic_ids or []))
    covered = list(dict.fromkeys(covered))
    if any(identifier not in by_id for identifier in covered):
        raise ApplicationError(422, "Выберите предыдущие активные темы этого предмета.")
    topic.covered_topic_ids = covered
    source = values.get("source_assessment_topic_id", topic.source_assessment_topic_id)
    if topic.lesson_type == "reflection" and source is None and creating and "source_assessment_topic_id" not in values:
        source = next((row.id for row in reversed(eligible) if row.archived_at is None and row.lesson_type == "assessment" and row.section_id == section.id), None)
    if source is not None and (source not in by_id or by_id[source].lesson_type != "assessment"):
        raise ApplicationError(422, "Для разбора выберите предыдущую контрольную этого предмета.")
    topic.source_assessment_topic_id = source if topic.lesson_type == "reflection" else None
    if topic.lesson_type == "reflection" and source is not None and "covered_topic_ids" not in values:
        topic.covered_topic_ids = list(by_id[source].covered_topic_ids or [])
    topic.review_required = not bool(topic.covered_topic_ids)


async def _finish(topic: Topic, subject_id: int, db: AsyncSession, *, refresh_draft: bool = False) -> dict[str, Any]:
    await db.flush()
    await rebuild_subject_graph(subject_id, db)
    if refresh_draft:
        from services.lessons import refresh_lesson_topic_draft
        await refresh_lesson_topic_draft(topic, db)
    section = await db.get(Section, topic.section_id)
    if section is not None:
        section.total_hours = await db.scalar(select(func.coalesce(func.sum(Topic.hours), 0)).where(
            Topic.section_id == section.id, Topic.archived_at.is_(None))) or 0
    subject = await db.get(Subject, subject_id)
    if subject is not None:
        subject.hours_per_year = await db.scalar(select(func.coalesce(func.sum(Topic.hours), 0))
            .join(Section, Section.id == Topic.section_id)
            .where(Section.subject_id == subject_id, Topic.archived_at.is_(None))) or 0
    await db.commit()
    clear_subject_outline_cache(subject_id)
    clear_curriculum_map_cache()
    from services.lessons import clear_lesson_manifest_cache
    clear_lesson_manifest_cache(topic.id)
    await db.refresh(topic)
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    return serialize_topic(topic, lesson.id if lesson else None, lesson.status if lesson else None)


async def get_topic(topic_id: int, user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    topic = await require_topic_management(user, topic_id, db)
    section = await require_section_management(user, topic.section_id, db)
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
    return {**serialize_topic(topic, lesson.id if lesson else None, lesson.status if lesson else None),
            "subject_id": section.subject_id}


async def create_topic(section_id: int, values: dict[str, Any], user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    section = await require_section_management(user, section_id, db)
    subject = await require_subject_management(user, section.subject_id, db)
    existing = (await db.scalars(select(Topic).where(Topic.section_id == section_id))).all()
    topic = Topic(section_id=section_id, sort_order=max((row.sort_order for row in existing), default=0) + 1,
                  name=values["name"].strip(), hours=values.get("hours", 1), lesson_type=values.get("lesson_type", "study"),
                  skills=values.get("skills", []), learning_objectives=values.get("learning_objectives", ""),
                  covered_topic_ids=[], review_required=False)
    db.add(topic)
    await db.flush()
    await _apply_scope(topic, values, section, db, creating=True)
    contract = infer_topic_contract(subject_name=subject.name, grade=subject.grade, topic_name=topic.name,
                                    lesson_type=topic.lesson_type, learning_objectives=topic.learning_objectives, skills=topic.skills)
    topic.learning_objectives = contract["learning_objectives"]
    topic.skills = contract["skills"]
    return await _finish(topic, section.subject_id, db)


async def update_topic(topic_id: int, values: dict[str, Any], user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    topic = await require_topic_management(user, topic_id, db)
    if topic.archived_at is not None:
        raise ApplicationError(409, "Сначала восстановите занятие из архива.")
    section = await require_section_management(user, topic.section_id, db)
    old_derived_goals = "; ".join(topic.skills or [])
    refresh_derived_goals = (
        topic.lesson_type in CONSOLIDATION_TYPES
        and bool(old_derived_goals)
        and (topic.learning_objectives or "").strip() == old_derived_goals
        and values.get("learning_objectives", topic.learning_objectives) == topic.learning_objectives
        and any(key in values for key in ("covered_topic_ids", "source_assessment_topic_id", "lesson_type"))
    )
    for key in ("name", "hours", "lesson_type", "learning_objectives", "skills"):
        if key in values:
            setattr(topic, key, values[key].strip() if key == "name" else values[key])
    await _apply_scope(topic, values, section, db)
    if refresh_derived_goals:
        topic.learning_objectives = ""
    return await _finish(topic, section.subject_id, db, refresh_draft=True)


async def set_topic_archived(topic_id: int, archived: bool, user: AuthPrincipal, db: AsyncSession) -> dict[str, Any]:
    topic = await require_topic_management(user, topic_id, db)
    section = await require_section_management(user, topic.section_id, db)
    if archived and topic.archived_at is None:
        topic.archived_at = datetime.now(timezone.utc)
    elif not archived and topic.archived_at is not None:
        topic.archived_at = None
        topic.review_required = True
        lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == topic.id))
        if lesson is not None:
            lesson.status = "draft"
            lesson.published_at = None
            lesson.published_by = None
            lesson.published_version_id = None
    return await _finish(topic, section.subject_id, db)
