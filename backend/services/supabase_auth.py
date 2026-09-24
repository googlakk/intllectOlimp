"""Minimal server-side Supabase Auth client for the beta identity flow."""

from __future__ import annotations

import os
import re
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
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(method, f"{url}{path}", json=payload, headers=headers)
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
    return await _request("GET", "/auth/v1/user", access_token=access_token)


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
