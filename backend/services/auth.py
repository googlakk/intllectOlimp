from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from models import Student, Teacher

UserRole = Literal["student", "teacher"]


class AuthServiceError(ApplicationError):
    pass


def serialize_user(user: Any, role: UserRole) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "role": role,
        "grade": getattr(user, "grade", None),
    }


def user_model_for_role(role: str):
    if role == "student":
        return Student
    if role == "teacher":
        return Teacher
    raise AuthServiceError(status_code=400, detail="Неизвестная роль")


async def list_login_users(db: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    students = (await db.scalars(select(Student).order_by(Student.name))).all()
    teachers = (await db.scalars(select(Teacher).order_by(Teacher.name))).all()
    return {
        "students": [serialize_user(user, "student") for user in students],
        "teachers": [serialize_user(user, "teacher") for user in teachers],
    }


async def login_user(role: str, name: str, db: AsyncSession) -> dict[str, Any]:
    model = user_model_for_role(role)
    user = await db.scalar(select(model).where(model.name == name))
    if not user:
        raise AuthServiceError(status_code=404, detail="Пользователь не найден")
    return serialize_user(user, role)  # type: ignore[arg-type]
