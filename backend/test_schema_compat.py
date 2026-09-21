import unittest
from types import SimpleNamespace

from schema_compat import apply_schema_compatibility


class FakeConnection:
    def __init__(self, dialect_name="postgresql", scalar_value="integer"):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.scalar_value = scalar_value
        self.executed = []
        self.scalar_queries = []

    async def execute(self, statement):
        self.executed.append(str(statement))

    async def scalar(self, statement):
        self.scalar_queries.append(str(statement))
        return self.scalar_value


class SchemaCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_postgres_adds_legacy_columns_and_converts_integer_hours(self):
        connection = FakeConnection(scalar_value="integer")

        await apply_schema_compatibility(connection)

        sql = "\n".join(connection.executed)
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence", sql)
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery", sql)
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status", sql)
        self.assertIn("ALTER TABLE topics ADD COLUMN IF NOT EXISTS sort_order", sql)
        self.assertIn("ALTER TABLE subjects ALTER COLUMN hours_per_week TYPE double precision", sql)
        self.assertEqual(len(connection.scalar_queries), 1)

    async def test_postgres_does_not_rewrite_hours_when_already_double(self):
        connection = FakeConnection(scalar_value="double precision")

        await apply_schema_compatibility(connection)

        sql = "\n".join(connection.executed)
        self.assertNotIn("ALTER TABLE subjects ALTER COLUMN hours_per_week", sql)
        self.assertEqual(len(connection.scalar_queries), 1)

    async def test_non_postgres_does_nothing(self):
        connection = FakeConnection(dialect_name="sqlite", scalar_value=None)

        await apply_schema_compatibility(connection)

        self.assertEqual(connection.executed, [])
        self.assertEqual(connection.scalar_queries, [])


if __name__ == "__main__":
    unittest.main()
