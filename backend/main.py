from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import Base, engine
from routes import auth, components, dashboard, ktp, lessons, progress, subjects
from seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # create_all does not alter tables from earlier releases. These additive
        # columns keep existing progress rows readable without a migration runner.
        if connection.dialect.name == "postgresql":
            await connection.execute(text(
                "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence JSON DEFAULT '{}'::json"
            ))
            await connection.execute(text(
                "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery JSON DEFAULT '{}'::json"
            ))
            await connection.execute(text(
                "ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status VARCHAR(50) DEFAULT 'not_assessed'"
            ))
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