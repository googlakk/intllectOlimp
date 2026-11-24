"""FastAPI dependencies for the signed-in user and role checks."""
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, Teacher, User
from security import SESSION_COOKIE, read_session_token


async def current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = read_session_token(session) if session else None
    user = await db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Требуется вход")
    return user


def require_role(*roles: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return user

    return dependency


require_admin = require_role("admin")
require_staff = require_role("admin", "teacher")
require_any = require_role("admin", "teacher", "student")


async def current_teacher(
    user: User = Depends(require_role("teacher")), db: AsyncSession = Depends(get_db)
) -> Teacher:
    teacher = await db.scalar(select(Teacher).where(Teacher.user_id == user.id))
    if teacher is None:
        raise HTTPException(status_code=403, detail="Профиль учителя не найден")
    return teacher


async def current_student(
    user: User = Depends(require_role("student")), db: AsyncSession = Depends(get_db)
) -> Student:
    student = await db.scalar(select(Student).where(Student.user_id == user.id))
    if student is None:
        raise HTTPException(status_code=403, detail="Профиль ученика не найден")
    return student
