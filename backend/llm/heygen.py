"""HeyGen v3 client for scripted lesson-avatar clips."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from llm import LLMError
from llm._http import AsyncClient, HTTPError, Timeout

BASE_URL = os.getenv("HEYGEN_BASE_URL", "https://api.heygen.com").rstrip("/")
TIMEOUT = float(os.getenv("HEYGEN_TIMEOUT", "120"))
CATALOG_CACHE_SECONDS = float(os.getenv("HEYGEN_CATALOG_CACHE_SECONDS", "600"))
# Без поля engine HeyGen v3 рендерит дорогим Avatar IV. Avatar III — заметно дешевле;
# другой движок (avatar_iv) — только осознанно, через переменную окружения.
AVATAR_ENGINES = ("avatar_iii", "avatar_iv")
# Кадр в пропорциях самого фото и фото целиком (contain): при 16:9 HeyGen растягивает вертикальный
# портрет на широкий кадр (cover) и срезает верх головы. В уроке аватар всё равно показывается в круге.
AVATAR_ASPECT_RATIO = os.getenv("HEYGEN_ASPECT_RATIO", "auto").strip() or "auto"
AVATAR_FIT = "contain"
AVATAR_ENGINE = os.getenv("HEYGEN_AVATAR_ENGINE", "avatar_iii").strip() or "avatar_iii"
if AVATAR_ENGINE not in AVATAR_ENGINES:
    # Опечатка в переменной превратила бы каждое видео в ошибку 400 от HeyGen.
    logging.getLogger(__name__).warning("HEYGEN_AVATAR_ENGINE=%r не поддерживается, используем avatar_iii", AVATAR_ENGINE)
    AVATAR_ENGINE = "avatar_iii"
_CATALOG_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass
class HeyGenVideoJob:
    id: str
    status: str
    video_url: str = ""
    thumbnail_url: str = ""
    duration: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeyGenAvatarLook:
    id: str
    group_id: str
    status: str
    preview_image_url: str = ""
    preview_video_url: str = ""
    default_voice_id: str = ""
    error: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def verify_webhook_signature(body: bytes, signature: str, timestamp: str, *, secret: str | None = None,
                             now: float | None = None, max_skew_seconds: int = 300) -> bool:
    key = (secret or os.getenv("HEYGEN_WEBHOOK_SECRET") or "").encode()
    if not key or not signature or not timestamp:
        return False
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False
    if abs((time.time() if now is None else now) - sent_at) > max_skew_seconds:
        return False
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.casefold(), expected.casefold())


class HeyGenProvider:
    name = "heygen"

    def __init__(self, client: Any | None = None, api_key: str | None = None) -> None:
        self._client = client
        self._api_key = api_key

    async def list_avatars(self, *, ownership: str = "all", limit: int = 200,
                           query: str | None = None) -> list[dict[str, Any]]:
        del ownership
        avatars = await self._cached_catalog("avatars", "/v2/avatars")
        if query and query.strip():
            needle = query.strip().casefold()
            avatars = [avatar for avatar in avatars if needle in " ".join((
                str(avatar.get("avatar_name") or ""),
                str(avatar.get("avatar_id") or ""),
                " ".join(str(tag) for tag in (avatar.get("tags") or [])),
            )).casefold()]
        return avatars[:max(1, min(limit, 500))]

    async def list_voices(self, *, language: str | None = None, voice_type: str = "public",
                          limit: int = 200) -> list[dict[str, Any]]:
        del voice_type
        voices = await self._cached_catalog("voices", "/v2/voices")
        if language:
            requested = language.casefold().split("-")[0]
            language_names = {
                "ru": {"ru", "russian", "русский"},
                "ky": {"ky", "kyrgyz", "кыргызский", "киргизский"},
            }.get(requested, {requested})
            filtered = []
            for voice in voices:
                voice_language = str(voice.get("language") or "").strip().casefold()
                locale = str(voice.get("locale") or voice.get("support_locale") or "").strip().casefold()
                if voice_language in language_names or locale == requested or locale.startswith(f"{requested}-"):
                    filtered.append(voice)
            if filtered:
                voices = filtered
        return voices[:max(1, min(limit, 500))]

    async def _cached_catalog(self, key: str, path: str) -> list[dict[str, Any]]:
        if self._client is not None:
            return self._catalog_items(await self._request("GET", path), key)
        cached_at, items = _CATALOG_CACHE.get(key, (0.0, []))
        if items and time.monotonic() - cached_at < CATALOG_CACHE_SECONDS:
            return items
        body = await self._request("GET", path)
        items = self._catalog_items(body, key)
        _CATALOG_CACHE[key] = (time.monotonic(), items)
        return items

    async def create_video(self, *, avatar_id: str, voice_id: str, script: str,
                           locale: str = "ru-RU", speed: float = 1.0,
                           pitch: float = 0.0, api_version: str = "v2") -> HeyGenVideoJob:
        if api_version == "v3":
            body = await self._request("POST", "/v3/videos", {
                "type": "avatar",
                "avatar_id": avatar_id,
                "engine": {"type": AVATAR_ENGINE},
                "aspect_ratio": AVATAR_ASPECT_RATIO,
                "fit": AVATAR_FIT,
                "output_format": "mp4",
                "script": script,
                "voice_id": voice_id,
                "voice_settings": {
                    "speed": max(0.5, min(speed, 1.5)),
                    "pitch": pitch,
                    "locale": locale,
                },
            })
            job = self._video_job(body, default_status="waiting")
            job.raw["_api_version"] = "v3"
            return job
        del locale, pitch
        body = await self._request("POST", "/v2/video/generate", {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id,
                    "speed": max(0.5, min(speed, 1.5)),
                },
            }],
            "dimension": {"width": 1280, "height": 720},
            "caption": True,
        })
        return self._video_job(body, default_status="pending")

    async def get_video(self, video_id: str, *, api_version: str = "v2") -> HeyGenVideoJob:
        encoded_id = quote(video_id, safe="")
        if api_version == "v3":
            job = self._video_job(await self._request("GET", f"/v3/videos/{encoded_id}"))
            job.raw["_api_version"] = "v3"
            return job
        return self._video_job(await self._request("GET", f"/v1/video_status.get?video_id={encoded_id}"))

    async def create_photo_avatar(
        self,
        *,
        name: str,
        image: bytes,
        media_type: str,
        idempotency_key: str,
    ) -> HeyGenAvatarLook:
        body = await self._request(
            "POST",
            "/v3/avatars",
            {
                "type": "photo",
                "name": name,
                "file": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(image).decode("ascii"),
                },
            },
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        return self._avatar_look(body)

    async def get_avatar_look(self, look_id: str) -> HeyGenAvatarLook:
        encoded_id = quote(look_id, safe="")
        return self._avatar_look(await self._request("GET", f"/v3/avatars/looks/{encoded_id}"))

    async def _request(self, method: str, path: str,
                       payload: dict[str, Any] | None = None,
                       extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
        key = (self._api_key or os.getenv("HEYGEN_API_KEY") or "").strip()
        if not key:
            raise LLMError("HEYGEN_API_KEY не настроен", provider=self.name)
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(TIMEOUT))
        try:
            headers = {"X-Api-Key": key, "Content-Type": "application/json"}
            headers.update(extra_headers or {})
            response = await client.request(
                method, f"{BASE_URL}{path}",
                headers=headers,
                content=json.dumps(payload) if payload is not None else None,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise LLMError("HeyGen вернул неожиданный ответ", provider=self.name)
            return body
        except HTTPError as exc:
            message = self._http_error_message(exc)
            raise LLMError(f"Ошибка HeyGen API: {message}", provider=self.name) from exc
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _video_job(body: dict[str, Any], default_status: str = "pending") -> HeyGenVideoJob:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        video_id = data.get("id") or data.get("video_id")
        if not isinstance(video_id, str) or not video_id:
            raise LLMError("HeyGen не вернул video id", provider="heygen")
        duration = data.get("duration")
        return HeyGenVideoJob(
            id=video_id,
            status=str(data.get("status") or default_status).lower(),
            video_url=str(data.get("video_url") or ""),
            thumbnail_url=str(data.get("thumbnail_url") or ""),
            duration=float(duration) if isinstance(duration, (int, float)) else None,
            raw=data,
        )

    @staticmethod
    def _avatar_look(body: dict[str, Any]) -> HeyGenAvatarLook:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        item = data.get("avatar_item") if isinstance(data.get("avatar_item"), dict) else data
        group = data.get("avatar_group") if isinstance(data.get("avatar_group"), dict) else {}
        look_id = item.get("id") or item.get("avatar_id")
        if not isinstance(look_id, str) or not look_id:
            raise LLMError("HeyGen не вернул avatar look id", provider="heygen")
        error = item.get("error") if isinstance(item.get("error"), dict) else None
        return HeyGenAvatarLook(
            id=look_id,
            group_id=str(item.get("group_id") or group.get("id") or ""),
            status=str(item.get("status") or "processing").lower(),
            preview_image_url=str(item.get("preview_image_url") or group.get("preview_image_url") or ""),
            preview_video_url=str(item.get("preview_video_url") or group.get("preview_video_url") or ""),
            default_voice_id=str(item.get("default_voice_id") or group.get("default_voice_id") or ""),
            error=error,
            raw=data,
        )

    @staticmethod
    def _catalog_items(body: dict[str, Any], key: str) -> list[dict[str, Any]]:
        data = body.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return [item for item in data[key] if isinstance(item, dict)]
        return []

    @staticmethod
    def _http_error_message(exc: HTTPError) -> str:
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                body = response.json()
                if isinstance(body, dict):
                    error = body.get("error")
                    if isinstance(error, dict) and isinstance(error.get("message"), str):
                        return error["message"]
                    for key in ("message", "error"):
                        if isinstance(body.get(key), str) and body[key]:
                            return body[key]
            except (TypeError, ValueError):
                pass
        return str(exc)
