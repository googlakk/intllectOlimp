from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Section, Subject, Topic

router = APIRouter(prefix="/api/ktp", tags=["ktp"])


class TopicInput(BaseModel):
    ktp_number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    hours: int = Field(default=1, ge=1)
    lesson_type: Literal["study", "assessment", "project"] = "study"
    learning_objectives: str = ""
    skills: list[str] = Field(default_factory=list)
    resources: str = ""


class SectionInput(BaseModel):
    name: str = Field(min_length=1)
    total_hours: int = Field(ge=0)
    topics: list[TopicInput] = Field(default_factory=list)


class KtpUploadInput(BaseModel):
    subject_name: str = Field(min_length=1)
    grade: int = Field(ge=1, le=12)
    hours_per_week: int = Field(ge=0)
    hours_per_year: int = Field(ge=0)
    sections: list[SectionInput] = Field(default_factory=list)


@router.post("/upload")
async def upload_ktp(payload: KtpUploadInput, db: AsyncSession = Depends(get_db)):
    try:
        subject = Subject(
            name=payload.subject_name,
            grade=payload.grade,
            hours_per_week=payload.hours_per_week,
            hours_per_year=payload.hours_per_year,
            source_info="Загружено из КТП",
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

            for topic_input in section_input.topics:
                db.add(
                    Topic(
                        section_id=section.id,
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
            "created_at": subject.created_at,
            "section_count": len(payload.sections),
            "topic_count": topic_count,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить загруженный КТП") from exc