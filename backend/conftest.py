"""Shared test fixtures.

Tests run against TEST_DATABASE_URL (never the dev database). The schema is
rebuilt from Alembic migrations once per session and tables are truncated
before each test that uses the database.
"""
import os

from dotenv import load_dotenv

load_dotenv()
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is required to run tests (see .env.example)")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # must happen before importing database

import asyncio  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from database import DATABASE_URL, AsyncSessionLocal, Base  # noqa: E402


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def migrated_database():
    asyncio.run(_reset_schema())
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "alembic.ini")), "head")


@pytest.fixture
async def db(migrated_database):
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session


@pytest.fixture
async def client(db):
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
