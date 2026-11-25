from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_role, require_staff
from models import SchoolClass, Section, Student, Topic, TopicDelivery

router = APIRouter(prefix="/api", tags=["classes"])


class ClassInput(BaseModel):
    school_system: Literal[11, 12]
    grade: int = Field(ge=1, le=12)
    letter: str = Field(min_length=1, max_length=5)
    program: Literal["cambridge", "national"]


class StudentClassInput(BaseModel):
    class_id: int | None


class DeliveryInput(BaseModel):
    class_id: int
    conducted_on: date


def serialize_class(row: SchoolClass, student_count: int = 0) -> dict:
    return {
        "student_count": student_count,
        "id": row.id,
        "school_system": row.school_system,
        "grade": row.grade,
        "letter": row.letter,
        "program": row.program,
        "name": f"{row.grade}{row.letter}",
    }


@router.get("/classes", dependencies=[Depends(require_staff)])
async def list_classes(db: AsyncSession = Depends(get_db)):
    counts = (
        select(Student.class_id, func.count(Student.id).label("n")).group_by(Student.class_id).subquery()
    )
    rows = await db.execute(
        select(SchoolClass, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.class_id == SchoolClass.id)
        .order_by(SchoolClass.grade, SchoolClass.letter)
    )
    return [serialize_class(row, n) for row, n in rows]


@router.delete("/classes/{class_id}", dependencies=[Depends(require_role("admin"))])
async def delete_class(class_id: int, db: AsyncSession = Depends(get_db)):
    """Students of the class are kept; they only lose the class link (ON DELETE SET NULL)."""
    row = await db.get(SchoolClass, class_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Класс не найден")
    await db.delete(row)
    await db.commit()
    return {"deleted": class_id}


@router.get("/students", dependencies=[Depends(require_staff)])
async def list_students(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Student).order_by(Student.grade, Student.name))
    return [{"id": r.id, "name": r.name, "grade": r.grade, "class_id": r.class_id} for r in rows]


@router.post("/classes", dependencies=[Depends(require_role("admin"))])
async def create_class(payload: ClassInput, db: AsyncSession = Depends(get_db)):
    row = SchoolClass(**payload.model_dump() | {"letter": payload.letter.strip().upper()})
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Такой класс уже есть") from exc
    await db.refresh(row)
    return serialize_class(row)


@router.put("/students/{student_id}/class", dependencies=[Depends(require_role("admin"))])
async def set_student_class(student_id: int, payload: StudentClassInput, db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Ученик не найден")
    if payload.class_id is not None:
        school_class = await db.get(SchoolClass, payload.class_id)
        if school_class is None:
            raise HTTPException(status_code=404, detail="Класс не найден")
        student.grade = school_class.grade  # keep the legacy column consistent
    student.class_id = payload.class_id
    await db.commit()
    return {"id": student.id, "class_id": student.class_id, "grade": student.grade}


@router.get("/topics/{topic_id}/deliveries", dependencies=[Depends(require_staff)])
async def list_deliveries(topic_id: int, db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(TopicDelivery).where(TopicDelivery.topic_id == topic_id).order_by(TopicDelivery.conducted_on)
    )
    return [{"id": r.id, "class_id": r.class_id, "conducted_on": r.conducted_on} for r in rows]


@router.get("/subjects/{subject_id}/deliveries", dependencies=[Depends(require_staff)])
async def subject_deliveries(subject_id: int, db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(TopicDelivery)
        .join(Topic, TopicDelivery.topic_id == Topic.id)
        .join(Section, Topic.section_id == Section.id)
        .where(Section.subject_id == subject_id)
        .order_by(TopicDelivery.conducted_on)
    )
    return [{"id": r.id, "topic_id": r.topic_id, "class_id": r.class_id, "conducted_on": r.conducted_on} for r in rows]


@router.post("/topics/{topic_id}/deliveries", dependencies=[Depends(require_staff)])
async def mark_delivered(topic_id: int, payload: DeliveryInput, db: AsyncSession = Depends(get_db)):
    """The «Проведено» mark: the next lesson part of this topic opens for the class."""
    if await db.get(Topic, topic_id) is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    if await db.get(SchoolClass, payload.class_id) is None:
        raise HTTPException(status_code=404, detail="Класс не найден")
    row = TopicDelivery(topic_id=topic_id, class_id=payload.class_id, conducted_on=payload.conducted_on)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Уже отмечено в этот день") from exc
    await db.refresh(row)
    return {"id": row.id, "class_id": row.class_id, "conducted_on": row.conducted_on}


@router.delete("/deliveries/{delivery_id}", dependencies=[Depends(require_staff)])
async def unmark_delivered(delivery_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(TopicDelivery, delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Отметка не найдена")
    await db.delete(row)
    await db.commit()
    return {"deleted": delivery_id}
