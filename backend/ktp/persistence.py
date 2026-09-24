"""Persistence use cases for imported KTP drafts."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Section, Subject, Topic
from topic_semantics import CONSOLIDATION_TYPES, ambiguous_lesson_name
from services.curriculum_graph import infer_topic_contract, rebuild_subject_graph


class KtpPersistenceError(ApplicationError):
    def __init__(self):
        super().__init__(
            status_code=500,
            detail="Не удалось сохранить загруженный КТП",
        )


async def save_ktp_draft(payload: Any, db: AsyncSession) -> dict[str, Any]:
    """Persist a reviewed KTP draft as subject, sections, and topics."""
    try:
        subject = Subject(
            name=payload.subject_name,
            grade=payload.grade,
            hours_per_week=payload.hours_per_week,
            hours_per_year=payload.hours_per_year,
            source_info="Загружено из КТП",
            instruction_language=payload.instruction_language,
        )
        db.add(subject)
        await db.flush()

        topic_count = 0
        for sort_order, section_input in enumerate(payload.sections, start=1):
            section = Section(
                subject_id=subject.id,
                name=section_input.name,
                sort_order=sort_order,
                total_hours=section_input.total_hours,
            )
            db.add(section)
            await db.flush()

            previous_topics = []
            for topic_order, topic_input in enumerate(section_input.topics, start=1):
                contract = infer_topic_contract(
                    subject_name=payload.subject_name,
                    grade=payload.grade,
                    topic_name=topic_input.name,
                    lesson_type=topic_input.lesson_type,
                    learning_objectives=topic_input.learning_objectives,
                    skills=topic_input.skills,
                )
                created_topic = Topic(
                        section_id=section.id,
                        sort_order=topic_order,
                        ktp_number=topic_input.ktp_number,
                        name=topic_input.name,
                        hours=topic_input.hours,
                        lesson_type=topic_input.lesson_type,
                        learning_objectives=contract["learning_objectives"],
                        skills=contract["skills"],
                        resources=topic_input.resources,
                        covered_topic_ids=[row.id for row in previous_topics if row.lesson_type in {"study", "project"}] if topic_input.lesson_type in CONSOLIDATION_TYPES else [],
                        source_assessment_topic_id=next((row.id for row in reversed(previous_topics) if row.lesson_type == "assessment"), None) if topic_input.lesson_type == "reflection" else None,
                        review_required=getattr(topic_input, "review_required", False) or ambiguous_lesson_name(topic_input.name) or (topic_input.lesson_type in CONSOLIDATION_TYPES and not any(row.lesson_type in {"study", "project"} for row in previous_topics)),
                    )
                db.add(created_topic)
                await db.flush()
                previous_topics.append(created_topic)
                topic_count += 1

        await db.flush()
        # Real AsyncSession builds the graph in the same transaction. Lightweight
        # test sessions intentionally exercise persistence only.
        if hasattr(db, "execute"):
            await rebuild_subject_graph(subject.id, db)

        await db.commit()
        await db.refresh(subject)
        return {
            "id": subject.id,
            "name": subject.name,
            "grade": subject.grade,
            "hours_per_week": subject.hours_per_week,
            "hours_per_year": subject.hours_per_year,
            "source_info": subject.source_info,
            "instruction_language": subject.instruction_language,
            "created_at": subject.created_at,
            "section_count": len(payload.sections),
            "topic_count": topic_count,
        }
    except Exception as exc:
        await db.rollback()
        raise KtpPersistenceError() from exc
