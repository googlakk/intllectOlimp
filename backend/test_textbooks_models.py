import unittest

from models import Base
from textbooks.models import TextbookBase


class TextbookModelsTests(unittest.TestCase):
    def test_tables_are_not_created_at_startup(self):
        # create_all при старте работает с Base: таблицы учебников — только миграцией.
        names = {"textbooks", "textbook_pages", "textbook_sections", "textbook_items", "topic_textbook_links"}
        self.assertTrue(names.isdisjoint(Base.metadata.tables))
        self.assertEqual(names, set(TextbookBase.metadata.tables))


if __name__ == "__main__":
    unittest.main()
