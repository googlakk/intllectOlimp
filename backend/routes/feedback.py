from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth_dependencies import require_roles
from database import get_db
from errors import ApplicationError
from routes.http_errors import raise_http_error
from services.auth import AuthPrincipal
from services.feedback import list_lesson_feedback, submit_lesson_feedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
admin_router = APIRouter(prefix="/api/admin/feedback", tags=["feedback"])


class LessonFeedbackInput(BaseModel):
    topic_id: int
    rating: int | None = Field(default=None, ge=1, le=5)
    had_errors: bool | None = None
    comment: str | None = Field(default=None, max_length=4000)


@router.post("")
async def submit(
    payload: LessonFeedbackInput,
    user: AuthPrincipal = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await submit_lesson_feedback(
            user, db, topic_id=payload.topic_id, rating=payload.rating, had_errors=payload.had_errors, comment=payload.comment,
        )
    except ApplicationError as exc:
        raise_http_error(exc)


@admin_router.get("")
async def feedback_list(
    only_errors: bool = False,
    subject_id: int | None = None,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await list_lesson_feedback(user, db, only_errors=only_errors, subject_id=subject_id)
