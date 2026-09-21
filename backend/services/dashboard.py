from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import GeneratedLesson, Progress, Student, Subject, Topic


def build_dashboard_overview(
    *,
    students: int,
    subjects: int,
    topics: int,
    published_lessons: int,
    completed_lessons: int,
) -> dict[str, int | float]:
    return {
        "students": students,
        "subjects": subjects,
        "topics": topics,
        "published_lessons": published_lessons,
        "average_progress": round(completed_lessons / topics * 100, 1) if topics else 0,
    }


def serialize_student_summary(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "grade": row.grade,
        "completed_topics": row.completed_topics,
        "average_score": float(row.average_score),
    }


async def get_dashboard_overview(db: AsyncSession) -> dict[str, int | float]:
    students = await db.scalar(select(func.count(Student.id))) or 0
    subjects = await db.scalar(select(func.count(Subject.id))) or 0
    topics = await db.scalar(select(func.count(Topic.id))) or 0
    published = await db.scalar(
        select(func.count(GeneratedLesson.id)).where(GeneratedLesson.status == "published")
    ) or 0
    completed = await db.scalar(
        select(func.count(Progress.id)).where(Progress.status == "completed")
    ) or 0
    return build_dashboard_overview(
        students=students,
        subjects=subjects,
        topics=topics,
        published_lessons=published,
        completed_lessons=completed,
    )


async def get_dashboard_students(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                Student.id,
                Student.name,
                Student.grade,
                func.count(Progress.id)
                .filter(Progress.status == "completed")
                .label("completed_topics"),
                func.coalesce(func.avg(Progress.score), 0).label("average_score"),
            )
            .outerjoin(Progress, Progress.student_id == Student.id)
            .group_by(Student.id)
            .order_by(Student.name)
        )
    ).all()
    return [serialize_student_summary(row) for row in rows]
