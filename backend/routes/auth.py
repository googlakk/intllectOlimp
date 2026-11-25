from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import current_user
from models import Student, Teacher, User
from security import (
    SESSION_COOKIE,
    SESSION_TTL,
    cookie_secure,
    create_session_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


class LoginInput(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


async def serialize_user(user: User, db: AsyncSession) -> dict:
    data = {
        "id": user.id,
        "login": user.login,
        "name": user.full_name,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "student_id": None,
        "teacher_id": None,
        "grade": None,
    }
    if user.role == "student":
        student = await db.scalar(select(Student).where(Student.user_id == user.id))
        if student:
            data["student_id"], data["grade"] = student.id, student.grade
    elif user.role == "teacher":
        teacher = await db.scalar(select(Teacher).where(Teacher.user_id == user.id))
        if teacher:
            data["teacher_id"] = teacher.id
    return data


@router.post("/login")
async def login(payload: LoginInput, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(func.lower(User.login) == payload.login.strip().lower()))
    password_ok = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    set_session_cookie(response, user.id)
    return await serialize_user(user, db)


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await serialize_user(user, db)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordInput,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="Новый пароль должен отличаться от текущего")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    await db.commit()
    return await serialize_user(user, db)
