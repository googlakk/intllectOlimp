"""BilimOs integration: change signal, manual sync, one-time SSO token login."""
import hmac
import logging
import os
from datetime import datetime, timezone
from urllib.parse import parse_qs

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

import bilimos_sync
from database import get_db
from deps import require_admin
from models import UsedJti, User
from routes.auth import set_session_cookie

router = APIRouter(tags=["integrations"])
log = logging.getLogger("bilimos")
LEEWAY_SEC = 10
NO_REFERRER = {"Referrer-Policy": "no-referrer"}
NO_ACCESS_PAGE = (
    "<!doctype html><html lang=\"ru\"><meta charset=\"utf-8\"><title>Нет доступа</title>"
    "<body style=\"font-family:sans-serif;text-align:center;padding:4rem\">"
    "<h1>Нет доступа к платформе</h1><p>Обратитесь к администратору школы.</p></body></html>"
)


@router.post("/api/integrations/bilimos/sync", status_code=202)
async def bilimos_signal(authorization: str = Header(default="")):
    secret = os.getenv("OLIMP_SYNC_SECRET")
    if not secret or not bilimos_sync.configured():
        raise HTTPException(status_code=404, detail="Интеграция с BilimOs не настроена")
    if not hmac.compare_digest(authorization.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(status_code=401, detail="Неверный ключ")
    bilimos_sync.request_sync()
    return {"accepted": True}


@router.post("/api/integrations/bilimos/sync-now", dependencies=[Depends(require_admin)])
async def bilimos_sync_now():
    if not bilimos_sync.configured():
        raise HTTPException(status_code=404, detail="Интеграция с BilimOs не настроена")
    try:
        return await bilimos_sync.sync_now()
    except Exception as exc:
        log.exception("BilimOs manual sync failed")
        raise HTTPException(status_code=502, detail="BilimOs недоступен, попробуйте позже") from exc


def _no_access() -> HTMLResponse:
    return HTMLResponse(NO_ACCESS_PAGE, status_code=403, headers=NO_REFERRER)


async def _find_user(db: AsyncSession, external_id: str) -> User | None:
    return await db.scalar(select(User).where(User.external_id == external_id))


@router.post("/api/sso/bilimos")
async def bilimos_sso(request: Request, db: AsyncSession = Depends(get_db)):
    public_key = os.getenv("OLIMP_SSO_PUBLIC_KEY", "").replace("\\n", "\n")
    token = parse_qs((await request.body()).decode(errors="replace")).get("token", [""])[0]
    if not public_key or not token:
        return _no_access()
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["EdDSA"],
            audience="olimp",
            issuer="bilimos",
            leeway=LEEWAY_SEC,
            options={"require": ["iss", "aud", "sub", "jti", "iat", "exp"]},
        )
    except jwt.PyJWTError:
        return _no_access()

    now = datetime.now(timezone.utc)
    await db.execute(delete(UsedJti).where(UsedJti.expires_at < now))
    expires_at = datetime.fromtimestamp(claims["exp"] + LEEWAY_SEC, timezone.utc)
    inserted = await db.scalar(
        insert(UsedJti).values(jti=str(claims["jti"])[:64], expires_at=expires_at)
        .on_conflict_do_nothing().returning(UsedJti.jti)
    )
    await db.commit()
    if inserted is None:
        return _no_access()  # replayed token

    user = await _find_user(db, str(claims["sub"]))
    if user is None and bilimos_sync.configured():
        try:
            await bilimos_sync.sync_now()
        except Exception:
            log.exception("BilimOs sync during SSO failed")
        user = await _find_user(db, str(claims["sub"]))
    if user is None or not user.is_active or user.role != claims.get("role"):
        return _no_access()

    user.last_login_at = func.now()
    await db.commit()
    response = RedirectResponse("/", status_code=303, headers=NO_REFERRER)
    set_session_cookie(response, user.id)
    return response
