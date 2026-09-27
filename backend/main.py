from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path


def load_local_env() -> None:
    for env_path in (Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


load_local_env()

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import bindparam, text

from cache_policy import api_cache_control
from database import Base, engine, warm_database_pool
from errors import ApplicationError
from routes import topics, accounts, ai_models, auth, avatar, components, curriculum, dashboard, feedback, ktp, lessons, media, progress, subjects, textbooks, tutor
from schema_compat import apply_schema_compatibility
from seed import seed_if_empty
from static_site import mount_frontend
from auth_dependencies import require_roles


async def missing_tables(connection) -> set[str]:
    """Каких таблиц моделей нет в базе — одним запросом. create_all проверяет каждую таблицу
    отдельно: на далёкой базе это десятки секунд старта, хотя таблицы давно есть."""
    names = set(Base.metadata.tables)
    if connection.dialect.name != "postgresql":
        return names
    existing = await connection.execute(
        text("SELECT table_name FROM information_schema.tables "
             "WHERE table_schema = current_schema() AND table_name IN :names").bindparams(bindparam("names", expanding=True)),
        {"names": sorted(names)},
    )
    return names - {row[0] for row in existing}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        if await missing_tables(connection):
            await connection.run_sync(Base.metadata.create_all)
        await apply_schema_compatibility(connection)
    await seed_if_empty()
    await warm_database_pool()
    # Видео аватара дозревают в HeyGen минутами — сервер сам забирает готовые, не дожидаясь редактора.
    from services.avatar_poller import run_avatar_poller

    stop_poller = asyncio.Event()
    poller = asyncio.create_task(run_avatar_poller(stop_poller))
    yield
    stop_poller.set()
    await poller
    await engine.dispose()


app = FastAPI(title="Intellect Learning Platform API", lifespan=lifespan)


@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    if "cache-control" not in response.headers:
        cache_control = api_cache_control(request.method, request.url.path)
        if cache_control:
            response.headers["Cache-Control"] = cache_control
    return response


@app.exception_handler(ApplicationError)
async def application_error_handler(_request: Request, exc: ApplicationError):
    content = {"detail": exc.detail}
    if exc.code:
        content["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=content)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(topics.router)
app.include_router(avatar.webhook_router)
# Роли проверяются в самих маршрутах: отзыв оставляет ученик, список видит администратор.
app.include_router(feedback.router)
app.include_router(feedback.admin_router)
for router in (ktp.router, components.router, avatar.router, dashboard.router, ai_models.router, textbooks.router):
    app.include_router(router, dependencies=[Depends(require_roles("admin", "teacher"))])
app.include_router(media.router)
app.include_router(avatar.asset_router)
app.include_router(media.content_router)
for router in (subjects.router, curriculum.router, lessons.router, progress.router, tutor.router):
    app.include_router(router, dependencies=[Depends(require_roles("admin", "teacher", "student"))])


@app.get("/api/healthz")
async def health():
    return {"status": "ok"}


# Последним: перехватывает все остальные пути и отдаёт собранный сайт.
mount_frontend(app)
