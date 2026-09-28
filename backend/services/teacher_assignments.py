"""Explicit, organization-scoped subject permissions for subject teachers."""

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccountEvent, Classroom, Profile, Subject
from services.auth import AuthPrincipal, AuthServiceError
from teacher_assignments import TeacherSubjectAssignment


def require_assignment_admin(user: AuthPrincipal) -> None:
    if user.role != "admin":
        raise AuthServiceError(403, "Назначать предметы учителям может только администратор.")


async def _assignment_rows(statement, db: AsyncSession):
    try:
        return (await db.execute(statement)).all()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise AuthServiceError(
            503, "Назначения предметов недоступны. Администратору нужно применить миграцию teacher_subject_assignments и перезапустить сервер.",
        ) from exc


async def teacher_subject_ids(user: AuthPrincipal, db: AsyncSession) -> list[int]:
    if user.role != "teacher" or user.teacher_id is None:
        raise AuthServiceError(403, "Доступ предметного учителя не настроен.")
    rows = await _assignment_rows(select(TeacherSubjectAssignment.subject_id).where(
        TeacherSubjectAssignment.teacher_id == user.teacher_id,
        TeacherSubjectAssignment.organization_id == user.organization_id,
    ), db)
    return [row[0] for row in rows]


async def teacher_subject_options(user: AuthPrincipal, db: AsyncSession) -> list[dict]:
    require_assignment_admin(user)
    await _assignment_rows(select(TeacherSubjectAssignment.subject_id).limit(0), db)
    rows = (await db.execute(select(Subject.id, Subject.name, Subject.grade).order_by(
        Subject.name, Subject.grade, Subject.id,
    ))).all()
    return [{"id": subject_id, "name": name, "grade": grade} for subject_id, name, grade in rows]


async def subjects_by_teacher(user: AuthPrincipal, db: AsyncSession) -> dict[int, list[dict]]:
    require_assignment_admin(user)
    rows = await _assignment_rows(select(
        TeacherSubjectAssignment.teacher_id, Subject.id, Subject.name, Subject.grade,
    ).join(Subject, Subject.id == TeacherSubjectAssignment.subject_id).where(
        TeacherSubjectAssignment.organization_id == user.organization_id,
    ).order_by(Subject.name, Subject.grade, Subject.id), db)
    result: dict[int, list[dict]] = {}
    for teacher_id, subject_id, name, grade in rows:
        result.setdefault(teacher_id, []).append({"id": subject_id, "name": name, "grade": grade})
    return result


async def validate_teacher_assignments(
    user: AuthPrincipal, subject_ids: list[int], classroom_ids: list[int], db: AsyncSession,
    *, allow_empty: bool = False,
) -> tuple[list[int], list[int]]:
    require_assignment_admin(user)
    subjects, classrooms = sorted(set(subject_ids)), sorted(set(classroom_ids))
    if (not subjects and not allow_empty) or len(subjects) > 200 or len(classrooms) > 200:
        raise AuthServiceError(422, "Выберите предмет и класс из загруженной программы (не более 200 назначений).")
    # Check deployment readiness before creating a remote Auth user.
    await _assignment_rows(select(TeacherSubjectAssignment.subject_id).limit(0), db)
    existing = set((await db.scalars(select(Subject.id).where(Subject.id.in_(subjects)))).all()) if subjects else set()
    if existing != set(subjects):
        raise AuthServiceError(422, "Один из выбранных предметов больше не существует. Обновите список.")
    if classrooms:
        available = set((await db.scalars(select(Classroom.id).where(
            Classroom.id.in_(classrooms), Classroom.organization_id == user.organization_id,
            Classroom.status == "active",
        ))).all())
        if available != set(classrooms):
            raise AuthServiceError(422, "Один из выбранных классов недоступен.")
    return subjects, classrooms


def add_subject_assignments(user: AuthPrincipal, profile: Profile, subject_ids: list[int], db: AsyncSession) -> None:
    for subject_id in subject_ids:
        db.add(TeacherSubjectAssignment(
            teacher_id=profile.teacher_id, subject_id=subject_id,
            organization_id=user.organization_id, assigned_by_profile_id=user.profile_id,
        ))
    db.add(AccountEvent(
        organization_id=user.organization_id, actor_profile_id=user.profile_id,
        target_profile_id=profile.id, event_type="teacher_subjects_assigned",
        metadata_json={"subject_ids": subject_ids},
    ))


async def replace_teacher_subjects(
    user: AuthPrincipal, *, teacher_profile_id: int, subject_ids: list[int], db: AsyncSession,
) -> None:
    require_assignment_admin(user)
    subjects, _ = await validate_teacher_assignments(user, subject_ids, [], db, allow_empty=True)
    profile = await db.scalar(select(Profile).where(
        Profile.id == teacher_profile_id, Profile.organization_id == user.organization_id,
        Profile.role == "teacher", Profile.teacher_id.is_not(None),
    ).with_for_update())
    if profile is None:
        raise AuthServiceError(404, "Учитель не найден.")
    await db.execute(delete(TeacherSubjectAssignment).where(
        TeacherSubjectAssignment.teacher_id == profile.teacher_id,
        TeacherSubjectAssignment.organization_id == user.organization_id,
    ))
    add_subject_assignments(user, profile, subjects, db)
    await db.commit()
