from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import bilimos_sync
from database import engine
from security import create_session_token
from routes import auth, classes, components, dashboard, integrations, ktp, lessons, progress, subjects


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_session_token(0)  # fail fast if SECRET_KEY is missing
    bilimos_sync.request_sync()  # background, non-fatal; no-op when not configured
    yield
    await engine.dispose()


app = FastAPI(title="Intellect Learning Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (auth.router, ktp.router, subjects.router, classes.router, components.router, lessons.router, progress.router, dashboard.router, integrations.router):
    app.include_router(router)


@app.get("/api/healthz")
async def health():
    return {"status": "ok"}

STATIC_DIR = os.getenv("STATIC_DIR")
if STATIC_DIR and os.path.isdir(STATIC_DIR):
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    static_root = Path(STATIC_DIR).resolve()

    # Registered last so every API route matches first.
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (static_root / path).resolve()
        if path and file.is_file() and file.is_relative_to(static_root):
            return FileResponse(file)
        return FileResponse(static_root / "index.html")
