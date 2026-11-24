import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import models  # noqa: F401  (registers tables on Base.metadata)
from database import DATABASE_URL, Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported; run against a database.")
asyncio.run(run_async_migrations())
