"""HTTP-контракт подготовки блока по подтверждённому источнику."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth_dependencies import require_roles
from database import get_db
from routes.http_errors import raise_http_error
from services.auth import AuthPrincipal
from services.educator_access import require_lesson_management
from services.lesson_components import component_context, insert_component, prepare_component
from services.lessons import LessonServiceError, serialize_lesson

router = APIRouter(prefix="/api/lessons", tags=["lesson-components"])


class PrepareInput(BaseModel):
    component: str = Field(min_length=1, max_length=100)
    objective_id: str = Field(min_length=1, max_length=200)
    after_index: int | None = Field(default=None, ge=-1)
    base_revision: str = Field(min_length=1, max_length=100)
    source_item_id: int | None = Field(default=None, ge=1)
    source_section_id: int | None = Field(default=None, ge=1)
    model: str | None = Field(default=None, max_length=200)


class InsertInput(BaseModel):
    block: dict[str, Any]
    after_index: int | None = Field(default=None, ge=-1)
    base_revision: str = Field(min_length=1, max_length=100)
    context_fingerprint: str = Field(min_length=1, max_length=8192)
    request_id: UUID


@router.get("/{lesson_id}/components/context")
async def context(lesson_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                  db: AsyncSession = Depends(get_db)):
    await require_lesson_management(user, lesson_id, db)
    try:
        return await component_context(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.post("/{lesson_id}/components/prepare")
async def prepare(lesson_id: int, payload: PrepareInput,
                  user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                  db: AsyncSession = Depends(get_db)):
    await require_lesson_management(user, lesson_id, db)
    try:
        return await prepare_component(lesson_id, **payload.model_dump(), db=db)
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.post("/{lesson_id}/components/insert")
async def insert(lesson_id: int, payload: InsertInput,
                 user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                 db: AsyncSession = Depends(get_db)):
    await require_lesson_management(user, lesson_id, db)
    try:
        lesson = await insert_component(lesson_id, **payload.model_dump(mode="json"), db=db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)
