"""Minimal server-side Supabase Auth client for the beta identity flow."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import time
from typing import Any

import httpx

from errors import ApplicationError


class SupabaseAuthError(ApplicationError):
    pass


def normalize_login(login: str) -> str:
    value = login.strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,49}", value):
        raise SupabaseAuthError(
            status_code=422,
            detail="Логин должен содержать 3–50 латинских букв, цифр, точек, дефисов или подчёркиваний.",
        )
    return value


def auth_email(login: str) -> str:
    return f"{normalize_login(login)}@users.intellect.local"


def _settings(*, admin: bool = False) -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key_name = "SUPABASE_SERVICE_ROLE_KEY" if admin else "SUPABASE_ANON_KEY"
    key = os.getenv(key_name, "")
    if not url or not key:
        raise SupabaseAuthError(
            status_code=503,
            detail=f"Supabase Auth не настроен: заполните SUPABASE_URL и {key_name}.",
        )
    return url, key


VERIFIED_TOKEN_TTL_S = 120
VERIFIED_TOKEN_LIMIT = 5000
_verified_tokens: dict[str, tuple[float, dict[str, Any]]] = {}
_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _http_client() -> httpx.AsyncClient:
    """Один клиент на процесс: соединение с Supabase (TCP + TLS) переиспользуется, а не открывается
    заново на каждый запрос. Новый цикл событий (тесты, перезапуск) — новый клиент."""
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client.is_closed or _client_loop is not loop:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10))
        _client_loop = loop
    return _client


def _token_key(access_token: str) -> str:
    return hashlib.sha256(access_token.encode()).hexdigest()


def _seconds_until_expiry(access_token: str) -> float:
    """Срок токена из поля exp (без проверки подписи: ей занимается Supabase при первой проверке)."""
    try:
        payload = access_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"]) - time.time()
    except (IndexError, KeyError, TypeError, ValueError):
        return 0.0


def _prune_verified_tokens(now: float) -> None:
    for key in [key for key, (expires, _) in _verified_tokens.items() if expires <= now]:
        del _verified_tokens[key]
    if len(_verified_tokens) >= VERIFIED_TOKEN_LIMIT:
        _verified_tokens.clear()


async def _request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    access_token: str | None = None,
    admin: bool = False,
    invalid_credentials_message: bool = False,
) -> dict[str, Any]:
    url, key = _settings(admin=admin)
    headers = {"apikey": key, "Content-Type": "application/json"}
    headers["Authorization"] = f"Bearer {access_token or key}"
    response = await _http_client().request(method, f"{url}{path}", json=payload, headers=headers)
    if response.is_error:
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        message = body.get("msg") or body.get("message") or body.get("error_description")
        if invalid_credentials_message and response.status_code in {400, 401}:
            message = "Неверный логин или пароль."
        raise SupabaseAuthError(status_code=response.status_code, detail=message or "Ошибка Supabase Auth")
    if not response.content:
        return {}
    return response.json()


async def password_sign_in(login: str, password: str) -> dict[str, Any]:
    return await _request(
        "POST",
        "/auth/v1/token?grant_type=password",
        payload={"email": auth_email(login), "password": password},
        invalid_credentials_message=True,
    )


async def refresh_session(refresh_token: str) -> dict[str, Any]:
    return await _request(
        "POST",
        "/auth/v1/token?grant_type=refresh_token",
        payload={"refresh_token": refresh_token},
    )


async def get_auth_user(access_token: str) -> dict[str, Any]:
    """Пользователь по токену. Проверенный Supabase токен помним до двух минут (не дольше его срока):
    иначе каждый запрос API ждёт лишний сетевой вызов в Supabase Auth (0,4–0,7 с)."""
    key = _token_key(access_token)
    cached = _verified_tokens.get(key)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]
    user = await _request("GET", "/auth/v1/user", access_token=access_token)
    ttl = min(VERIFIED_TOKEN_TTL_S, _seconds_until_expiry(access_token) - 5)
    if ttl > 0:
        if len(_verified_tokens) >= VERIFIED_TOKEN_LIMIT:
            _prune_verified_tokens(now)
        _verified_tokens[key] = (now + ttl, user)
    return user


def forget_auth_token(access_token: str) -> None:
    """После выхода или смены пароля токен снова проверяется в Supabase."""
    _verified_tokens.pop(_token_key(access_token), None)


async def change_auth_password(access_token: str, password: str) -> None:
    await _request("PUT", "/auth/v1/user", payload={"password": password}, access_token=access_token)


async def logout_auth_session(access_token: str) -> None:
    await _request("POST", "/auth/v1/logout", access_token=access_token)


async def admin_create_auth_user(
    *, login: str, password: str, display_name: str, role: str
) -> dict[str, Any]:
    return await _request(
        "POST",
        "/auth/v1/admin/users",
        payload={
            "email": auth_email(login),
            "password": password,
            "email_confirm": True,
            "user_metadata": {"login_name": normalize_login(login), "display_name": display_name, "role": role},
            "app_metadata": {"provisioned_by": "intellect-backend", "platform_role": role},
        },
        admin=True,
    )


async def admin_update_auth_user(auth_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await _request("PUT", f"/auth/v1/admin/users/{auth_user_id}", payload=payload, admin=True)


async def admin_delete_auth_user(auth_user_id: str) -> None:
    await _request("DELETE", f"/auth/v1/admin/users/{auth_user_id}", admin=True)
