import asyncio
import os
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import event, exc, text
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

POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
# Пинг только после простоя: pool_pre_ping платил лишний обмен с базой на КАЖДОМ запросе,
# а до Supabase это сотни миллисекунд. Соединение, которым пользовались недавно, живо.
IDLE_PING_SEC = int(os.getenv("DATABASE_IDLE_PING_SEC", "60"))

engine = create_async_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
    pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE_SEC", "1800")),
    pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT_SEC", "10")),
)


@event.listens_for(engine.sync_engine, "checkin")
def _remember_checkin(dbapi_connection, connection_record) -> None:
    connection_record.info["checked_in_at"] = time.monotonic()


@event.listens_for(engine.sync_engine, "checkout")
def _ping_after_idle(dbapi_connection, connection_record, connection_proxy) -> None:
    checked_in_at = connection_record.info.get("checked_in_at")
    if checked_in_at is None or time.monotonic() - checked_in_at < IDLE_PING_SEC:
        return
    try:
        dbapi_connection.ping()
    except Exception as error:  # соединение закрыто пулером или сетью — пул откроет новое
        raise exc.DisconnectionError() from error


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def warm_database_pool(connections: int | None = None) -> None:
    """Открыть несколько соединений сразу, параллельно: первая страница шлёт запросы одновременно,
    и каждое новое соединение с далёкой базой стоит секунды. Сбой прогрева не мешает старту."""
    count = max(1, min(connections or int(os.getenv("DATABASE_POOL_WARM", "3")), POOL_SIZE))

    async def open_one():
        connection = await engine.connect()
        try:
            await connection.execute(text("select 1"))
        except BaseException:
            await connection.close()
            raise
        return connection

    opened = await asyncio.gather(*(open_one() for _ in range(count)), return_exceptions=True)
    await asyncio.gather(*(item.close() for item in opened if not isinstance(item, BaseException)))
