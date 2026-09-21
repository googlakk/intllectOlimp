"""Persistence use cases for imported KTP drafts."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Section, Subject, Topic


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

            for topic_order, topic_input in enumerate(section_input.topics, start=1):
                db.add(
                    Topic(
                        section_id=section.id,
                        sort_order=topic_order,
                        ktp_number=topic_input.ktp_number,
                        name=topic_input.name,
                        hours=topic_input.hours,
                        lesson_type=topic_input.lesson_type,
                        learning_objectives=topic_input.learning_objectives,
                        skills=topic_input.skills,
                        resources=topic_input.resources,
                    )
                )
                topic_count += 1

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
