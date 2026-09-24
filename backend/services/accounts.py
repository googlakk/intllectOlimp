"""Provision beta accounts and enforce classroom ownership boundaries."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    AccountEvent,
    Classroom,
    ClassroomStudent,
    ClassroomTeacher,
    Profile,
    Student,
    Teacher,
)
from services.auth import AuthPrincipal, AuthServiceError
from services.curriculum_graph import refresh_student_access
from services.supabase_auth import (
    admin_create_auth_user,
    admin_delete_auth_user,
    admin_update_auth_user,
    normalize_login,
)


def temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(14))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


async def require_classroom_management(user: AuthPrincipal, classroom_id: int, db: AsyncSession) -> Classroom:
    classroom = await db.get(Classroom, classroom_id)
    if classroom is None or classroom.organization_id != user.organization_id:
        raise AuthServiceError(status_code=404, detail="Класс не найден.")
    if user.role == "admin":
        return classroom
    if user.role == "teacher" and user.teacher_id is not None:
        assignment = await db.get(ClassroomTeacher, (classroom_id, user.teacher_id))
        if assignment is not None:
            return classroom
    raise AuthServiceError(status_code=403, detail="Этот класс вам не назначен.")


async def require_student_visibility(user: AuthPrincipal, student_id: int, db: AsyncSession) -> None:
    profile = await db.scalar(select(Profile).where(
        Profile.student_id == student_id,
        Profile.organization_id == user.organization_id,
    ))
    if profile is None:
        raise AuthServiceError(status_code=404, detail="Ученик не найден.")
    if user.role == "admin" or (user.role == "student" and user.student_id == student_id):
        return
    if user.role == "teacher" and user.teacher_id is not None:
        visible = await db.scalar(
            select(ClassroomStudent.id)
            .join(ClassroomTeacher, ClassroomTeacher.classroom_id == ClassroomStudent.classroom_id)
            .where(
                ClassroomStudent.student_id == student_id,
                ClassroomStudent.left_at.is_(None),
                ClassroomTeacher.teacher_id == user.teacher_id,
            )
        )
        if visible is not None:
            return
    raise AuthServiceError(status_code=403, detail="Ученик не относится к вашим классам.")


async def list_classrooms(user: AuthPrincipal, db: AsyncSession) -> list[dict[str, Any]]:
    statement = select(Classroom).where(
        Classroom.organization_id == user.organization_id,
        Classroom.status == "active",
    )
    if user.role == "teacher":
        statement = statement.join(ClassroomTeacher).where(ClassroomTeacher.teacher_id == user.teacher_id)
    rows = (await db.scalars(statement.order_by(Classroom.grade, Classroom.name))).all()
    result = []
    for classroom in rows:
        student_count = len((await db.scalars(select(ClassroomStudent.id).where(
            ClassroomStudent.classroom_id == classroom.id,
            ClassroomStudent.left_at.is_(None),
        ))).all())
        teacher_rows = (await db.execute(
            select(Profile.id, Profile.display_name, Profile.status)
            .join(ClassroomTeacher, ClassroomTeacher.teacher_id == Profile.teacher_id)
            .where(ClassroomTeacher.classroom_id == classroom.id)
            .order_by(Profile.display_name)
        )).all()
        result.append({
            "id": classroom.id,
            "name": classroom.name,
            "grade": classroom.grade,
            "academic_year": classroom.academic_year,
            "student_count": student_count,
            "teachers": [
                {"profile_id": profile_id, "name": name, "status": status}
                for profile_id, name, status in teacher_rows
            ],
        })
    return result


async def list_teachers(user: AuthPrincipal, db: AsyncSession) -> list[dict[str, Any]]:
    if user.role != "admin":
        raise AuthServiceError(status_code=403, detail="Список учителей доступен только администратору.")
    rows = (await db.execute(
        select(Profile, Teacher)
        .join(Teacher, Teacher.id == Profile.teacher_id)
        .where(Profile.organization_id == user.organization_id, Profile.role == "teacher")
        .order_by(Profile.display_name)
    )).all()
    return [{
        "profile_id": profile.id,
        "teacher_id": teacher.id,
        "name": profile.display_name,
        "login": profile.login_name,
        "status": profile.status,
        "must_change_password": profile.must_change_password,
    } for profile, teacher in rows]


async def create_classroom(
    user: AuthPrincipal, *, name: str, grade: int, academic_year: str, db: AsyncSession
) -> dict[str, Any]:
    classroom = Classroom(
        organization_id=user.organization_id,
        name=name.strip(),
        grade=grade,
        academic_year=academic_year.strip(),
        created_by_profile_id=user.profile_id,
    )
    db.add(classroom)
    await db.commit()
    await db.refresh(classroom)
    return {
        "id": classroom.id,
        "name": classroom.name,
        "grade": classroom.grade,
        "academic_year": classroom.academic_year,
        "student_count": 0,
        "teachers": [],
    }


async def _create_profile_with_auth(
    *,
    user: AuthPrincipal,
    role: str,
    login: str,
    display_name: str,
    teacher_id: int | None,
    student_id: int | None,
    db: AsyncSession,
) -> tuple[Profile, str, str]:
    login_name = normalize_login(login)
    duplicate = await db.scalar(select(Profile.id).where(
        Profile.organization_id == user.organization_id,
        Profile.login_name == login_name,
    ))
    if duplicate is not None:
        raise AuthServiceError(status_code=409, detail="Такой логин уже используется.")
    password = temporary_password()
    auth_user = await admin_create_auth_user(
        login=login_name, password=password, display_name=display_name, role=role
    )
    auth_user_id = str(auth_user.get("id") or (auth_user.get("user") or {}).get("id") or "")
    if not auth_user_id:
        raise AuthServiceError(status_code=502, detail="Supabase не вернул идентификатор пользователя.")
    try:
        profile = Profile(
            auth_user_id=UUID(auth_user_id),
            organization_id=user.organization_id,
            role=role,
            login_name=login_name,
            display_name=display_name.strip(),
            status="active",
            must_change_password=True,
            teacher_id=teacher_id,
            student_id=student_id,
            created_by_profile_id=user.profile_id,
        )
        db.add(profile)
        await db.flush()
        db.add(AccountEvent(
            organization_id=user.organization_id,
            actor_profile_id=user.profile_id,
            target_profile_id=profile.id,
            event_type="account_created",
            metadata_json={"role": role},
        ))
        return profile, password, auth_user_id
    except Exception:
        await db.rollback()
        try:
            await admin_delete_auth_user(auth_user_id)
        except Exception:
            pass
        raise


async def create_teacher_account(
    user: AuthPrincipal, *, login: str, display_name: str, db: AsyncSession
) -> dict[str, Any]:
    teacher = Teacher(name=display_name.strip())
    db.add(teacher)
    await db.flush()
    auth_user_id: str | None = None
    try:
        profile, password, auth_user_id = await _create_profile_with_auth(
            user=user,
            role="teacher",
            login=login,
            display_name=display_name,
            teacher_id=teacher.id,
            student_id=None,
            db=db,
        )
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        if auth_user_id:
            await admin_delete_auth_user(auth_user_id)
        raise
    return {"profile_id": profile.id, "teacher_id": teacher.id, "login": profile.login_name, "temporary_password": password}


async def create_student_account(
    user: AuthPrincipal,
    *,
    classroom_id: int,
    login: str,
    display_name: str,
    db: AsyncSession,
) -> dict[str, Any]:
    classroom = await require_classroom_management(user, classroom_id, db)
    student = Student(name=display_name.strip(), grade=classroom.grade)
    db.add(student)
    await db.flush()
    auth_user_id: str | None = None
    try:
        profile, password, auth_user_id = await _create_profile_with_auth(
            user=user,
            role="student",
            login=login,
            display_name=display_name,
            teacher_id=None,
            student_id=student.id,
            db=db,
        )
        db.add(ClassroomStudent(
            classroom_id=classroom.id,
            student_id=student.id,
            enrolled_by_profile_id=user.profile_id,
        ))
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        if auth_user_id:
            await admin_delete_auth_user(auth_user_id)
        raise
    return {
        "profile_id": profile.id,
        "student_id": student.id,
        "classroom_id": classroom.id,
        "login": profile.login_name,
        "temporary_password": password,
    }


async def assign_teacher(
    user: AuthPrincipal, *, classroom_id: int, teacher_profile_id: int, db: AsyncSession
) -> None:
    classroom = await require_classroom_management(user, classroom_id, db)
    profile = await db.get(Profile, teacher_profile_id)
    if (
        profile is None
        or profile.organization_id != user.organization_id
        or profile.role != "teacher"
        or profile.teacher_id is None
        or profile.status != "active"
    ):
        raise AuthServiceError(status_code=404, detail="Учитель не найден.")
    assignment = await db.get(ClassroomTeacher, (classroom.id, profile.teacher_id))
    if assignment is None:
        db.add(ClassroomTeacher(
            classroom_id=classroom.id,
            teacher_id=profile.teacher_id,
            assigned_by_profile_id=user.profile_id,
        ))
        db.add(AccountEvent(
            organization_id=user.organization_id,
            actor_profile_id=user.profile_id,
            target_profile_id=profile.id,
            event_type="classroom_assigned",
            metadata_json={"classroom_id": classroom.id},
        ))
        await db.commit()


async def unassign_teacher(
    user: AuthPrincipal, *, classroom_id: int, teacher_profile_id: int, db: AsyncSession
) -> None:
    classroom = await require_classroom_management(user, classroom_id, db)
    profile = await db.get(Profile, teacher_profile_id)
    if (
        profile is None
        or profile.organization_id != user.organization_id
        or profile.role != "teacher"
        or profile.teacher_id is None
    ):
        raise AuthServiceError(status_code=404, detail="Учитель не найден.")
    assignment = await db.get(ClassroomTeacher, (classroom.id, profile.teacher_id))
    if assignment is None:
        return
    await db.delete(assignment)
    db.add(AccountEvent(
        organization_id=user.organization_id,
        actor_profile_id=user.profile_id,
        target_profile_id=profile.id,
        event_type="classroom_unassigned",
        metadata_json={"classroom_id": classroom.id},
    ))
    await db.commit()


async def list_classroom_students(
    user: AuthPrincipal, classroom_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    await require_classroom_management(user, classroom_id, db)
    rows = (
        await db.execute(
            select(Student, Profile, ClassroomStudent)
            .join(ClassroomStudent, ClassroomStudent.student_id == Student.id)
            .join(Profile, Profile.student_id == Student.id)
            .where(ClassroomStudent.classroom_id == classroom_id, ClassroomStudent.left_at.is_(None))
            .order_by(Student.name)
        )
    ).all()
    return [{
        "student_id": student.id,
        "profile_id": profile.id,
        "name": student.name,
        "login": profile.login_name,
        "grade": student.grade,
        "status": profile.status,
        "must_change_password": profile.must_change_password,
        "enrolled_at": enrollment.enrolled_at,
    } for student, profile, enrollment in rows]


async def transfer_student(
    user: AuthPrincipal, *, student_profile_id: int, target_classroom_id: int, db: AsyncSession
) -> None:
    target = await require_classroom_management(user, target_classroom_id, db)
    profile = await db.get(Profile, student_profile_id)
    if profile is None or profile.organization_id != user.organization_id or profile.student_id is None:
        raise AuthServiceError(status_code=404, detail="Ученик не найден.")
    current = await db.scalar(select(ClassroomStudent).where(
        ClassroomStudent.student_id == profile.student_id,
        ClassroomStudent.left_at.is_(None),
    ))
    if current is not None:
        if current.classroom_id == target.id:
            raise AuthServiceError(status_code=409, detail="Ученик уже состоит в этом классе.")
        await require_classroom_management(user, current.classroom_id, db)
        current.left_at = datetime.now(timezone.utc)
    student = await db.get(Student, profile.student_id)
    if student is not None:
        student.grade = target.grade
    db.add(ClassroomStudent(
        classroom_id=target.id,
        student_id=profile.student_id,
        enrolled_by_profile_id=user.profile_id,
    ))
    db.add(AccountEvent(
        organization_id=user.organization_id,
        actor_profile_id=user.profile_id,
        target_profile_id=profile.id,
        event_type="classroom_transferred",
        metadata_json={"from_classroom_id": current.classroom_id if current else None, "to_classroom_id": target.id},
    ))
    await db.flush()
    await refresh_student_access(profile.student_id, db)
    await db.commit()


async def set_account_blocked(
    user: AuthPrincipal, *, target_profile_id: int, blocked: bool, db: AsyncSession
) -> None:
    profile = await db.get(Profile, target_profile_id)
    if profile is None or profile.organization_id != user.organization_id or profile.role == "admin":
        raise AuthServiceError(status_code=404, detail="Аккаунт не найден.")
    if user.role == "teacher":
        if profile.student_id is None:
            raise AuthServiceError(status_code=403, detail="Учитель может блокировать только своего ученика.")
        await require_student_visibility(user, profile.student_id, db)
    await admin_update_auth_user(str(profile.auth_user_id), {"ban_duration": "876000h" if blocked else "none"})
    profile.status = "blocked" if blocked else "active"
    db.add(AccountEvent(
        organization_id=user.organization_id,
        actor_profile_id=user.profile_id,
        target_profile_id=profile.id,
        event_type="account_blocked" if blocked else "account_restored",
        metadata_json={},
    ))
    await db.commit()


async def reset_temporary_password(
    user: AuthPrincipal, *, target_profile_id: int, db: AsyncSession
) -> str:
    profile = await db.get(Profile, target_profile_id)
    if profile is None or profile.organization_id != user.organization_id or profile.role == "admin":
        raise AuthServiceError(status_code=404, detail="Аккаунт не найден.")
    if user.role == "teacher":
        if profile.student_id is None:
            raise AuthServiceError(status_code=403, detail="Учитель может сбросить пароль только своему ученику.")
        enrollment = await db.scalar(select(ClassroomStudent).join(
            ClassroomTeacher, ClassroomTeacher.classroom_id == ClassroomStudent.classroom_id
        ).where(
            ClassroomStudent.student_id == profile.student_id,
            ClassroomStudent.left_at.is_(None),
            ClassroomTeacher.teacher_id == user.teacher_id,
        ))
        if enrollment is None:
            raise AuthServiceError(status_code=403, detail="Ученик не относится к вашим классам.")
    password = temporary_password()
    await admin_update_auth_user(str(profile.auth_user_id), {"password": password})
    profile.must_change_password = True
    db.add(AccountEvent(
        organization_id=user.organization_id,
        actor_profile_id=user.profile_id,
        target_profile_id=profile.id,
        event_type="password_reset_issued",
        metadata_json={},
    ))
    await db.commit()
    return password
