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

    # Всё одной командой DO: на далёкой базе каждый отдельный запрос стоит сотни миллисекунд,
    # а их здесь больше двадцати — это были десятки секунд на каждом старте.
    await connection.execute(text("""
        DO $$ BEGIN
          ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence JSON DEFAULT '{}'::json;
          ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery JSON DEFAULT '{}'::json;
          ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status VARCHAR(50) DEFAULT 'not_assessed';
          ALTER TABLE topics ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;
          ALTER TABLE topics ADD COLUMN IF NOT EXISTS covered_topic_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
          ALTER TABLE topics ADD COLUMN IF NOT EXISTS source_assessment_topic_id INTEGER;
          ALTER TABLE topics ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
          ALTER TABLE topics ADD COLUMN IF NOT EXISTS review_required BOOLEAN NOT NULL DEFAULT FALSE;
          ALTER TABLE generated_lessons ADD COLUMN IF NOT EXISTS published_version_id BIGINT;
          ALTER TABLE progress ADD COLUMN IF NOT EXISTS responses JSONB NOT NULL DEFAULT '{}'::jsonb;
          CREATE INDEX IF NOT EXISTS topics_active_section_sort_idx
            ON topics(section_id, sort_order) WHERE archived_at IS NULL;

          -- Внешние ключи добавляются, только если их нет: старые базы становятся совместимы по запросам
          -- без повторного исправления данных из полной миграции на каждом старте.
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'topics_source_assessment_topic_id_fkey') THEN
            ALTER TABLE topics ADD CONSTRAINT topics_source_assessment_topic_id_fkey
              FOREIGN KEY (source_assessment_topic_id) REFERENCES topics(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'generated_lessons_published_version_id_fkey') THEN
            ALTER TABLE generated_lessons ADD CONSTRAINT generated_lessons_published_version_id_fkey
              FOREIGN KEY (published_version_id) REFERENCES lesson_versions(id) ON DELETE SET NULL;
          END IF;

          UPDATE generated_lessons SET published_version_id = active_version_id
            WHERE status = 'published' AND published_version_id IS NULL;
          UPDATE progress p SET lesson_version_id = l.published_version_id
            FROM generated_lessons l WHERE l.topic_id = p.topic_id
            AND p.lesson_version_id IS NULL AND l.published_version_id IS NOT NULL;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'subjects' AND column_name = 'hours_per_week' AND data_type <> 'double precision'
          ) THEN
            ALTER TABLE subjects ALTER COLUMN hours_per_week TYPE double precision;
          END IF;
        END $$
    """))
