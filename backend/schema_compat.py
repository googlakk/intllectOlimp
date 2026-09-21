"""Runtime schema compatibility for deployments without a migration runner."""

from typing import Any

from sqlalchemy import text


async def apply_schema_compatibility(connection: Any) -> None:
    """Apply additive legacy schema fixes after `create_all`.

    This is intentionally small and idempotent. New schema changes should move
    to a real migration path instead of growing application startup forever.
    """
    if connection.dialect.name != "postgresql":
        return

    await connection.execute(text(
        "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence JSON DEFAULT '{}'::json"
    ))
    await connection.execute(text(
        "ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery JSON DEFAULT '{}'::json"
    ))
    await connection.execute(text(
        "ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status VARCHAR(50) DEFAULT 'not_assessed'"
    ))
    await connection.execute(text(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0"
    ))

    current_type = await connection.scalar(text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'subjects' AND column_name = 'hours_per_week'"
    ))
    if current_type and current_type != "double precision":
        await connection.execute(text(
            "ALTER TABLE subjects ALTER COLUMN hours_per_week TYPE double precision"
        ))
