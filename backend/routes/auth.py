from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, Teacher

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginInput(BaseModel):
    role: str
    name: str


def to_dict(user, role: str):
    return {"id": user.id, "name": user.name, "role": role, "grade": getattr(user, "grade", None)}


@router.get("/users")
async def users(db: AsyncSession = Depends(get_db)):
    students = (await db.scalars(select(Student).order_by(Student.name))).all()
    teachers = (await db.scalars(select(Teacher).order_by(Teacher.name))).all()
    return {"students": [to_dict(u, "student") for u in students], "teachers": [to_dict(u, "teacher") for u in teachers]}


@router.post("/login")
async def login(payload: LoginInput, db: AsyncSession = Depends(get_db)):
    if payload.role not in {"student", "teacher"}:
        raise HTTPException(400, "Неизвестная роль")
    model = Student if payload.role == "student" else Teacher
    user = await db.scalar(select(model).where(model.name == payload.name))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return to_dict(user, payload.role)