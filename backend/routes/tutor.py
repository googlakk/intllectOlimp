from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth_dependencies import require_roles
from database import get_db
from routes.http_errors import raise_http_error
from services.auth import AuthPrincipal, AuthServiceError
from services.lessons import LessonServiceError
from services.tutor import TurnInput, TutorServiceError, get_tutor_session, take_tutor_turn

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class TutorTurnInput(BaseModel):
    topic_id: int = Field(ge=1)
    block_index: int = Field(ge=0)
    question_index: int | None = Field(default=None, ge=0)
    step_index: int | None = Field(default=None, ge=0)
    event: Literal["answer_submitted", "hint_requested", "idle", "message"]
    message: str | None = Field(default=None, max_length=500)
    student_value: str | None = Field(default=None, max_length=200)
    hint_level: int | None = Field(default=None, ge=0, le=20)
    client_outcome: Literal["correct", "incorrect", "wrong_unit"] | None = None


def _student_id(user: AuthPrincipal) -> int:
    if user.student_id is None:
        raise_http_error(AuthServiceError(status_code=403, detail="Помощник доступен только ученику"))
    return user.student_id


@router.post("/turn")
async def tutor_turn(
    payload: TutorTurnInput,
    user: AuthPrincipal = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await take_tutor_turn(
            student_id=_student_id(user), organization_id=user.organization_id, grade=user.grade,
            payload=TurnInput(**payload.model_dump()), db=db,
        )
    except (TutorServiceError, LessonServiceError) as exc:
        raise_http_error(exc)


@router.get("/session")
async def tutor_session(
    topic_id: int = Query(ge=1),
    user: AuthPrincipal = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_tutor_session(
            student_id=_student_id(user), organization_id=user.organization_id, topic_id=topic_id, db=db,
        )
    except (TutorServiceError, LessonServiceError) as exc:
        raise_http_error(exc)
