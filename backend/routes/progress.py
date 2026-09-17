from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Progress

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/{student_id}")
async def by_student(student_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Progress).where(Progress.student_id == student_id))).all()
    return [{c.name: getattr(row, c.name) for c in Progress.__table__.columns} for row in rows]