"""FastAPI adapters for verified Supabase identities and role checks."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.auth import AuthPrincipal, AuthServiceError, UserRole, principal_for_auth_user
from services.supabase_auth import SupabaseAuthError, get_auth_user

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthServiceError(status_code=401, detail="Требуется вход в систему.", code="auth_required")
    try:
        auth_user = await get_auth_user(credentials.credentials)
    except SupabaseAuthError as exc:
        # Supabase отвечает 403 на истёкший или битый токен. Для клиента это
        # 401: он обновит сессию и повторит запрос, а не упрётся в «нет прав».
        if exc.status_code in {401, 403}:
            raise AuthServiceError(status_code=401, detail="Сессия истекла. Войдите снова.", code="session_expired") from exc
        raise
    return await principal_for_auth_user(str(auth_user.get("id") or ""), credentials.credentials, db)


def require_roles(*roles: UserRole, password_change_allowed: bool = False) -> Callable[..., Any]:
    async def dependency(user: AuthPrincipal = Depends(get_current_user)) -> AuthPrincipal:
        if user.role not in roles:
            raise AuthServiceError(status_code=403, detail="Недостаточно прав для этого действия.")
        if user.must_change_password and not password_change_allowed:
            raise AuthServiceError(status_code=403, detail="Сначала измените временный пароль.")
        return user

    return dependency
