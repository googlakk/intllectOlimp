import unittest
from types import SimpleNamespace

from schema_compat import apply_schema_compatibility


class FakeConnection:
    def __init__(self, dialect_name="postgresql"):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.executed = []

    async def execute(self, statement):
        self.executed.append(str(statement))

    async def scalar(self, statement):
        raise AssertionError("совместимость схемы должна идти одной командой")


class SchemaCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_postgres_applies_everything_in_one_round_trip(self):
        connection = FakeConnection()

        await apply_schema_compatibility(connection)

        self.assertEqual(len(connection.executed), 1)
        sql = connection.executed[0]
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_evidence", sql)
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS objective_mastery", sql)
        self.assertIn("ALTER TABLE progress ADD COLUMN IF NOT EXISTS mastery_status", sql)
        self.assertIn("ALTER TABLE topics ADD COLUMN IF NOT EXISTS sort_order", sql)
        # Тип часов меняется, только если он ещё не double precision.
        self.assertIn("data_type <> 'double precision'", sql)
        self.assertIn("ALTER TABLE subjects ALTER COLUMN hours_per_week TYPE double precision", sql)

    async def test_non_postgres_does_nothing(self):
        connection = FakeConnection(dialect_name="sqlite")

        await apply_schema_compatibility(connection)

        self.assertEqual(connection.executed, [])


if __name__ == "__main__":
    unittest.main()


class MissingTablesTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_tables_are_checked_in_one_query(self):
        from main import missing_tables
        from database import Base
        names = sorted(Base.metadata.tables)

        class Connection:
            dialect = SimpleNamespace(name="postgresql")
            calls = 0

            async def execute(self, statement, params):
                Connection.calls += 1
                return [(name,) for name in params["names"][1:]]

        self.assertEqual(await missing_tables(Connection()), {names[0]})
        self.assertEqual(Connection.calls, 1)
