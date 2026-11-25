from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Quarter, Section, Subject, Topic
from deps import require_any

router = APIRouter(prefix="/api", tags=["subjects"], dependencies=[Depends(require_any)])


TOPIC_ORDER = (Topic.quarter.asc().nulls_last(), Topic.sort_number.asc().nulls_last(), Topic.ktp_number, Topic.id)


def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@router.get("/subjects")
async def subjects(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Subject).order_by(Subject.name))).all()
    return [{**serialize(row), "progress": 0} for row in rows]


@router.get("/subjects/{subject_id}/sections")
async def sections(subject_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Section).where(Section.subject_id == subject_id).order_by(Section.sort_order))).all()
    return [serialize(row) for row in rows]


@router.get("/sections/{section_id}/topics")
async def topics(section_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Topic).where(Topic.section_id == section_id).order_by(*TOPIC_ORDER))).all()
    return [serialize(row) for row in rows]


@router.get("/subjects/{subject_id}/topics")
async def subject_topics(subject_id: int, db: AsyncSession = Depends(get_db)):
    """All KTP rows of a subject in course order, for grouping by quarter on the client."""
    rows = (
        await db.execute(
            select(Topic, Section.name, Section.sort_order)
            .join(Section, Topic.section_id == Section.id)
            .where(Section.subject_id == subject_id)
            .order_by(*TOPIC_ORDER)
        )
    ).all()
    return [
        {**serialize(topic), "section_name": section_name, "section_sort_order": section_order}
        for topic, section_name, section_order in rows
    ]

@router.get("/quarters")
async def quarters(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Quarter).order_by(Quarter.starts_on))).all()
    return [serialize(row) for row in rows]
