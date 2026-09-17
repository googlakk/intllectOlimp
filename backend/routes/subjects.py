from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Section, Subject, Topic

router = APIRouter(prefix="/api", tags=["subjects"])


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
    rows = (await db.scalars(select(Topic).where(Topic.section_id == section_id).order_by(Topic.ktp_number))).all()
    return [serialize(row) for row in rows]