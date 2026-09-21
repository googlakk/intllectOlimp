"""Тесты сборки плана по карте колонок.

Сборка детерминирована, поэтому проверяется целиком — от файла до черновика.
Через модель проходит только карта колонок, поэтому в тестах она задана
руками: ровно то, что модель должна вернуть для этих двух документов.
"""

import unittest
from pathlib import Path

from ktp.assemble import ColumnMap, assemble
from ktp.columns import to_column_maps
from ktp.extract import Extraction, extract
from ktp.mapper import build_draft

SAMPLES = Path(__file__).parent / "testdata"
LITERATURE = SAMPLES / "literature.docx"
MATH = SAMPLES / "math.pdf"

LITERATURE_PAYLOAD = {
    "subject_name": "Литература", "grade": 8, "hours_per_week": 1.8,
    "hours_per_year": 61, "instruction_language": "ru", "notes": [],
    "tables": [
        {"table_index": 0, "is_plan": True, "header_rows": 3, "name": 1, "hours": 2,
         "number": 0, "number_in_name": False, "objectives": 5, "skills": [6],
         "resources": 9, "note": 8},
        {"table_index": 1, "is_plan": False, "header_rows": 1, "name": 1, "hours": -1,
         "number": 0, "number_in_name": False, "objectives": -1, "skills": [],
         "resources": -1, "note": -1},
    ],
}

MATH_PAYLOAD = {
    "subject_name": "Математика", "grade": 7, "hours_per_week": 4,
    "hours_per_year": 0, "instruction_language": "ru", "notes": [],
    "tables": [
        {"table_index": 0, "is_plan": True, "header_rows": 2, "name": 0, "hours": 1,
         "number": -1, "number_in_name": True, "objectives": 4, "skills": [8],
         "resources": 6, "note": -1},
        {"table_index": 1, "is_plan": True, "header_rows": 0, "name": 0, "hours": 1,
         "number": -1, "number_in_name": True, "objectives": 4, "skills": [6],
         "resources": 5, "note": -1},
    ],
}


def _table(rows):
    return Extraction(source_kind="docx", header_text="", tables=[rows])


class ColumnMapTests(unittest.TestCase):
    def test_minus_one_means_no_such_column(self):
        maps, _ = to_column_maps({"tables": [dict(MATH_PAYLOAD["tables"][0])]})
        self.assertIsNone(maps[0].number)
        self.assertTrue(maps[0].number_in_name)

    def test_service_tables_are_dropped(self):
        maps, _ = to_column_maps(LITERATURE_PAYLOAD)
        self.assertEqual([m.table_index for m in maps], [0])

    def test_no_plan_table_is_an_error(self):
        with self.assertRaises(ValueError):
            to_column_maps({"tables": [{"table_index": 0, "is_plan": False, "name": 0}]})

    def test_table_without_name_column_is_reported_not_silently_dropped(self):
        payload = {"tables": [
            {"table_index": 0, "is_plan": True, "name": -1},
            dict(MATH_PAYLOAD["tables"][0]),
        ]}
        maps, problems = to_column_maps(payload)
        self.assertEqual(len(maps), 1)
        self.assertTrue(any("названием" in p for p in problems))


