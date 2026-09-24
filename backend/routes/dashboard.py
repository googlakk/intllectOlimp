from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.dashboard import get_dashboard_overview, get_dashboard_students, get_student_learning_report
from errors import ApplicationError
from routes.http_errors import raise_http_error
from auth_dependencies import require_roles
from services.auth import AuthPrincipal

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    return await get_dashboard_overview(db, user=user)


@router.get("/students")
async def student_rows(
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    return await get_dashboard_students(db, user=user)


@router.get("/students/{student_id}/learning")
async def student_learning(student_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await get_student_learning_report(student_id, db, user=user)
    except ApplicationError as exc:
        raise_http_error(exc)
