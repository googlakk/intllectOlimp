import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
parts = urlsplit(DATABASE_URL)
query = dict(parse_qsl(parts.query))
sslmode = query.pop("sslmode", None)
query.pop("channel_binding", None)
# Строка Supabase из вкладки Transaction pooler несёт ?pgbouncer=true —
# это параметр для Prisma. asyncpg такого аргумента не знает и падает.
query.pop("pgbouncer", None)
if sslmode and sslmode != "disable":
    query["ssl"] = "require"
DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE_SEC", "1800")),
    pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT_SEC", "10")),
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def warm_database_pool() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("select 1"))
