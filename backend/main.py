from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routes import auth, components, dashboard, ktp, lessons, progress, subjects
from seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await seed_if_empty()
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
for router in (auth.router, ktp.router, subjects.router, components.router, lessons.router, progress.router, dashboard.router):
    app.include_router(router)


@app.get("/api/healthz")
async def health():
    return {"status": "ok"}