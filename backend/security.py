"""Password hashing and session tokens.

Passwords: argon2 via pwdlib. Sessions: a signed JWT in an httpOnly cookie,
so page scripts never see the token.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

SESSION_COOKIE = "intellect_session"
SESSION_TTL = timedelta(days=int(os.getenv("SESSION_TTL_DAYS", "7")))
_ALGORITHM = "HS256"
_hasher = PasswordHash.recommended()


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if not key or len(key) < 32:
        raise RuntimeError("SECRET_KEY must be set to a random string of at least 32 characters")
    return key


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Spend comparable time so missing hashes are not distinguishable by timing.
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def generate_password(length: int = 10) -> str:
    """Readable temporary password: no look-alike characters."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_session_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + SESSION_TTL}
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def read_session_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"
