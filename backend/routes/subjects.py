from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.catalog import list_sections, list_subject_outline, list_subjects, list_topics

router = APIRouter(prefix="/api", tags=["subjects"])


@router.get("/subjects")
async def subjects(db: AsyncSession = Depends(get_db)):
    return await list_subjects(db)


@router.get("/subjects/{subject_id}/sections")
async def sections(subject_id: int, db: AsyncSession = Depends(get_db)):
    return await list_sections(subject_id, db)


@router.get("/subjects/{subject_id}/outline")
async def subject_outline(subject_id: int, db: AsyncSession = Depends(get_db)):
    return await list_subject_outline(subject_id, db)


@router.get("/sections/{section_id}/topics")
async def topics(section_id: int, db: AsyncSession = Depends(get_db)):
    return await list_topics(section_id, db)