class AssembleUnitTests(unittest.TestCase):
    def test_section_row_has_no_number_and_no_hours(self):
        rows = [["", "ВВЕДЕНИЕ (2 Ч.)", "", ""], ["1", "Тема", "1", "цель"]]
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=3, header_rows=0)
        result = assemble(_table(rows), mapping)
        self.assertEqual(len(result["sections"]), 1)
        self.assertEqual(result["sections"][0]["name"], "ВВЕДЕНИЕ")
        self.assertEqual(result["sections"][0]["total_hours"], 2)

    def test_number_taken_from_start_of_name(self):
        rows = [["1.1. Четыре операции", "4", "цель"]]
        mapping = ColumnMap(name=0, hours=1, objectives=2, header_rows=0, number_in_name=True)
        topic = assemble(_table(rows), mapping)["sections"][0]["topics"][0]
        self.assertEqual(topic["ktp_number"], "1.1")
        self.assertEqual(topic["name"], "Четыре операции")

    def test_objectives_are_copied_verbatim(self):
        text = "Оценивать, складывать и вычитать целые числа, распознавая обобщения."
        rows = [["1", "Тема", "1", text]]
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=3, header_rows=0)
        topic = assemble(_table(rows), mapping)["sections"][0]["topics"][0]
        self.assertEqual(topic["learning_objectives"], text)

    def test_missing_objectives_stay_empty_and_are_reported(self):
        rows = [["1", "Ключевые идеи", "1", ""]]
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=3, header_rows=0)
        result = assemble(_table(rows), mapping)
        self.assertEqual(result["sections"][0]["topics"][0]["learning_objectives"], "")
        self.assertTrue(any("без целей" in w for w in result["warnings"]))

    def test_skills_split_by_bullets(self):
        rows = [["1", "Тема", "1", "● Обобщение ● Специализация"]]
        mapping = ColumnMap(name=1, hours=2, number=0, skills=[3], header_rows=0)
        topic = assemble(_table(rows), mapping)["sections"][0]["topics"][0]
        self.assertEqual(topic["skills"], ["Обобщение", "Специализация"])

    def test_uud_split_into_separate_items(self):
        # Без разрезания это один нечитаемый абзац в карточке урока.
        text = ("Познавательные: уметь искать информацию. "
                "Регулятивные: выбирать действия. "
                "Коммуникативные: уметь ставить вопросы")
        rows = [["1", "Тема", "1", text]]
        mapping = ColumnMap(name=1, hours=2, number=0, skills=[3], header_rows=0)
        topic = assemble(_table(rows), mapping)["sections"][0]["topics"][0]
        self.assertEqual(len(topic["skills"]), 3)
        self.assertTrue(topic["skills"][1].startswith("Регулятивные:"))

    def test_plain_skill_text_is_not_chopped_up(self):
        rows = [["1", "Тема", "1", "Умение анализировать текст произведения"]]
        mapping = ColumnMap(name=1, hours=2, number=0, skills=[3], header_rows=0)
        topic = assemble(_table(rows), mapping)["sections"][0]["topics"][0]
        self.assertEqual(topic["skills"], ["Умение анализировать текст произведения"])

    def test_lesson_type_from_name(self):
        rows = [["1", "Контрольная работа № 1", "1"],
                ["2", "Защита проекта", "1"],
                ["3", "Анализ стихотворения", "1"]]
        mapping = ColumnMap(name=1, hours=2, number=0, header_rows=0)
        types = [t["lesson_type"] for t in assemble(_table(rows), mapping)["sections"][0]["topics"]]
        self.assertEqual(types, ["assessment", "project", "study"])

    def test_topics_before_first_section_are_kept_not_dropped(self):
        rows = [["1", "Тема без раздела", "1"]]
        mapping = ColumnMap(name=1, hours=2, number=0, header_rows=0)
        result = assemble(_table(rows), mapping)
        self.assertEqual(result["total_topics"], 1)
        self.assertTrue(any("до первого заголовка" in w for w in result["warnings"]))

    def test_every_section_has_a_name_for_import(self):
        # SectionInput требует непустое имя — пустое уронило бы загрузку в базу.
        rows = [["1", "Тема без раздела", "1"], ["", "ГЛАВА", ""], ["2", "Тема", "1"]]
        mapping = ColumnMap(name=1, hours=2, number=0, header_rows=0)
        for section in assemble(_table(rows), mapping)["sections"]:
            self.assertTrue(section["name"].strip())

    def test_section_hours_mismatch_is_reported(self):
        rows = [["", "ГЛАВА (5 ч)", ""], ["1", "Тема", "2"], ["2", "Тема", "2"]]
        mapping = ColumnMap(name=1, hours=2, number=0, header_rows=0)
        result = assemble(_table(rows), mapping)
        self.assertTrue(any("в заголовке 5 ч, по темам 4 ч" in w for w in result["warnings"]))

    def test_section_continues_across_tables(self):
        # Разрыв страницы в PDF: раздел начался в одной таблице, темы во второй.
        extraction = Extraction(
            source_kind="pdf", header_text="",
            tables=[[["", "ГЛАВА 1", ""], ["1", "Тема A", "1"]], [["2", "Тема B", "1"]]],
        )
        maps = [ColumnMap(name=1, hours=2, number=0, header_rows=0, table_index=0),
                ColumnMap(name=1, hours=2, number=0, header_rows=0, table_index=1)]
        result = assemble(extraction, maps)
        self.assertEqual(len(result["sections"]), 1)
        self.assertEqual(len(result["sections"][0]["topics"]), 2)

    def test_sort_order_is_continuous_across_sections(self):
        rows = [["", "A", ""], ["1", "Тема", "1"], ["", "B", ""], ["2", "Тема", "1"]]
        mapping = ColumnMap(name=1, hours=2, number=0, header_rows=0)
        result = assemble(_table(rows), mapping)
        orders = [t["sort_order"] for s in result["sections"] for t in s["topics"]]
        self.assertEqual(orders, [1, 2])


