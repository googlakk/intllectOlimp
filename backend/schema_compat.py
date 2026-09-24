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
    await connection.execute(text(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS covered_topic_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    ))
    await connection.execute(text(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS source_assessment_topic_id INTEGER"
    ))
    await connection.execute(text(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ"
    ))
    await connection.execute(text(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS review_required BOOLEAN NOT NULL DEFAULT FALSE"
    ))
    await connection.execute(text(
        "ALTER TABLE generated_lessons ADD COLUMN IF NOT EXISTS published_version_id BIGINT"
    ))
    await connection.execute(text(
        "ALTER TABLE progress ADD COLUMN IF NOT EXISTS responses JSONB NOT NULL DEFAULT '{}'::jsonb"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS topics_active_section_sort_idx "
        "ON topics(section_id, sort_order) WHERE archived_at IS NULL"
    ))

    # Runtime compatibility is deliberately additive. Foreign keys are added
    # only when missing so older deployments become query-compatible without
    # replaying the data-repair portion of the full migration at every start.
    await connection.execute(text("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'topics_source_assessment_topic_id_fkey') THEN
            ALTER TABLE topics ADD CONSTRAINT topics_source_assessment_topic_id_fkey
              FOREIGN KEY (source_assessment_topic_id) REFERENCES topics(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'generated_lessons_published_version_id_fkey') THEN
            ALTER TABLE generated_lessons ADD CONSTRAINT generated_lessons_published_version_id_fkey
              FOREIGN KEY (published_version_id) REFERENCES lesson_versions(id) ON DELETE SET NULL;
          END IF;
        END $$
    """))
    await connection.execute(text(
        "UPDATE generated_lessons SET published_version_id = active_version_id "
        "WHERE status = 'published' AND published_version_id IS NULL"
    ))
    await connection.execute(text(
        "UPDATE progress p SET lesson_version_id = l.published_version_id "
        "FROM generated_lessons l WHERE l.topic_id = p.topic_id "
        "AND p.lesson_version_id IS NULL AND l.published_version_id IS NOT NULL"
    ))

    current_type = await connection.scalar(text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'subjects' AND column_name = 'hours_per_week'"
    ))
    if current_type and current_type != "double precision":
        await connection.execute(text(
            "ALTER TABLE subjects ALTER COLUMN hours_per_week TYPE double precision"
        ))
