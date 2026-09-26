import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from starlette.responses import RedirectResponse, StreamingResponse

from database import get_db
from auth_dependencies import require_roles
from llm import LLMError
from llm._http import AsyncClient, Timeout
from llm.heygen import HeyGenProvider, verify_webhook_signature
from models import GenerationJob, LessonAsset
from services.avatar import (
    avatar_video_urls,
    is_private_avatar_video,
    AvatarServiceError, create_custom_photo_profile, create_profile, list_avatar_jobs, list_profiles,
    refresh_avatar_job, refresh_avatar_jobs, refresh_custom_photo_profile, serialize_avatar_profile,
    serialize_generation_job, submit_avatar_job, update_profile_voice,
)
from services.auth import AuthPrincipal
from services.media_access import require_lesson_version_media_access
from routes.http_errors import raise_http_error

router = APIRouter(prefix="/api/avatar", tags=["avatar"])
asset_router = APIRouter(prefix="/api/avatar", tags=["avatar-assets"])
webhook_router = APIRouter(prefix="/api/avatar", tags=["avatar-webhooks"])


class AvatarProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    avatar_id: str = Field(min_length=1, max_length=255)
    voice_id: str | None = Field(default=None, max_length=255)
    supported_languages: list[str] = Field(default_factory=lambda: ["ru"])
    voice_settings: dict[str, Any] = Field(default_factory=dict)
    consent_metadata: dict[str, Any] = Field(default_factory=dict)
    preview_image_url: str | None = None
    preview_audio_url: str | None = None


class AvatarJobInput(BaseModel):
    lesson_version_id: int = Field(ge=1)
    scene_id: str = Field(min_length=1, max_length=160)
    beat_id: str | None = Field(default=None, max_length=160)
    cue_id: str | None = Field(default=None, max_length=160)
    profile_id: int = Field(ge=1)
    script: str = Field(min_length=1, max_length=5000)
    locale: str = Field(default="ru-RU", min_length=2, max_length=35)


class AvatarVoiceInput(BaseModel):
    voice_id: str = Field(min_length=1, max_length=255)


def serialize_avatar_cue_asset(asset: LessonAsset, video_url: str | None = None) -> dict[str, Any]:
    """video_url — прямая ссылка (подписанная или публичная): <video> играет её частями, без нашего сервера."""
    metadata = asset.metadata_json or {}
    return {
        "id": asset.id,
        "video_url": video_url or f"/api/avatar/assets/{asset.id}/stream",
        "poster_url": metadata.get("thumbnail_url"),
        "duration_ms": asset.duration_ms,
        "mime_type": asset.mime_type,
        "scene_id": asset.scene_id,
        "cue_id": metadata.get("cue_id"),
        "beat_id": metadata.get("beat_id"),
    }


@router.get("/catalog/avatars")
async def avatar_catalog(q: str | None = None) -> list[dict[str, Any]]:
    try:
        return await HeyGenProvider().list_avatars(query=q)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/catalog/voices")
async def voice_catalog(language: str | None = None) -> list[dict[str, Any]]:
    try:
        return await HeyGenProvider().list_voices(language=language)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/profiles")
