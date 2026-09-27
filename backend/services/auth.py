"""Verified platform identities and role-based FastAPI dependencies."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Profile, Student, Teacher

UserRole = Literal["admin", "teacher", "student"]


class AuthServiceError(ApplicationError):
    pass


@dataclass(frozen=True)
class AuthPrincipal:
    profile_id: int
    auth_user_id: UUID
    organization_id: int
    role: UserRole
    login_name: str
    display_name: str
    must_change_password: bool
    teacher_id: int | None
    student_id: int | None
    grade: int | None
    access_token: str


def serialize_principal(user: AuthPrincipal) -> dict[str, Any]:
    return {
        "id": user.student_id or user.teacher_id or user.profile_id,
        "profile_id": user.profile_id,
        "name": user.display_name,
        "login_name": user.login_name,
        "role": user.role,
        "grade": user.grade,
        "must_change_password": user.must_change_password,
    }


# Профиль активного пользователя помним недолго: это лишний запрос к базе на каждом вызове API.
# Смена пароля, блокировка и сброс пароля сбрасывают запись сразу (forget_principal).
PRINCIPAL_TTL_S = 30
_principals: dict[UUID, tuple[float, AuthPrincipal]] = {}


def forget_principal(auth_user_id: UUID | str | None) -> None:
    try:
        _principals.pop(UUID(str(auth_user_id)), None)
    except (TypeError, ValueError):
        pass


async def principal_for_auth_user(auth_user_id: str, access_token: str, db: AsyncSession) -> AuthPrincipal:
    try:
        parsed_auth_user_id = UUID(auth_user_id)
    except (TypeError, ValueError) as exc:
        raise AuthServiceError(status_code=401, detail="Сессия недействительна.", code="session_invalid") from exc
    cached = _principals.get(parsed_auth_user_id)
    if cached and cached[0] > time.monotonic():
        return replace(cached[1], access_token=access_token)
    row = (
        await db.execute(
            select(Profile, Student.grade)
            .outerjoin(Student, Student.id == Profile.student_id)
            .where(Profile.auth_user_id == parsed_auth_user_id)
        )
    ).one_or_none()
    if row is None:
        raise AuthServiceError(status_code=403, detail="Профиль платформы не создан.", code="profile_missing")
    profile, grade = row
    if profile.status != "active":
        message = "Аккаунт заблокирован." if profile.status == "blocked" else "Аккаунт пока не активирован."
        code = "account_blocked" if profile.status == "blocked" else "account_inactive"
        raise AuthServiceError(status_code=403, detail=message, code=code)
    principal = AuthPrincipal(
        profile_id=profile.id,
        auth_user_id=profile.auth_user_id,
        organization_id=profile.organization_id,
        role=profile.role,
        login_name=profile.login_name,
        display_name=profile.display_name,
        must_change_password=profile.must_change_password,
        teacher_id=profile.teacher_id,
        student_id=profile.student_id,
        grade=grade,
        access_token=access_token,
    )
    if len(_principals) > 5000:
        _principals.clear()
    _principals[parsed_auth_user_id] = (time.monotonic() + PRINCIPAL_TTL_S, principal)
    return principal


# Kept as pure helpers for old data migrations; they are not exposed as login APIs.
def user_model_for_role(role: str):
    if role == "student":
        return Student
    if role == "teacher":
        return Teacher
    raise AuthServiceError(status_code=400, detail="Неизвестная роль")
