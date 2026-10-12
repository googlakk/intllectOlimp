"""Run with CATALOG_TEST_POSTGRES_URL pointing to an isolated local database."""
import os
import unittest

from sqlalchemy import insert, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.schema import CreateColumn

from models import Section, Topic
from services.catalog import clear_subject_outline_cache, list_subject_outline


@unittest.skipUnless(os.getenv("CATALOG_TEST_POSTGRES_URL"), "isolated PostgreSQL not configured")
class CatalogPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_outline_loads_json_and_jsonb_blocks_without_returning_content(self):
        url = make_url(os.environ["CATALOG_TEST_POSTGRES_URL"])
        # Never reuse DATABASE_URL: development and production share that database.
        self.assertIn(url.host, ("127.0.0.1", "localhost"))
        self.assertEqual(url.database, "catalog_regression")
        engine = create_async_engine(url)
        try:
            for block_type in ("json", "jsonb"):
                with self.subTest(block_type=block_type):
                    clear_subject_outline_cache()
                    async with engine.connect() as connection:
                        for model in (Section, Topic):
                            columns = ", ".join(str(CreateColumn(column).compile(
                                dialect=postgresql.dialect(),
                            )) for column in model.__table__.columns)
                            await connection.execute(text(
                                f"CREATE TEMP TABLE {model.__tablename__} ({columns}) ON COMMIT DROP"
                            ))
                        await connection.execute(text(
                            "CREATE TEMP TABLE generated_lessons (id int, topic_id int, "
                            f"blocks {block_type}, status text, active_version_id bigint, "
                            "published_version_id bigint) ON COMMIT DROP"
                        ))
                        await connection.execute(insert(Section).values(
                            id=3, subject_id=1, name="Алгебра", sort_order=1, total_hours=9,
                        ))
                        await connection.execute(insert(Topic), [
                            {"id": n, "section_id": 3, "name": f"Тема {n}", "sort_order": n}
                            for n in range(1, 10)
                        ])
                        # Missing lesson, SQL NULL, JSON null, empty/nonempty arrays,
                        # legacy object/scalar, and active/published version markers.
                        await connection.execute(text(
                            "INSERT INTO generated_lessons VALUES "
                            "(2,2,NULL,'draft',NULL,NULL), "
                            "(3,3,'null','draft',NULL,NULL), "
                            "(4,4,'[]','draft',NULL,NULL), "
                            "(5,5,'[{\"component\":\"Text\"}]','draft',NULL,NULL), "
                            "(6,6,'{}','draft',NULL,NULL), "
                            "(7,7,'42','draft',NULL,NULL), "
                            "(8,8,'[]','draft',18,NULL), "
                            "(9,9,'[]','published',NULL,19)"
                        ))
                        async with AsyncSession(bind=connection) as db:
                            outline = await list_subject_outline(1, db)
                        topics = outline[0]["topics"]
                        self.assertEqual(len(topics), 9)
                        self.assertEqual([t["lesson_has_materials"] for t in topics],
                                         [False, False, False, False, True, False, False, True, False])
                        self.assertTrue(topics[-1]["lesson_has_published_version"])
                        self.assertIsNone(topics[0]["lesson_id"])
                        self.assertTrue(all("blocks" not in t for t in topics))
                        await connection.commit()
        finally:
            clear_subject_outline_cache()
            await engine.dispose()
