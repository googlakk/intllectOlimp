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

    # --- Закрытые файлы (учебники): без публичных ссылок, доступ только через бэкенд ---

    @staticmethod
    def _credentials() -> tuple[str, str]:
        base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not base_url or not key:
            raise LLMError("Supabase Storage не настроен", provider="supabase-storage")
        return base_url, key

    async def create_signed_upload(self, *, bucket: str, path: str) -> str:
        """Разовая ссылка, по которой браузер загружает большой файл прямо в хранилище (PUT)."""
        base_url, key = self._credentials()
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(30))
        try:
            response = await client.post(
                f"{base_url}/storage/v1/object/upload/sign/{quote(bucket)}/{quote(path, safe='/')}",
                # Без upsert: по разовой ссылке нельзя подменить уже загруженный файл.
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            response.raise_for_status()
            signed = str(response.json().get("url") or "")
            if not signed:
                raise LLMError("Хранилище не вернуло ссылку для загрузки", provider="supabase-storage")
            return f"{base_url}/storage/v1{signed}"
        except HTTPError as exc:
            raise LLMError(f"Не удалось подготовить загрузку: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def object_size(self, *, bucket: str, path: str) -> int | None:
        """Размер файла в хранилище (HEAD) — не доверяем размеру, который прислал браузер."""
        base_url, key = self._credentials()
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(30))
        try:
            response = await client.head(
                f"{base_url}/storage/v1/object/{quote(bucket)}/{quote(path, safe='/')}",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            length = response.headers.get("content-length")
            return int(length) if length and length.isdigit() else None
        except HTTPError as exc:
            raise LLMError(f"Не удалось проверить файл в хранилище: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def download_bytes(self, *, bucket: str, path: str) -> bytes:
        base_url, key = self._credentials()
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(300))
        try:
            response = await client.get(
                f"{base_url}/storage/v1/object/{quote(bucket)}/{quote(path, safe='/')}",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            response.raise_for_status()
            return response.content
        except HTTPError as exc:
            raise LLMError(f"Не удалось скачать файл из хранилища: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def delete_object(self, *, bucket: str, path: str) -> None:
        """Удалить файл; если его и не было (сорвалась загрузка) — не ошибка."""
        base_url, key = self._credentials()
        owns_client = self._client is None
        client = self._client or AsyncClient(timeout=Timeout(30))
        try:
            response = await client.request(
                "DELETE", f"{base_url}/storage/v1/object/{quote(bucket)}",
                headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "application/json"},
                json={"prefixes": [path]},
            )
            if response.status_code not in (200, 204, 404):
                response.raise_for_status()
        except HTTPError as exc:
            raise LLMError(f"Не удалось удалить файл из хранилища: {exc}", provider="supabase-storage") from exc
        finally:
            if owns_client:
                await client.aclose()
