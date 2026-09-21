from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.dashboard import get_dashboard_overview, get_dashboard_students

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    return await get_dashboard_overview(db)


@router.get("/students")
async def student_rows(db: AsyncSession = Depends(get_db)):
    return await get_dashboard_students(db)
