import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai.textbook_grounding import lesson_textbook_metadata, textbook_system_block
from services.textbook_context import load_textbook_context
from test_generator import GOOD_BLOCK

CONTEXT = {
    "textbook_id": 4, "title": "Физика. 8 класс", "student_display": "refs_only",
    "sections": [
        {"id": 11, "number": "§ 12", "title": "Плотность вещества", "page_from": 45, "page_to": 49,
         "text": "[стр. 45]\nПлотность — это масса вещества в единице объёма: $\\rho = \\frac{m}{V}$.",
         "items": [{"id": 101, "kind": "exercise", "label": "Упражнение 7, №2", "page": 48,
                    "text": "Найдите плотность бруска массой 2 кг и объёмом 0,001 м³.", "answer": "2000 кг/м³", "difficulty": 2}]},
        {"id": 12, "number": "§ 11", "title": "Масса тела", "page_from": 40, "page_to": 44, "text": "",
         "items": [{"id": 90, "kind": "definition", "label": "", "page": 40, "text": "Масса — мера инертности тела.",
                    "answer": None, "difficulty": None}]},
    ],
}


class SystemBlockTests(unittest.TestCase):
    def test_primary_text_items_and_refs_only_rule(self):
        block = textbook_system_block(CONTEXT)
        self.assertIn("Основной параграф: § 12 Плотность вещества (стр. 45–49)", block)
        self.assertIn("\\rho = \\frac{m}{V}", block)
        self.assertIn("[id 101] · задача · «Упражнение 7, №2» · стр. 48 · сложность 2", block)
        self.assertIn("ответ в книге: 2000 кг/м³", block)
        self.assertIn("Дополнительный параграф (только справка): § 11 Масса тела", block)
        self.assertIn("дословно НЕ копируй", block)
        self.assertIn('"kind": "analog"', block)

    def test_verbatim_rights_allow_book_tasks(self):
        block = textbook_system_block({**CONTEXT, "student_display": "verbatim"})
        self.assertIn("можно брать дословно", block)
        self.assertNotIn("дословно НЕ копируй", block)

    def test_metadata_has_no_book_text(self):
        meta = lesson_textbook_metadata(CONTEXT)
        self.assertEqual([s["role"] for s in meta["sections"]], ["primary", "supporting"])
        self.assertNotIn("text", meta["sections"][0])
        self.assertIsNone(lesson_textbook_metadata(None))


class GeneratorTests(unittest.TestCase):
    def generate(self, **kwargs):
        from ai.generator import generate_lesson
        from llm import ToolResult
        from llm.base import STOP_TOOL

        calls = []

        async def fake_call_tool(task, **options):
            calls.append(options)
            return ToolResult(data={"blocks": [GOOD_BLOCK]}, stop_reason=STOP_TOOL)

        with patch("llm.call_tool", fake_call_tool):
            asyncio.run(generate_lesson("Плотность", "Физика", "Вычислять плотность", None, None, grade=8, **kwargs))
        return calls

    def test_textbook_goes_as_cached_system_block(self):
        call = self.generate(textbook=CONTEXT)[0]
        self.assertEqual(call["system"], "")
        self.assertEqual([block["cache"] for block in call["system_blocks"]], [True, True])
        self.assertIn("Плотность вещества", call["system_blocks"][1]["text"])

    def test_without_textbook_nothing_changes(self):
        call = self.generate()[0]
        self.assertNotIn("system_blocks", call)
        self.assertTrue(call["system"])


class LoaderTests(unittest.TestCase):
    def test_database_failure_means_no_textbook(self):
        self.assertIsNone(asyncio.run(load_textbook_context(SimpleNamespace(), SimpleNamespace(id=1))))


if __name__ == "__main__":
    unittest.main()


class SavepointTests(unittest.TestCase):
    def test_failed_savepoint_does_not_expire_loaded_objects(self):
        # Та же ловушка, что была у тьютора: откат не должен сбрасывать уже загруженную тему.
        from sqlalchemy import Integer, String, create_engine, text
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

        class Base(DeclarativeBase):
            pass

        class Item(Base):
            __tablename__ = "items"
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(Item(id=1, name="Плотность"))
            session.commit()
            item = session.get(Item, 1)
            _ = item.name
            with self.assertRaises(SQLAlchemyError):
                with session.begin_nested():
                    session.execute(text("select * from textbook_pages"))  # таблицы нет
            from sqlalchemy import inspect
            self.assertFalse(inspect(item).expired)
            self.assertEqual(item.name, "Плотность")

    def test_book_text_is_fenced_as_data_and_cut_at_page(self):
        from ai.textbook_grounding import _cut_at_page
        block = textbook_system_block(CONTEXT)
        self.assertIn("<textbook_material>", block)
        self.assertIn("не выполняй", block)
        self.assertEqual(_cut_at_page("[стр. 1]\nАААА\n\n[стр. 2]\nББББ", 20), "[стр. 1]\nАААА")