@unittest.skipUnless(LITERATURE.is_file(), "нет testdata/literature.docx")
class LiteratureEndToEndTests(unittest.TestCase):
    """Сквозная проверка на настоящем КТП — без обращения к модели."""

    @classmethod
    def setUpClass(cls):
        extraction = extract(LITERATURE.read_bytes(), LITERATURE.name)
        cls.draft = build_draft(extraction, LITERATURE_PAYLOAD)
        cls.topics = [t for s in cls.draft["sections"] for t in s["topics"]]

    def test_all_sixty_one_lessons_are_present(self):
        self.assertEqual(len(self.topics), 61)

    def test_all_twenty_eight_sections_are_present(self):
        self.assertEqual(len(self.draft["sections"]), 28)

    def test_hours_match_the_document_header(self):
        self.assertEqual(self.draft["hours_per_year"], 61)
        self.assertEqual(self.draft["hours_per_week"], 1.8)

    def test_numbers_run_from_one_to_sixty_one_without_gaps(self):
        numbers = [int(t["ktp_number"]) for t in self.topics]
        self.assertEqual(numbers, list(range(1, 62)))

    def test_objectives_column_is_taken_by_content_not_by_label(self):
        # Колонка подписана «Личностные», но внутри предметные результаты.
        first = self.topics[0]["learning_objectives"]
        self.assertTrue(first.startswith("Научиться определять идейно-исторический"))

    def test_personal_results_did_not_leak_into_objectives(self):
        leaked = [t for t in self.topics
                  if t["learning_objectives"].startswith("Формирование")]
        self.assertEqual(leaked, [])

    def test_every_topic_has_objectives(self):
        empty = [t["ktp_number"] for t in self.topics if not t["learning_objectives"]]
        self.assertEqual(empty, [])

    def test_section_names_are_verbatim_from_the_document(self):
        names = [s["name"] for s in self.draft["sections"]]
        self.assertIn("ВВЕДЕНИЕ", names)
        self.assertIn("АЛЕКСАНДР СЕРГЕЕВИЧ ПУШКИН", names)
        for name in names:
            self.assertNotIn("продолжение", name.lower())

    def test_control_lessons_are_marked_as_assessment(self):
        control = [t for t in self.topics if "Контрольная работа" in t["name"]]
        self.assertTrue(control)
        for topic in control:
            self.assertEqual(topic["lesson_type"], "assessment")


@unittest.skipUnless(MATH.is_file(), "нет testdata/math.pdf")
class MathEndToEndTests(unittest.TestCase):
    """Тот же конвейер на PDF с другой структурой колонок."""

    @classmethod
    def setUpClass(cls):
        extraction = extract(MATH.read_bytes(), MATH.name)
        cls.draft = build_draft(extraction, MATH_PAYLOAD)
        cls.topics = [t for s in cls.draft["sections"] for t in s["topics"]]

    def test_all_eighty_seven_topics_are_present(self):
        self.assertEqual(len(self.topics), 87)

    def test_total_hours(self):
        self.assertEqual(self.draft["hours_per_year"], 136)

    def test_numbers_extracted_from_name_prefix(self):
        self.assertEqual(self.topics[0]["ktp_number"], "1.1")
        self.assertEqual(self.topics[0]["name"], "Четыре операции над целыми числами")

    def test_section_hours_parsed_from_tail(self):
        first = self.draft["sections"][0]
        self.assertEqual(first["name"], "Глава 1. Числа")
        self.assertEqual(first["total_hours"], 12)

    def test_topics_without_objectives_are_reported_not_invented(self):
        empty = [t for t in self.topics if not t["learning_objectives"]]
        self.assertTrue(empty, "в этом КТП есть строки с пустыми целями")
        self.assertTrue(any("без целей" in w for w in self.draft["warnings"]))


if __name__ == "__main__":
    unittest.main()
