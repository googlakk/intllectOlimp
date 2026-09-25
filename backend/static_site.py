"""Раздача собранного frontend из того же процесса, что и API.

В продакшене сайт и /api живут на одном адресе: frontend ходит на
относительный /api, отдельный прокси не нужен. Если сборки нет
(локальная разработка через Vite), ничего не подключается.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

DEFAULT_DIST = Path(__file__).resolve().parent.parent / "artifacts" / "intellect-learning-platform" / "dist" / "public"
IMMUTABLE_ASSET_CACHE = "public, max-age=31536000, immutable"
HTML_SHELL_CACHE = "no-cache"


def frontend_dist() -> Path:
    return Path(os.getenv("FRONTEND_DIST") or DEFAULT_DIST).resolve()


def mount_frontend(app: FastAPI, dist: Path | None = None) -> bool:
    """Подключает SPA последним маршрутом. Возвращает False, если сборки нет."""
    root = (dist or frontend_dist()).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Неизвестный API-адрес не должен превращаться в HTML-страницу.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_file() and root in candidate.parents:
                cache = IMMUTABLE_ASSET_CACHE if full_path.startswith("assets/") else HTML_SHELL_CACHE
                return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": HTML_SHELL_CACHE})

    return True
