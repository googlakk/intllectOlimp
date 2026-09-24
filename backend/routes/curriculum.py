from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.http_errors import raise_http_error
from services.curriculum_graph import (
    CurriculumGraphError,
    get_student_curriculum_map,
    get_subject_graph,
    rebuild_subject_graph,
)
from services.accounts import require_student_visibility
from auth_dependencies import require_roles
from services.auth import AuthPrincipal
from services.educator_access import require_subject_management

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.post("/subjects/{subject_id}/build")
async def build_subject_graph(
    subject_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_subject_management(user, subject_id, db)
    try:
        result = await rebuild_subject_graph(subject_id, db)
        await db.commit()
        return result
    except CurriculumGraphError as exc:
        await db.rollback()
        raise_http_error(exc)


@router.get("/subjects/{subject_id}/graph")
async def subject_graph(
    subject_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_subject_management(user, subject_id, db)
    try:
        return await get_subject_graph(subject_id, db)
    except CurriculumGraphError as exc:
        raise_http_error(exc)


@router.get("/students/{student_id}/map")
async def student_map(
    student_id: int,
    subject_id: int | None = Query(default=None, ge=1),
    refresh: bool = Query(default=False),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    await require_student_visibility(user, student_id, db)
    try:
        return await get_student_curriculum_map(student_id, db, subject_id=subject_id, refresh=refresh)
    except CurriculumGraphError as exc:
        raise_http_error(exc)
