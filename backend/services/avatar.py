"""Persistent avatar profiles and asynchronous HeyGen generation jobs."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import ApplicationError
from llm import LLMError
from llm.heygen import AVATAR_ENGINE, HeyGenProvider
from models import AvatarProfile, GeneratedLesson, GenerationJob, LessonAsset, LessonVersion
from narration import spoken_text
from services.lessons import (LessonServiceError, clear_lesson_manifest_cache_for_version, ensure_lesson_media_draft)
from storage import SupabaseStorage


class AvatarServiceError(ApplicationError):
    pass


# Видео аватара — лицо учителя: храним в закрытой корзине, ученику — временная подписанная ссылка.
AVATAR_VIDEO_BUCKET = os.getenv("AVATAR_VIDEO_BUCKET", "avatar-videos")
SIGNED_URL_TTL_SEC = 3600
# Страница держит ссылки до 25 минут (useAvatarCueAssets): отдаём только те, которым жить заметно дольше.
SIGNED_URL_MIN_LEFT_SEC = 40 * 60
_signed_url_cache: dict[tuple[str, str], tuple[float, str]] = {}


def is_private_avatar_video(asset: Any) -> bool:
    return getattr(asset, "storage_bucket", None) == AVATAR_VIDEO_BUCKET and bool(getattr(asset, "storage_path", None))


async def avatar_video_urls(assets: list[Any], storage: SupabaseStorage | None = None) -> dict[int, str]:
    """Прямые ссылки на видео для <video>: закрытые — подписанные (одним запросом на все), старые публичные — как есть."""
    urls: dict[int, str] = {}
    now = time.monotonic()
    to_sign: list[Any] = []
    for asset in assets:
        if not is_private_avatar_video(asset):
            if asset.source_url and not str(asset.source_url).startswith("storage:"):
                urls[asset.id] = asset.source_url
            continue
        cached = _signed_url_cache.get((asset.storage_bucket, asset.storage_path))
        if cached and cached[0] - now > SIGNED_URL_MIN_LEFT_SEC:
            urls[asset.id] = cached[1]
        else:
            to_sign.append(asset)
    if to_sign:
        for key in [key for key, (expires_at, _url) in _signed_url_cache.items() if expires_at <= now]:
            _signed_url_cache.pop(key, None)
        signed = await (storage or SupabaseStorage()).create_signed_urls(
            bucket=AVATAR_VIDEO_BUCKET, paths=[asset.storage_path for asset in to_sign], expires_in=SIGNED_URL_TTL_SEC,
        )
        for asset in to_sign:
            url = signed.get(asset.storage_path)
            if url:
                _signed_url_cache[(asset.storage_bucket, asset.storage_path)] = (now + SIGNED_URL_TTL_SEC, url)
                urls[asset.id] = url
    return urls


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
    """Черновик урока, куда пишется видео. Номер версии мог устареть: первая реплика опубликованного урока
    создаёт черновик с новым номером, а редактор шлёт остальные со старым; учитель мог поправить урок,
    пока HeyGen делал видео. Тогда пишем в актуальный черновик того же урока, а не отказываем."""
    version = await db.get(LessonVersion, version_id)
    lesson = await db.get(GeneratedLesson, version.lesson_id) if version is not None and getattr(version, "lesson_id", None) else None
    if lesson is not None and lesson.active_version_id and lesson.active_version_id != version_id:
        version_id = lesson.active_version_id
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
    if request["api_version"] == "v3":
        # Движок — не часть отпечатка (готовый ролик не рендерим заново), но видно, чем рендерили.
        request["engine"] = AVATAR_ENGINE
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


def _cue_script(document: Any, cue_id: str | None) -> str | None:
    for episode in (document or {}).get("episodes", []) if isinstance(document, dict) else []:
        for scene in episode.get("scenes", []) if isinstance(episode, dict) else []:
            for cue in scene.get("avatar_cues", []) if isinstance(scene, dict) else []:
                if isinstance(cue, dict) and cue.get("id") == cue_id:
                    return spoken_text(str(cue.get("script") or ""))
    return None


async def published_version_with_same_cue(job: Any, db: AsyncSession) -> int | None:
    """Опубликованная версия урока, если в ней та же реплика с тем же текстом.

    Видео пишется в черновик, а ученик видит опубликованную версию — без переопубликации он видео
    не увидит. Если реплика в опубликованном уроке дословно та же, видео — лишь её озвучка, содержание
    урока не меняется: прикрепляем и туда. Текст реплики изменился — только черновик, учитель переопубликует.
    """
    payload = job.request_payload or {}
    cue_id, script = payload.get("cue_id"), payload.get("script")
    if not cue_id or not script:
        return None
    draft = await db.get(LessonVersion, job.lesson_version_id)
    lesson = await db.get(GeneratedLesson, draft.lesson_id) if draft is not None and getattr(draft, "lesson_id", None) else None
    published_id = getattr(lesson, "published_version_id", None)
    if not published_id or published_id == job.lesson_version_id:
        return None
    published = await db.get(LessonVersion, published_id)
    if published is None or _cue_script(published.lesson_document, cue_id) != script:
        return None
    return published_id


async def refresh_avatar_job(job_id: int, db: AsyncSession,
                             provider: HeyGenProvider | None = None,
                             storage: SupabaseStorage | None = None) -> GenerationJob:
    # Строка задания под блокировкой: опрос из редактора и фоновый опрос не создадут видео дважды.
    job = await db.get(GenerationJob, job_id, with_for_update=True)
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
            bucket = AVATAR_VIDEO_BUCKET
            path = f"lessons/{job.lesson_version_id}/{job.scene_id or 'avatar'}/{result.id}.mp4"
            try:
                _public_url, size_bytes = await storage_client.copy_from_url(
                    source_url=result.video_url, bucket=bucket, path=path, content_type="video/mp4",
                )
            except LLMError as exc:
                if "not found" not in str(exc).casefold():
                    raise  # временный сбой: следующий опрос попробует снова
                # Корзины нет — повтор не поможет, а ссылка HeyGen со временем истечёт: сообщаем явно.
                job.status = "failed"
                job.error = {"message": f"Нет закрытой корзины «{bucket}» в Supabase Storage. Создайте её и сгенерируйте реплику заново."}
                job.completed_at = datetime.now(timezone.utc)
                job.updated_at = job.completed_at
                await db.commit()
                await db.refresh(job)
                return job
            # Корзина закрытая: публичной ссылки нет, ученику выдаётся подписанная (avatar_video_urls).
            asset_url = f"storage:{bucket}/{path}"
        asset_fields = dict(
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
        )
        db.add(LessonAsset(lesson_version_id=job.lesson_version_id, **asset_fields))
        await clear_lesson_manifest_cache_for_version(job.lesson_version_id, db)
        published_id = await published_version_with_same_cue(job, db)
        if published_id is not None:
            db.add(LessonAsset(lesson_version_id=published_id, **asset_fields))
            await clear_lesson_manifest_cache_for_version(published_id, db)
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
