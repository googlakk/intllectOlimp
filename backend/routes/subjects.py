from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.http_errors import raise_http_error
from services.catalog import list_sections, list_subject_outline, list_subjects, list_topics
from services.grade_access import GradeAccessError
from auth_dependencies import require_roles
from services.auth import AuthPrincipal
from services.educator_access import (
    require_section_management,
    require_subject_management,
)
from services.teacher_assignments import teacher_subject_ids

router = APIRouter(prefix="/api", tags=["subjects"])


@router.get("/subjects")
async def subjects(
    _student_id: int | None = Query(default=None, ge=1, alias="student_id"),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        subject_ids = await teacher_subject_ids(user, db) if user.role == "teacher" else None
        return await list_subjects(
            db,
            student_id=user.student_id if user.role == "student" else None,
            subject_ids=subject_ids,
        )
    except GradeAccessError as exc:
        raise_http_error(exc)


@router.get("/subjects/{subject_id}/sections")
async def sections(
    subject_id: int,
    _student_id: int | None = Query(default=None, ge=1, alias="student_id"),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        if user.role == "teacher":
            await require_subject_management(user, subject_id, db)
        return await list_sections(subject_id, db, student_id=user.student_id if user.role == "student" else None)
    except GradeAccessError as exc:
        raise_http_error(exc)


@router.get("/subjects/{subject_id}/outline")
async def subject_outline(
    subject_id: int,
    include_archived: bool = False,
    _student_id: int | None = Query(default=None, ge=1, alias="student_id"),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        if user.role == "teacher":
            await require_subject_management(user, subject_id, db)
        return await list_subject_outline(subject_id, db, student_id=user.student_id if user.role == "student" else None, include_archived=include_archived and user.role != "student")
    except GradeAccessError as exc:
        raise_http_error(exc)


@router.get("/sections/{section_id}/topics")
async def topics(
    section_id: int,
    include_archived: bool = False,
    _student_id: int | None = Query(default=None, ge=1, alias="student_id"),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        if user.role == "teacher":
            await require_section_management(user, section_id, db)
        return await list_topics(section_id, db, student_id=user.student_id if user.role == "student" else None, include_archived=include_archived and user.role != "student")
    except GradeAccessError as exc:
        raise_http_error(exc)
