"""Reversible student removal without deleting credentials or learning history."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccountEvent, Classroom, ClassroomStudent, Profile, Student
from services.accounts import require_classroom_management
from services.auth import AuthPrincipal, AuthServiceError, forget_principal
from services.curriculum_graph import refresh_student_access


def _require_admin(user: AuthPrincipal) -> None:
    if user.role != "admin":
        raise AuthServiceError(403, "Удалять и восстанавливать учеников может только администратор.")


async def _student_profile(user: AuthPrincipal, profile_id: int, db: AsyncSession) -> Profile:
    profile = await db.scalar(select(Profile).where(
        Profile.id == profile_id, Profile.organization_id == user.organization_id,
        Profile.role == "student", Profile.student_id.is_not(None),
    ).with_for_update())
    if profile is None:
        raise AuthServiceError(404, "Ученик не найден.")
    return profile


async def remove_student(
    user: AuthPrincipal, *, classroom_id: int, student_profile_id: int, db: AsyncSession,
) -> None:
    _require_admin(user)
    await require_classroom_management(user, classroom_id, db)
    profile = await _student_profile(user, student_profile_id, db)
    if profile.status == "archived":
        return
    enrollments = (await db.scalars(select(ClassroomStudent).join(
        Classroom, Classroom.id == ClassroomStudent.classroom_id,
    ).where(
        ClassroomStudent.student_id == profile.student_id,
        ClassroomStudent.left_at.is_(None), Classroom.organization_id == user.organization_id,
    ))).all()
    if not any(row.classroom_id == classroom_id for row in enrollments):
        raise AuthServiceError(409, "Ученик уже не состоит в выбранном классе. Обновите список.")
    now = datetime.now(timezone.utc)
    previous_status = profile.status
    for enrollment in enrollments:
        enrollment.left_at = now
    profile.status = "archived"
    db.add(AccountEvent(
        organization_id=user.organization_id, actor_profile_id=user.profile_id,
        target_profile_id=profile.id, event_type="account_blocked",
        metadata_json={"action": "student_removed", "classroom_id": classroom_id, "previous_status": previous_status},
    ))
    await db.commit()
    forget_principal(profile.auth_user_id)


async def list_removed_students(user: AuthPrincipal, db: AsyncSession) -> list[dict[str, Any]]:
    _require_admin(user)
    rows = (await db.execute(select(Student, Profile).join(
        Profile, Profile.student_id == Student.id,
    ).where(
        Profile.organization_id == user.organization_id, Profile.role == "student",
        Profile.status == "archived",
    ).order_by(Student.name))).all()
    return [{
        "student_id": student.id, "profile_id": profile.id, "name": student.name,
        "login": profile.login_name, "grade": student.grade, "status": profile.status,
        "must_change_password": profile.must_change_password,
    } for student, profile in rows]


async def restore_student(
    user: AuthPrincipal, *, student_profile_id: int, target_classroom_id: int, db: AsyncSession,
) -> None:
    _require_admin(user)
    target = await require_classroom_management(user, target_classroom_id, db)
    if target.status != "active":
        raise AuthServiceError(409, "Выберите действующий класс.")
    profile = await _student_profile(user, student_profile_id, db)
    if profile.status != "archived":
        raise AuthServiceError(409, "Этот ученик не удалён. Обновите список.")
    student = await db.get(Student, profile.student_id)
    if student is None:
        raise AuthServiceError(404, "Ученик не найден.")
    existing = await db.scalar(select(ClassroomStudent.id).where(
        ClassroomStudent.student_id == student.id, ClassroomStudent.left_at.is_(None),
    ))
    if existing is not None:
        raise AuthServiceError(409, "У ученика уже есть действующий класс. Обратитесь к администратору.")
    removal = await db.scalar(select(AccountEvent).where(
        AccountEvent.organization_id == user.organization_id,
        AccountEvent.target_profile_id == profile.id, AccountEvent.event_type == "account_blocked",
        AccountEvent.metadata_json["action"].astext == "student_removed",
    ).order_by(AccountEvent.id.desc()).limit(1))
    # Restore a pre-existing block, rather than silently granting a blocked pupil access.
    previous = (removal.metadata_json or {}).get("previous_status") if removal else None
    profile.status = previous if previous in ("active", "blocked", "invited") else "blocked"
    student.grade = target.grade
    db.add(ClassroomStudent(
        classroom_id=target.id, student_id=student.id, enrolled_by_profile_id=user.profile_id,
    ))
    db.add(AccountEvent(
        organization_id=user.organization_id, actor_profile_id=user.profile_id,
        target_profile_id=profile.id, event_type="account_restored",
        metadata_json={"action": "student_restored", "classroom_id": target.id, "status": profile.status},
    ))
    await db.flush()
    await refresh_student_access(student.id, db)
    await db.commit()
    forget_principal(profile.auth_user_id)