async def profiles(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await list_profiles(db)


@router.post("/profiles")
async def add_profile(payload: AvatarProfileInput, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return serialize_avatar_profile(await create_profile(payload, db))


@router.post("/profiles/custom-photo")
async def add_custom_photo_profile(
    name: str = Form(min_length=1, max_length=255),
    teacher_id: int = Form(ge=1),
    rights_confirmed: bool = Form(),
    voice_id: str | None = Form(default=None, max_length=255),
    file: UploadFile = File(...),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    image = await file.read()
    try:
        profile = await create_custom_photo_profile(
            name=name,
            teacher_id=teacher_id if user.role == "admin" else user.teacher_id or 0,
            image=image,
            content_type=file.content_type,
            filename=file.filename or "avatar",
            rights_confirmed=rights_confirmed,
            voice_id=voice_id,
            db=db,
        )
        return serialize_avatar_profile(profile)
    except AvatarServiceError as exc:
        raise_http_error(exc)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.put("/profiles/{profile_id}/voice")
async def set_profile_voice(
    profile_id: int,
    payload: AvatarVoiceInput,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return serialize_avatar_profile(await update_profile_voice(profile_id, payload.voice_id, db))
    except AvatarServiceError as exc:
        raise_http_error(exc)


@router.post("/profiles/{profile_id}/refresh")
async def refresh_custom_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        return serialize_avatar_profile(await refresh_custom_photo_profile(profile_id, db))
    except AvatarServiceError as exc:
        raise_http_error(exc)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/jobs")
async def add_job(
    payload: AvatarJobInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await require_lesson_version_media_access(user, payload.lesson_version_id, db)
    try:
        return serialize_generation_job(await submit_avatar_job(payload, db))
    except AvatarServiceError as exc:
        raise_http_error(exc)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/jobs")
async def jobs(
    lesson_version_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await require_lesson_version_media_access(user, lesson_version_id, db)
    return [serialize_generation_job(job) for job in await list_avatar_jobs(lesson_version_id, db)]


@router.post("/jobs/refresh")
async def refresh_jobs(
    lesson_version_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await require_lesson_version_media_access(user, lesson_version_id, db)
    try:
        refreshed = await refresh_avatar_jobs(lesson_version_id, db)
        return [serialize_generation_job(job) for job in refreshed]
    except AvatarServiceError as exc:
        raise_http_error(exc)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/jobs/{job_id}")
async def job_status(
    job_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание аватара не найдено")
    await require_lesson_version_media_access(user, job.lesson_version_id, db)
    try:
        return serialize_generation_job(await refresh_avatar_job(job_id, db))
    except AvatarServiceError as exc:
        raise_http_error(exc)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@asset_router.get("/cue-asset")
async def avatar_cue_asset(
    lesson_version_id: int = Query(ge=1),
    cue_id: str = Query(min_length=1, max_length=160),
    scene_id: str | None = Query(default=None, max_length=160),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    await require_lesson_version_media_access(user, lesson_version_id, db)
    statement = select(LessonAsset).where(
        LessonAsset.lesson_version_id == lesson_version_id,
        LessonAsset.kind == "avatar_video",
        LessonAsset.status == "ready",
    ).order_by(LessonAsset.created_at.desc())
    if scene_id:
        statement = statement.where(LessonAsset.scene_id == scene_id)
    assets = (await db.scalars(statement)).all()
    for asset in assets:
        metadata = asset.metadata_json or {}
        if metadata.get("cue_id") == cue_id:
            urls = await _direct_urls([asset])
            return serialize_avatar_cue_asset(asset, urls.get(asset.id))
    return None


async def _direct_urls(assets: list[LessonAsset]) -> dict[int, str]:
    try:
        return await avatar_video_urls(assets)
    except LLMError:
        # Хранилище не подписало ссылки — отдаём через сервер (медленнее, но урок не ломается).
        return {}


@asset_router.get("/cue-assets")
async def avatar_cue_assets(
    lesson_version_id: int = Query(ge=1),
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Видео всех реплик урока одним запросом: при смене шага ссылка уже есть и ролик стартует сразу."""
    await require_lesson_version_media_access(user, lesson_version_id, db)
    assets = (await db.scalars(select(LessonAsset).where(
        LessonAsset.lesson_version_id == lesson_version_id,
        LessonAsset.kind == "avatar_video",
        LessonAsset.status == "ready",
    ).order_by(LessonAsset.created_at.desc()))).all()
    latest: dict[str, LessonAsset] = {}
    for asset in assets:
        cue = (asset.metadata_json or {}).get("cue_id")
        if cue and cue not in latest:
            latest[cue] = asset
    urls = await _direct_urls(list(latest.values()))
    return [serialize_avatar_cue_asset(asset, urls.get(asset.id)) for asset in latest.values()]


@asset_router.get("/assets/{asset_id}/stream")
async def avatar_asset_stream(
    asset_id: int,
    request: Request,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(LessonAsset, asset_id)
    if asset is None or asset.kind != "avatar_video" or not asset.source_url:
        raise HTTPException(status_code=404, detail="Видео аватара не найдено")
    await require_lesson_version_media_access(user, asset.lesson_version_id, db)
    if is_private_avatar_video(asset):
        # Закрытая корзина: отправляем браузер по подписанной ссылке прямо в хранилище.
        urls = await _direct_urls([asset])
        if not urls.get(asset.id):
            raise HTTPException(status_code=502, detail="Видео аватара временно недоступно")
        return RedirectResponse(urls[asset.id], status_code=307)
    client = AsyncClient(timeout=Timeout(120))
    upstream_headers = {}
    if request.headers.get("range"):
        upstream_headers["Range"] = request.headers["range"]
    upstream_request = client.build_request("GET", asset.source_url, headers=upstream_headers)
    upstream = await client.send(upstream_request, stream=True)
    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail="HeyGen-видео временно недоступно")

    async def cleanup() -> None:
        await upstream.aclose()
        await client.aclose()

    response_headers = {
        key: upstream.headers[key]
        for key in ("content-length", "content-range", "accept-ranges", "etag", "last-modified")
        if key in upstream.headers
    }
    response_headers["Cache-Control"] = "private, max-age=3600"
    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "video/mp4"),
        headers=response_headers,
        background=BackgroundTask(cleanup),
    )


@webhook_router.post("/webhooks/heygen")
async def heygen_webhook(request: Request, db: AsyncSession = Depends(get_db),
                         heygen_signature: str = Header(default="", alias="Heygen-Signature"),
                         heygen_timestamp: str = Header(default="", alias="Heygen-Timestamp")) -> dict[str, str]:
    raw = await request.body()
    if not verify_webhook_signature(raw, heygen_signature, heygen_timestamp):
        raise HTTPException(status_code=401, detail="Некорректная подпись HeyGen")
    event = json.loads(raw)
    data = event.get("data") if isinstance(event.get("data"), dict) else event
    external_id = data.get("video_id") or data.get("id")
    if isinstance(external_id, str):
        job = await db.scalar(select(GenerationJob).where(GenerationJob.external_job_id == external_id))
        if job is not None:
            await refresh_avatar_job(job.id, db)
    return {"status": "ok"}
