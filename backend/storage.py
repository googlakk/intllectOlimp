"""Server-side Supabase Storage client for generated lesson assets."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from llm import LLMError
from llm._http import AsyncClient, HTTPError, Timeout


class SupabaseStorage:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    async def copy_from_url(self, *, source_url: str, bucket: str, path: str,
                            content_type: str) -> tuple[str, int]:
        base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not base_url or not key:
            raise LLMError("Supabase Storage не настроен", provider="supabase-storage")
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(180))
        try:
            source = await client.get(source_url)
            source.raise_for_status()
            target = f"{base_url}/storage/v1/object/{quote(bucket)}/{quote(path, safe='/')}"
            uploaded = await client.post(target, headers={
                "Authorization": f"Bearer {key}", "apikey": key,
                "Content-Type": content_type, "x-upsert": "true",
            }, content=source.content)
            uploaded.raise_for_status()
            public_url = f"{base_url}/storage/v1/object/public/{bucket}/{quote(path, safe='/')}"
            return public_url, len(source.content)
        except HTTPError as exc:
            raise LLMError(f"Не удалось сохранить asset в Supabase Storage: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def upload_bytes(self, *, content: bytes, bucket: str, path: str,
                           content_type: str) -> tuple[str, int]:
        base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not base_url or not key:
            raise LLMError("Supabase Storage не настроен", provider="supabase-storage")
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(180))
        try:
            target = f"{base_url}/storage/v1/object/{quote(bucket)}/{quote(path, safe='/')}"
            uploaded = await client.post(target, headers={
                "Authorization": f"Bearer {key}", "apikey": key,
                "Content-Type": content_type, "x-upsert": "true",
            }, content=content)
            uploaded.raise_for_status()
            public_url = f"{base_url}/storage/v1/object/public/{bucket}/{quote(path, safe='/')}"
            return public_url, len(content)
        except HTTPError as exc:
            raise LLMError(f"Не удалось сохранить asset в Supabase Storage: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()
