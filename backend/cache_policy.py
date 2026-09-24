from __future__ import annotations

from re import fullmatch


PRIVATE_READ_CACHE = "private, max-age=30, stale-while-revalidate=120"
PRIVATE_MEDIA_CACHE = "private, max-age=3600"
PRIVATE_NO_STORE = "private, no-store"


def api_cache_control(method: str, path: str) -> str | None:
    if not path.startswith("/api/"):
        return None
    if method.upper() != "GET":
        return PRIVATE_NO_STORE
    if path == "/api/healthz":
        return "no-store"
    if fullmatch(r"/api/lessons/\d+/manifest", path):
        return PRIVATE_READ_CACHE
    if path == "/api/subjects" or fullmatch(r"/api/subjects/\d+/(sections|outline)", path):
        return PRIVATE_READ_CACHE
    if fullmatch(r"/api/sections/\d+/topics", path):
        return PRIVATE_READ_CACHE
    if fullmatch(r"/api/curriculum/students/\d+/map", path):
        return PRIVATE_READ_CACHE
    if path.startswith("/api/avatar/assets/") or path.startswith("/api/media/content/"):
        return PRIVATE_MEDIA_CACHE
    return PRIVATE_NO_STORE
