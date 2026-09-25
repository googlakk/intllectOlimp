"""Таблица тьютора не создаётся сама при старте бэкенда — только миграцией."""

import re
import unittest
from pathlib import Path

import models  # noqa: F401 — регистрирует все обычные таблицы в Base.metadata
from database import Base
from tutor.models import TutorBase, TutorTurn

MIGRATION = Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "20260926120000_tutor_turns.sql"


class TutorTableTests(unittest.TestCase):
    def test_tutor_table_is_not_created_by_startup_create_all(self):
        self.assertNotIn("tutor_turns", Base.metadata.tables)
        self.assertIn("tutor_turns", TutorBase.metadata.tables)

    def test_migration_matches_the_model_columns(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        body = sql.split("CREATE TABLE IF NOT EXISTS public.tutor_turns (")[1].split("\n);")[0]
        sql_columns = {match.group(1) for match in re.finditer(r"^ (\w+) ", body, re.MULTILINE)}
        self.assertEqual(sql_columns, set(TutorTurn.__table__.columns.keys()))

    def test_migration_locks_the_table_down(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        for statement in ("ENABLE ROW LEVEL SECURITY", "REVOKE ALL ON public.tutor_turns FROM anon, authenticated",
                          "GRANT ALL ON public.tutor_turns TO service_role"):
            self.assertIn(statement, sql)


if __name__ == "__main__":
    unittest.main()
