import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth_dependencies import require_roles
from llm import LLMError
from llm.catalog import ModelChoiceError, resolve_image_choice
from llm.media import build_educational_media_prompt, media_provider
from media_planner import build_block_media_plan, build_lesson_media_plan
from models import GeneratedLesson, GenerationJob, LessonAsset, LessonVersion
from services.avatar import request_hash
from services.auth import AuthPrincipal
from services.educator_access import require_lesson_management
from services.lessons import LessonServiceError, clear_lesson_manifest_cache_for_version, ensure_lesson_media_draft
from routes.http_errors import raise_http_error
from services.media_access import require_generation_job_media_access, require_lesson_version_media_access
from storage import SupabaseStorage

router = APIRouter(prefix="/api/media", tags=["media"])
content_router = APIRouter(prefix="/api/media", tags=["media-content"])


class EducationalImageInput(BaseModel):
    lesson_version_id: int | None = Field(default=None, ge=1)
    scene_id: str | None = Field(default=None, max_length=160)
    block_id: str | None = Field(default=None, max_length=160)
    beat_id: str | None = Field(default=None, max_length=160)
    slide_id: str | None = Field(default=None, max_length=160)
    media_slot_id: str | None = Field(default=None, max_length=160)
    placement: str | None = Field(default="inline", max_length=80)
    topic: str = Field(min_length=1)
    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    concept: str | None = None
    learning_goal: str | None = None
    visual_form: str | None = None
    visual_intent: str | None = "structure"
    pedagogical_role: str | None = "conceptual explanation support"
    misconception_to_avoid: str | None = None
    curriculum_context: str | None = None
    source_context: str | None = None
    must_include: list[str] = Field(default_factory=list, max_length=6)
    avoid: list[str] = Field(default_factory=list, max_length=6)
    success_check: str | None = None
    prompt: str | None = None
    style: str | None = None
    labels_language: str = "ru"
    aspect_ratio: str = "16:9"
    resolution: str = "1K"
    quality: str = "medium"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    model: str | None = None


class EducationalVideoInput(BaseModel):
    lesson_version_id: int | None = Field(default=None, ge=1)
    scene_id: str | None = Field(default=None, max_length=160)
    block_id: str | None = Field(default=None, max_length=160)
    beat_id: str | None = Field(default=None, max_length=160)
    slide_id: str | None = Field(default=None, max_length=160)
    media_slot_id: str | None = Field(default=None, max_length=160)
    placement: str | None = Field(default="inline", max_length=80)
    topic: str = Field(min_length=1)
    subject: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    concept: str | None = None
    learning_goal: str | None = None
    visual_form: str | None = None
    visual_intent: str | None = "process"
    pedagogical_role: str | None = "dynamic explanation support"
    misconception_to_avoid: str | None = None
    curriculum_context: str | None = None
    source_context: str | None = None
    must_include: list[str] = Field(default_factory=list, max_length=6)
    avoid: list[str] = Field(default_factory=list, max_length=6)
    success_check: str | None = None
    prompt: str | None = None
    style: str | None = None
    labels_language: str = "ru"
    aspect_ratio: str = "16:9"
    duration: int = Field(default=6, ge=2, le=20)
    resolution: str = "720p"
    generate_audio: bool = False
    model: str | None = None


class LessonMediaPlanInput(BaseModel):
    lesson_id: int = Field(ge=1)
    # Автоиллюстрации при генерации урока: только картинки, без видео.
    images_only: bool = False


class BlockMediaPlanInput(BaseModel):
    lesson_id: int = Field(ge=1)
    block_index: int = Field(ge=0)
    slide_index: int | None = Field(default=None, ge=0)
    preferred_kind: Literal["image", "video"] | None = None


