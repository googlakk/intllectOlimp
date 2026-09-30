from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from languages import Language
from routes.http_errors import raise_http_error
from services.lessons import (
    LessonServiceError,
    create_lesson_draft,
    delete_lesson_record,
    generate_lesson_draft,
    get_lesson_by_topic,
    get_student_lesson_manifest,
    get_lesson_quality,
    publish_lesson,
    serialize_lesson,
    set_lesson_avatar_profile,
    unpublish_lesson,
    update_lesson_blocks,
)
from auth_dependencies import require_roles
from services.auth import AuthPrincipal, AuthServiceError
from services.educator_access import require_lesson_management, require_topic_management

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class GenerateInput(BaseModel):
    topic_id: int
    teacher_id: int
    # id варианта из /api/ai/models; пусто — модель по умолчанию.
    model: str | None = Field(default=None, max_length=200)
    content_language: Language | None = None


class BlocksInput(BaseModel):
    blocks: list[dict[str, Any]]


class LessonDocumentInput(BaseModel):
    lesson_document: dict[str, Any]


class PublishInput(BaseModel):
    teacher_id: int
    acknowledge_warnings: bool = False
    # Учитель ознакомился с недочётами и публикует под свою ответственность.
    override_errors: bool = False


class AvatarProfileSelectionInput(BaseModel):
    profile_id: int


@router.post("/draft")
async def create_draft(
    payload: GenerateInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = payload.teacher_id if user.role == "admin" else user.teacher_id
    if teacher_id is None:
        raise AuthServiceError(status_code=403, detail="Профиль учителя не связан с аккаунтом.")
    await require_topic_management(user, payload.topic_id, db)
    try:
        lesson = await create_lesson_draft(payload.topic_id, teacher_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.post("/generate")
async def generate(
    payload: GenerateInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = payload.teacher_id if user.role == "admin" else user.teacher_id
    if teacher_id is None:
        raise AuthServiceError(status_code=403, detail="Профиль учителя не связан с аккаунтом.")
    await require_topic_management(user, payload.topic_id, db)
    try:
        lesson = await generate_lesson_draft(
            topic_id=payload.topic_id,
            teacher_id=teacher_id,
            db=db,
            model_choice=payload.model,
            content_language=payload.content_language,
        )
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.get("/{topic_id}/manifest")
async def student_manifest(
    topic_id: int,
    user: AuthPrincipal = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    if user.student_id is None:
        raise AuthServiceError(status_code=403, detail="Профиль ученика не связан с аккаунтом.")
    try:
        return await get_student_lesson_manifest(
            topic_id=topic_id,
            student_id=user.student_id,
            db=db,
        )
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.get("/{topic_id}")
async def by_topic(
    topic_id: int,
    role: str | None = Query(default=None),
    student_id: int | None = Query(default=None, ge=1),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    effective_role = user.role
    effective_student_id = user.student_id if user.role == "student" else None
    if user.role == "teacher":
        await require_topic_management(user, topic_id, db)
    try:
        lesson = await get_lesson_by_topic(topic_id, effective_role, db, student_id=effective_student_id)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/blocks")
async def update_blocks(
    lesson_id: int,
    payload: BlocksInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_lesson_management(user, lesson_id, db)
    try:
        lesson = await update_lesson_blocks(lesson_id, payload.blocks, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/avatar")
async def select_avatar_profile(
    lesson_id: int,
    payload: AvatarProfileSelectionInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_lesson_management(user, lesson_id, db)
    try:
        lesson = await set_lesson_avatar_profile(lesson_id, payload.profile_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.get("/{lesson_id}/quality")
async def lesson_quality(
    lesson_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_lesson_management(user, lesson_id, db)
    try:
        return await get_lesson_quality(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.put("/{lesson_id}/publish")
async def publish(
    lesson_id: int,
    payload: PublishInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = payload.teacher_id if user.role == "admin" else user.teacher_id
    if teacher_id is None:
        raise AuthServiceError(status_code=403, detail="Профиль учителя не связан с аккаунтом.")
    await require_lesson_management(user, lesson_id, db)
    try:
        lesson = await publish_lesson(
            lesson_id=lesson_id,
            teacher_id=teacher_id,
            acknowledge_warnings=payload.acknowledge_warnings,
            db=db,
            override_errors=payload.override_errors,
        )
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.put("/{lesson_id}/unpublish")
async def unpublish(
    lesson_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_lesson_management(user, lesson_id, db)
    try:
        lesson = await unpublish_lesson(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
    return serialize_lesson(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson(
    lesson_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await require_lesson_management(user, lesson_id, db)
    try:
        return await delete_lesson_record(lesson_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)
