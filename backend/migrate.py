"""Bring the database to the latest schema.

Run before starting the API: `python migrate.py`.
Databases created before Alembic (tables made by create_all) are adopted:
missing additive columns are added, then the baseline revision is stamped.
"""
import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from database import DATABASE_URL

BASELINE = "bb0fd10140f3"
LEGACY_COLUMNS = (
    "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence JSON DEFAULT '{}'::json",
    "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery JSON DEFAULT '{}'::json",
    "ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status VARCHAR(50) DEFAULT 'not_assessed'",
)


async def adopt_legacy_database() -> bool:
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
            if "alembic_version" in tables or "subjects" not in tables:
                return False
            for statement in LEGACY_COLUMNS:
                await connection.execute(text(statement))
            return True
    finally:
        await engine.dispose()


def main() -> None:
    config = Config("alembic.ini")
    if asyncio.run(adopt_legacy_database()):
        command.stamp(config, BASELINE)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
