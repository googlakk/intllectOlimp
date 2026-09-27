from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AccountEvent, Profile
from auth_dependencies import get_current_user, require_roles
from services.auth import (
    AuthPrincipal,
    forget_principal,
    principal_for_auth_user,
    serialize_principal,
)
from services.supabase_auth import (
    change_auth_password,
    forget_auth_token,
    logout_auth_session,
    password_sign_in,
    refresh_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginInput(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordInput(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


def _session_payload(session: dict, principal: AuthPrincipal) -> dict:
    return {
        "access_token": session["access_token"],
        "refresh_token": session["refresh_token"],
        "expires_in": session.get("expires_in", 3600),
        "user": serialize_principal(principal),
    }


@router.post("/login")
async def login(payload: LoginInput, db: AsyncSession = Depends(get_db)):
    session = await password_sign_in(payload.login, payload.password)
    principal = await principal_for_auth_user(
        str((session.get("user") or {}).get("id") or ""), session["access_token"], db
    )
    # Одна команда UPDATE вместо чтения профиля и записи: на далёкой базе каждый обмен — сотни мс.
    await db.execute(update(Profile).where(Profile.id == principal.profile_id).values(last_login_at=datetime.now(timezone.utc)))
    await db.commit()
    return _session_payload(session, principal)


@router.post("/refresh")
async def refresh(payload: RefreshInput, db: AsyncSession = Depends(get_db)):
    session = await refresh_session(payload.refresh_token)
    principal = await principal_for_auth_user(
        str((session.get("user") or {}).get("id") or ""), session["access_token"], db
    )
    return _session_payload(session, principal)


@router.get("/me")
async def me(user: AuthPrincipal = Depends(get_current_user)):
    return serialize_principal(user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher", "student", password_change_allowed=True)),
    db: AsyncSession = Depends(get_db),
):
    password = payload.new_password
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        from services.auth import AuthServiceError
        raise AuthServiceError(status_code=422, detail="Пароль должен содержать буквы и цифры.")
    await change_auth_password(user.access_token, password)
    profile = await db.get(Profile, user.profile_id)
    if profile is not None:
        profile.must_change_password = False
        db.add(AccountEvent(
            organization_id=user.organization_id,
            actor_profile_id=user.profile_id,
            target_profile_id=user.profile_id,
            event_type="password_changed",
            metadata_json={},
        ))
        await db.commit()
    forget_principal(user.auth_user_id)
    return {"ok": True}


@router.post("/logout")
async def logout(user: AuthPrincipal = Depends(get_current_user)):
    forget_auth_token(user.access_token)
    forget_principal(user.auth_user_id)
    await logout_auth_session(user.access_token)
    return {"ok": True}
