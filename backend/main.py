from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from security import create_session_token
from routes import auth, classes, components, dashboard, ktp, lessons, progress, subjects


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_session_token(0)  # fail fast if SECRET_KEY is missing
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
for router in (auth.router, ktp.router, subjects.router, classes.router, components.router, lessons.router, progress.router, dashboard.router):
    app.include_router(router)


@app.get("/api/healthz")
async def health():
    return {"status": "ok"}