@router.post("/lesson-plan")
async def lesson_media_plan(
    payload: LessonMediaPlanInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await require_lesson_management(user, payload.lesson_id, db)
    lesson = await db.get(GeneratedLesson, payload.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Урок не найден")
    document: dict[str, Any] = {}
    if lesson.active_version_id:
        version = await db.get(LessonVersion, lesson.active_version_id)
        if version is not None and isinstance(version.lesson_document, dict):
            document = version.lesson_document
    return build_lesson_media_plan(
        lesson.blocks or [], lesson.lesson_metadata or {}, document, allow_video=not payload.images_only,
    )


@router.post("/block-plan")
async def block_media_plan(
    payload: BlockMediaPlanInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await require_lesson_management(user, payload.lesson_id, db)
    lesson = await db.get(GeneratedLesson, payload.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Урок не найден")
    blocks = lesson.blocks or []
    if payload.block_index >= len(blocks):
        raise HTTPException(status_code=404, detail="Блок урока не найден")
    scene_id = None
    if lesson.active_version_id:
        version = await db.get(LessonVersion, lesson.active_version_id)
        document = version.lesson_document if version is not None and isinstance(version.lesson_document, dict) else {}
        for episode in document.get("episodes", []):
            for scene in episode.get("scenes", []):
                if scene.get("original_block_index") == payload.block_index:
                    scene_id = scene.get("id")
                    break
    return build_block_media_plan(
        block=blocks[payload.block_index], block_index=payload.block_index,
        metadata=lesson.lesson_metadata or {}, scene_id=scene_id,
        slide_index=payload.slide_index, preferred_kind=payload.preferred_kind,
    )


def _media_error(exc: LLMError) -> HTTPException:
    return HTTPException(status_code=502, detail={"message": str(exc), "provider": exc.provider, "model": exc.model})


def _provider():
    try:
        return media_provider()
    except LLMError as exc:
        raise _media_error(exc)


async def _media_draft_version(version_id: int, db: AsyncSession) -> int:
    try:
        return await ensure_lesson_media_draft(version_id, db)
    except LessonServiceError as exc:
        raise_http_error(exc)


@router.post("/image")
async def generate_image(
    payload: EducationalImageInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if payload.lesson_version_id:
        await require_lesson_version_media_access(user, payload.lesson_version_id, db)
        payload = payload.model_copy(update={"lesson_version_id": await _media_draft_version(payload.lesson_version_id, db)})
    prompt = build_educational_media_prompt(
        topic=payload.topic,
        media_kind="image",
        subject=payload.subject,
        grade=payload.grade,
        concept=payload.concept,
        style=payload.style,
        labels_language=payload.labels_language,
        prompt=payload.prompt,
        learning_goal=payload.learning_goal,
        visual_form=payload.visual_form,
        visual_intent=payload.visual_intent,
        pedagogical_role=payload.pedagogical_role,
        misconception_to_avoid=payload.misconception_to_avoid,
        curriculum_context=payload.curriculum_context,
        source_context=payload.source_context,
        must_include=payload.must_include,
        avoid=payload.avoid,
        success_check=payload.success_check,
    )
    try:
        selected_model = resolve_image_choice(payload.model)
    except ModelChoiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        provider = _provider()
        result = await provider.generate_image(
            prompt=prompt,
            model=selected_model,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            quality=payload.quality,
            output_format=payload.output_format,
        )
    except LLMError as exc:
        raise _media_error(exc)
    asset_url = result.url
    data_url = result.data_url
    if payload.lesson_version_id and SupabaseStorage.configured():
        if await db.get(LessonVersion, payload.lesson_version_id) is None:
            raise HTTPException(status_code=404, detail="Версия урока не найдена")
        raw = base64.b64decode(result.b64_json) if result.b64_json else b""
        if raw:
            digest = hashlib.sha256(raw).hexdigest()[:20]
            extension = "jpg" if payload.output_format == "jpeg" else payload.output_format
            path = f"lessons/{payload.lesson_version_id}/{payload.scene_id or 'media'}/{digest}.{extension}"
            asset_url, size_bytes = await SupabaseStorage().upload_bytes(
                content=raw, bucket="lesson-assets", path=path, content_type=result.media_type,
            )
            db.add(LessonAsset(
                lesson_version_id=payload.lesson_version_id, scene_id=payload.scene_id,
                kind="image", provider="openrouter", provider_asset_id=digest,
                storage_bucket="lesson-assets", storage_path=path, source_url=asset_url,
                mime_type=result.media_type, size_bytes=size_bytes, status="ready",
                metadata_json={
                    "prompt": result.prompt, "model": result.model,
                    "block_id": payload.block_id, "beat_id": payload.beat_id,
                    "slide_id": payload.slide_id, "media_slot_id": payload.media_slot_id,
                    "pedagogical_role": payload.pedagogical_role, "placement": payload.placement,
                    "learning_goal": payload.learning_goal, "success_check": payload.success_check,
                },
            ))
            await clear_lesson_manifest_cache_for_version(payload.lesson_version_id, db)
            await db.commit()
            data_url = ""
    # Persist the draft pointer even when a provider returned a remote URL.
    if payload.lesson_version_id:
        await db.commit()
    return {
        "kind": "image",
        "lesson_version_id": payload.lesson_version_id,
        "model": result.model,
        "prompt": result.prompt,
        "media_type": result.media_type,
        "b64_json": result.b64_json,
        "data_url": data_url,
        "url": asset_url,
        "usage": result.usage,
    }


@router.post("/video")
async def generate_video(
    payload: EducationalVideoInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if payload.lesson_version_id:
        await require_lesson_version_media_access(user, payload.lesson_version_id, db)
        payload = payload.model_copy(update={"lesson_version_id": await _media_draft_version(payload.lesson_version_id, db)})
    prompt = build_educational_media_prompt(
        topic=payload.topic,
        media_kind="video",
        subject=payload.subject,
        grade=payload.grade,
        concept=payload.concept,
        style=payload.style,
        labels_language=payload.labels_language,
        prompt=payload.prompt,
        learning_goal=payload.learning_goal,
        visual_form=payload.visual_form,
        visual_intent=payload.visual_intent,
        pedagogical_role=payload.pedagogical_role,
        misconception_to_avoid=payload.misconception_to_avoid,
        curriculum_context=payload.curriculum_context,
        source_context=payload.source_context,
        must_include=payload.must_include,
        avoid=payload.avoid,
        success_check=payload.success_check,
    )
    try:
        provider = _provider()
        job = await provider.submit_video(
            prompt=prompt,
            model=payload.model,
            aspect_ratio=payload.aspect_ratio,
            duration=payload.duration,
            resolution=payload.resolution,
            generate_audio=payload.generate_audio,
        )
    except LLMError as exc:
        raise _media_error(exc)
    generation_job_id = None
    if payload.lesson_version_id:
        if await db.get(LessonVersion, payload.lesson_version_id) is None:
            raise HTTPException(status_code=404, detail="Версия урока не найдена")
        fingerprint = request_hash({
            "provider": "openrouter", "lesson_version_id": payload.lesson_version_id,
            "scene_id": payload.scene_id, "prompt": prompt, "model": job.model,
            "block_id": payload.block_id, "beat_id": payload.beat_id,
            "slide_id": payload.slide_id, "media_slot_id": payload.media_slot_id,
        })
        record = await db.scalar(select(GenerationJob).where(
            GenerationJob.provider == "openrouter", GenerationJob.request_hash == fingerprint,
        ))
        if record is None:
            record = GenerationJob(
                lesson_version_id=payload.lesson_version_id, scene_id=payload.scene_id,
                provider="openrouter", job_type="educational_video",
                external_job_id=job.id, request_hash=fingerprint, status="submitted",
                attempts=1, request_payload={
                    "prompt": prompt, "model": job.model, "block_id": payload.block_id,
                    "beat_id": payload.beat_id, "slide_id": payload.slide_id,
                    "media_slot_id": payload.media_slot_id, "placement": payload.placement,
                    "pedagogical_role": payload.pedagogical_role,
                    "learning_goal": payload.learning_goal, "success_check": payload.success_check,
                },
                result_payload=job.__dict__,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
        generation_job_id = record.id
    return {
        "kind": "video",
        "lesson_version_id": payload.lesson_version_id,
        "id": job.id,
        "status": job.status,
        "model": job.model,
        "polling_url": job.polling_url,
        "generation_id": job.generation_id,
        "unsigned_urls": job.unsigned_urls,
        "content_url": _video_content_url(job),
        "usage": job.usage,
        "error": job.error,
        "prompt": prompt,
        "generation_job_id": generation_job_id,
    }


@router.get("/video/{job_id}")
async def video_status(
    job_id: str,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    record = await require_generation_job_media_access(user, job_id, db, provider="openrouter")
    try:
        provider = _provider()
        job = await provider.get_video_status(job_id)
    except LLMError as exc:
        raise _media_error(exc)
    content_url = _video_content_url(job)
    if record.provider == "openrouter":
        record.result_payload = job.__dict__
        record.status = "failed" if job.status == "failed" else "completed" if job.status == "completed" else "processing"
        record.updated_at = datetime.now(timezone.utc)
        if job.status == "completed" and SupabaseStorage.configured():
            existing = await db.scalar(select(LessonAsset).where(
                LessonAsset.generation_job_id == record.id, LessonAsset.status == "ready",
            ))
            if existing is None:
                record.lesson_version_id = await _media_draft_version(record.lesson_version_id, db)
                content = await provider.get_video_content(job_id, index=0)
                path = f"lessons/{record.lesson_version_id}/{record.scene_id or 'media'}/{job_id}.mp4"
                content_url, size_bytes = await SupabaseStorage().upload_bytes(
                    content=content.content, bucket="lesson-assets", path=path,
                    content_type=content.media_type or "video/mp4",
                )
                db.add(LessonAsset(
                    lesson_version_id=record.lesson_version_id, generation_job_id=record.id,
                    scene_id=record.scene_id, kind="video", provider="openrouter",
                    provider_asset_id=job_id, storage_bucket="lesson-assets", storage_path=path,
                    source_url=content_url, mime_type=content.media_type or "video/mp4",
                    size_bytes=size_bytes, status="ready",
                    metadata_json={
                        "model": job.model,
                        "block_id": (record.request_payload or {}).get("block_id"),
                        "beat_id": (record.request_payload or {}).get("beat_id"),
                        "slide_id": (record.request_payload or {}).get("slide_id"),
                        "media_slot_id": (record.request_payload or {}).get("media_slot_id"),
                        "placement": (record.request_payload or {}).get("placement"),
                        "pedagogical_role": (record.request_payload or {}).get("pedagogical_role"),
                        "learning_goal": (record.request_payload or {}).get("learning_goal"),
                        "success_check": (record.request_payload or {}).get("success_check"),
                    },
                ))
                await clear_lesson_manifest_cache_for_version(record.lesson_version_id, db)
            else:
                content_url = existing.source_url or content_url
            record.completed_at = datetime.now(timezone.utc)
        await db.commit()
    return {
        "kind": "video",
        "id": job.id,
        "status": job.status,
        "model": job.model,
        "polling_url": job.polling_url,
        "generation_id": job.generation_id,
        "unsigned_urls": job.unsigned_urls,
        "content_url": content_url,
        "usage": job.usage,
        "error": job.error,
    }


@content_router.get("/video/{job_id}/content")
async def video_content(
    job_id: str,
    index: int = 0,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await require_generation_job_media_access(user, job_id, db, provider="openrouter")
    try:
        provider = _provider()
        content = await provider.get_video_content(job_id, index=index)
    except LLMError as exc:
        raise _media_error(exc)
    return Response(
        content=content.content,
        media_type=content.media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


def _video_content_url(job: Any) -> str:
    if job.status != "completed":
        return ""
    return f"/api/media/video/{job.id}/content"
