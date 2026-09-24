"""One-time extraction of embedded lesson media into Supabase Storage."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lesson_contracts import adapt_legacy_blocks
from models import GeneratedLesson, LessonAsset
from services.lessons import clear_lesson_manifest_cache, persist_lesson_version
from storage import SupabaseStorage

DATA_URL = re.compile(r"^data:([^;,]+);base64,(.+)$", re.DOTALL)


def parse_data_url(value: str) -> tuple[str, bytes]:
    match = DATA_URL.fullmatch(value.strip())
    if not match:
        raise ValueError("Некорректный data URL")
    return match.group(1), base64.b64decode(match.group(2), validate=True)


async def migrate_embedded_assets(db: AsyncSession, storage: SupabaseStorage | None = None) -> dict[str, int]:
    storage = storage or SupabaseStorage()
    if not storage.configured():
        raise RuntimeError("SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY обязательны")
    lessons = (await db.scalars(select(GeneratedLesson))).all()
    migrated_assets = 0
    migrated_lessons = 0
    for lesson in lessons:
        changed = False
        blocks: list[dict[str, Any]] = [dict(block) for block in (lesson.blocks or [])]
        for index, block in enumerate(blocks):
            content = dict(block.get("content") or {})
            value = content.get("data_url")
            if not isinstance(value, str) or not value.startswith("data:"):
                continue
            mime_type, raw = parse_data_url(value)
            digest = hashlib.sha256(raw).hexdigest()[:20]
            extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(mime_type, "bin")
            version_id = lesson.active_version_id
            if not version_id:
                continue
            scene_id = f"scene-{index + 1}"
            path = f"lessons/{version_id}/{scene_id}/{digest}.{extension}"
            url, size_bytes = await storage.upload_bytes(
                content=raw, bucket="lesson-assets", path=path, content_type=mime_type,
            )
            db.add(LessonAsset(
                lesson_version_id=version_id, scene_id=scene_id, kind="image",
                provider="legacy_migration", provider_asset_id=digest,
                storage_bucket="lesson-assets", storage_path=path, source_url=url,
                mime_type=mime_type, size_bytes=size_bytes, status="ready",
                metadata_json={"migrated_from": "generated_lessons.blocks.data_url"},
            ))
            content.pop("data_url", None)
            content["url"] = url
            block["content"] = content
            changed = True
            migrated_assets += 1
        if changed:
            lesson.blocks = blocks
            await persist_lesson_version(
                lesson, adapt_legacy_blocks(blocks, lesson.lesson_metadata or {}), db, status="ready",
            )
            clear_lesson_manifest_cache(lesson.topic_id)
            migrated_lessons += 1
    await db.commit()
    return {"lessons": migrated_lessons, "assets": migrated_assets}
