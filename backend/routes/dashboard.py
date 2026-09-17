from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import GeneratedLesson, Progress, Student, Subject, Topic

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    students = await db.scalar(select(func.count(Student.id))) or 0
    subjects = await db.scalar(select(func.count(Subject.id))) or 0
    topics = await db.scalar(select(func.count(Topic.id))) or 0
    published = await db.scalar(select(func.count(GeneratedLesson.id)).where(GeneratedLesson.status == "published")) or 0
    completed = await db.scalar(select(func.count(Progress.id)).where(Progress.status == "completed")) or 0
    return {"students": students, "subjects": subjects, "topics": topics, "published_lessons": published, "average_progress": round(completed / topics * 100, 1) if topics else 0}


@router.get("/students")
async def student_rows(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Student.id, Student.name, Student.grade, func.count(Progress.id).filter(Progress.status == "completed").label("completed_topics"), func.coalesce(func.avg(Progress.score), 0).label("average_score")).outerjoin(Progress, Progress.student_id == Student.id).group_by(Student.id).order_by(Student.name))).all()
    return [{"id": r.id, "name": r.name, "grade": r.grade, "completed_topics": r.completed_topics, "average_score": float(r.average_score)} for r in rows]