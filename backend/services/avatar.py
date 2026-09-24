"""Persistent avatar profiles and asynchronous HeyGen generation jobs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from llm.heygen import HeyGenProvider
from models import AvatarProfile, GenerationJob, LessonAsset, LessonVersion
from narration import spoken_text
from services.lessons import (LessonServiceError, clear_lesson_manifest_cache_for_version, ensure_lesson_media_draft)
from storage import SupabaseStorage


class AvatarServiceError(ApplicationError):
    pass


MAX_CUSTOM_AVATAR_BYTES = 10 * 1024 * 1024
CUSTOM_AVATAR_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _serialize(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


async def list_profiles(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(AvatarProfile).where(AvatarProfile.is_active.is_(True)))).all()
    return [_serialize(row) for row in rows]


async def list_avatar_jobs(lesson_version_id: int, db: AsyncSession) -> list[GenerationJob]:
    return list((await db.scalars(select(GenerationJob).where(
        GenerationJob.lesson_version_id == lesson_version_id,
        GenerationJob.provider == "heygen",
        GenerationJob.job_type == "avatar_video",
    ).order_by(GenerationJob.id))).all())


async def create_profile(payload: Any, db: AsyncSession) -> AvatarProfile:
    profile = AvatarProfile(
        name=payload.name,
        provider_avatar_id=payload.avatar_id,
        provider_voice_id=payload.voice_id,
        supported_languages=payload.supported_languages,
        voice_settings=payload.voice_settings,
        consent_metadata=payload.consent_metadata,
        preview_image_url=payload.preview_image_url,
        preview_audio_url=payload.preview_audio_url,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


def validate_custom_avatar_image(data: bytes, content_type: str | None) -> str:
    if not data:
        raise AvatarServiceError(status_code=422, detail="Выберите фотографию")
    if len(data) > MAX_CUSTOM_AVATAR_BYTES:
        raise AvatarServiceError(status_code=413, detail="Фотография должна быть не больше 10 МБ")
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    signatures = CUSTOM_AVATAR_TYPES.get(normalized)
    if signatures is None or not any(data.startswith(signature) for signature in signatures):
        raise AvatarServiceError(status_code=422, detail="Поддерживаются только PNG и JPEG")
    return normalized


async def create_custom_photo_profile(
    *,
    name: str,
    teacher_id: int,
    image: bytes,
    content_type: str | None,
    filename: str,
    rights_confirmed: bool,
    voice_id: str | None,
    db: AsyncSession,
    provider: HeyGenProvider | None = None,
) -> AvatarProfile:
    from models import Teacher

    if not name.strip():
        raise AvatarServiceError(status_code=422, detail="Укажите имя аватара")
    if not rights_confirmed:
        raise AvatarServiceError(status_code=422, detail="Подтвердите право использовать изображение")
    if await db.get(Teacher, teacher_id) is None:
        raise AvatarServiceError(status_code=404, detail="Учитель не найден")
    media_type = validate_custom_avatar_image(image, content_type)
    digest = hashlib.sha256(image).hexdigest()
    look = await (provider or HeyGenProvider()).create_photo_avatar(
        name=name.strip(),
        image=image,
        media_type=media_type,
        idempotency_key=f"photo-avatar:{teacher_id}:{digest}",
    )
    now = datetime.now(timezone.utc).isoformat()
    profile = AvatarProfile(
        name=name.strip(),
        provider="heygen",
        provider_avatar_id=look.id,
        provider_voice_id=voice_id or look.default_voice_id or None,
        supported_languages=["ru", "ky"],
        consent_metadata={
            "source": "teacher_photo_upload",
            "api_version": "v3",
            "avatar_type": "photo_avatar",
            "status": look.status,
            "group_id": look.group_id,
            "preview_video_url": look.preview_video_url or None,
            "rights_confirmed": True,
            "confirmed_by_teacher_id": teacher_id,
            "confirmed_at": now,
            "source_filename": filename,
            "source_sha256": digest,
            "error": look.error,
        },
        preview_image_url=look.preview_image_url or None,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile_voice(profile_id: int, voice_id: str, db: AsyncSession) -> AvatarProfile:
    profile = await db.get(AvatarProfile, profile_id)
    if profile is None or not profile.is_active:
        raise AvatarServiceError(status_code=404, detail="Профиль аватара не найден")
    profile.provider_voice_id = voice_id
    await db.commit()
    await db.refresh(profile)
    return profile


async def refresh_custom_photo_profile(
    profile_id: int,
    db: AsyncSession,
    provider: HeyGenProvider | None = None,
) -> AvatarProfile:
    profile = await db.get(AvatarProfile, profile_id)
    if profile is None or not profile.is_active:
        raise AvatarServiceError(status_code=404, detail="Профиль аватара не найден")
    metadata = dict(profile.consent_metadata or {})
    if metadata.get("source") != "teacher_photo_upload":
        return profile
    look = await (provider or HeyGenProvider()).get_avatar_look(profile.provider_avatar_id)
    metadata.update({
        "status": look.status,
        "group_id": look.group_id or metadata.get("group_id"),
        "preview_video_url": look.preview_video_url or metadata.get("preview_video_url"),
        "error": look.error,
    })
    profile.consent_metadata = metadata
    if look.preview_image_url:
        profile.preview_image_url = look.preview_image_url
    if not profile.provider_voice_id and look.default_voice_id:
        profile.provider_voice_id = look.default_voice_id
    await db.commit()
    await db.refresh(profile)
    return profile


async def _avatar_draft_version(version_id: int, db: AsyncSession) -> int:
    try:
        return await ensure_lesson_media_draft(version_id, db)
    except LessonServiceError as exc:
        raise AvatarServiceError(status_code=exc.status_code, detail=exc.detail) from exc


async def submit_avatar_job(payload: Any, db: AsyncSession,
                            provider: HeyGenProvider | None = None) -> GenerationJob:
    if await db.get(LessonVersion, payload.lesson_version_id) is None:
        raise AvatarServiceError(status_code=404, detail="Версия урока не найдена")
    profile = await db.get(AvatarProfile, payload.profile_id)
    if profile is None or not profile.is_active:
        raise AvatarServiceError(status_code=404, detail="Профиль аватара не найден")
    metadata = profile.consent_metadata or {}
    if metadata.get("source") == "teacher_photo_upload" and metadata.get("status") != "completed":
        raise AvatarServiceError(
            status_code=409,
            detail="Фото-аватар ещё не готов. Дождитесь завершения обработки HeyGen",
        )
    if not profile.provider_voice_id:
        raise AvatarServiceError(status_code=422, detail="Для аватара не выбран голос")
    narration = spoken_text(payload.script)
    if not narration:
        raise AvatarServiceError(status_code=422, detail="Реплика аватара не содержит текста для озвучивания")
    draft_version_id = await _avatar_draft_version(payload.lesson_version_id, db)
    request = {
        "lesson_version_id": draft_version_id,
        "scene_id": payload.scene_id,
        "beat_id": getattr(payload, "beat_id", None),
        "cue_id": getattr(payload, "cue_id", None),
        "profile_id": payload.profile_id,
        "avatar_id": profile.provider_avatar_id,
        "voice_id": profile.provider_voice_id,
        "script": narration,
        "locale": payload.locale,
        "voice_settings": profile.voice_settings or {},
        "api_version": (profile.consent_metadata or {}).get("api_version", "v2"),
    }
    fingerprint = request_hash(request)
    existing = await db.scalar(select(GenerationJob).where(
        GenerationJob.provider == "heygen", GenerationJob.request_hash == fingerprint,
    ))
    if existing is not None:
        return existing
    settings = profile.voice_settings or {}
    submitted = await (provider or HeyGenProvider()).create_video(
        avatar_id=profile.provider_avatar_id,
        voice_id=profile.provider_voice_id,
        script=narration,
        locale=payload.locale,
        speed=float(settings.get("speed", 1.0)),
        pitch=float(settings.get("pitch", 0.0)),
        api_version=str(request["api_version"]),
    )
    job = GenerationJob(
        lesson_version_id=draft_version_id,
        scene_id=payload.scene_id,
        provider="heygen",
        job_type="avatar_video",
        external_job_id=submitted.id,
        request_hash=fingerprint,
        status="submitted",
        attempts=1,
        request_payload=request,
        result_payload=submitted.raw,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def refresh_avatar_job(job_id: int, db: AsyncSession,
                             provider: HeyGenProvider | None = None,
                             storage: SupabaseStorage | None = None) -> GenerationJob:
    job = await db.get(GenerationJob, job_id)
    if job is None or job.provider != "heygen" or not job.external_job_id:
        raise AvatarServiceError(status_code=404, detail="Задание HeyGen не найдено")
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    result = await (provider or HeyGenProvider()).get_video(
        job.external_job_id,
        api_version=str((job.request_payload or {}).get("api_version", "v2")),
    )
    job.result_payload = result.raw
    if result.status == "completed" and result.video_url:
        job.lesson_version_id = await _avatar_draft_version(job.lesson_version_id, db)
        asset_url, size_bytes, bucket, path = result.video_url, None, None, None
        storage_client = storage or SupabaseStorage()
        if storage_client.configured():
            bucket = "lesson-assets"
            path = f"lessons/{job.lesson_version_id}/{job.scene_id or 'avatar'}/{result.id}.mp4"
            asset_url, size_bytes = await storage_client.copy_from_url(
                source_url=result.video_url, bucket=bucket, path=path, content_type="video/mp4",
            )
        db.add(LessonAsset(
            lesson_version_id=job.lesson_version_id,
            generation_job_id=job.id,
            scene_id=job.scene_id,
            kind="avatar_video",
            provider="heygen",
            provider_asset_id=result.id,
            storage_bucket=bucket,
            storage_path=path,
            source_url=asset_url,
            mime_type="video/mp4",
            size_bytes=size_bytes,
            duration_ms=int(result.duration * 1000) if result.duration is not None else None,
            status="ready",
            metadata_json={
                "thumbnail_url": result.thumbnail_url,
                "beat_id": (job.request_payload or {}).get("beat_id"),
                "cue_id": (job.request_payload or {}).get("cue_id"),
                "pedagogical_role": "avatar_explanation",
                "placement": "avatar",
            },
        ))
        await clear_lesson_manifest_cache_for_version(job.lesson_version_id, db)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
    elif result.status == "failed":
        job.status = "failed"
        job.error = result.raw
        job.completed_at = datetime.now(timezone.utc)
    else:
        job.status = "processing"
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


async def refresh_avatar_jobs(lesson_version_id: int, db: AsyncSession) -> list[GenerationJob]:
    jobs = await list_avatar_jobs(lesson_version_id, db)
    provider = HeyGenProvider()
    storage = SupabaseStorage()
    for job in jobs:
        if job.status not in {"completed", "failed", "cancelled"}:
            await refresh_avatar_job(job.id, db, provider=provider, storage=storage)
    return await list_avatar_jobs(lesson_version_id, db)


serialize_avatar_profile = _serialize
serialize_generation_job = _serialize
