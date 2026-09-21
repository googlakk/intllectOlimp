"""Проверка карты колонок по содержимому ячеек.

Повод — настоящий случай. Модель в предупреждениях написала: «колонка 5
подписана "Личностные", но содержит цели обучения», а в карту поставила
objectives = 7. Во всех 61 теме целью стало «Формирование мотивации к
обучению». Структура при этом была безупречна, и сверка ничего не заметила:
текст-то дословный, просто не тот.

Отсюда правило: модель предлагает карту, код её проверяет.
"""

import unittest
from pathlib import Path

from ktp.assemble import ColumnMap
from ktp.extract import Extraction, extract
from ktp.mapper import build_draft
from ktp.validate import classify_column, verify_objectives_column

LITERATURE = Path(__file__).parent / "testdata" / "literature.docx"
MATH = Path(__file__).parent / "testdata" / "math.pdf"

# Карта ровно в том виде, в каком её вернула модель на живом разборе.
MODEL_ANSWER_LITERATURE = {
    "subject_name": "Литература", "grade": 8, "hours_per_week": 1.8,
    "hours_per_year": 61, "instruction_language": "ru", "notes": [],
    "tables": [{
        "table_index": 0, "is_plan": True, "header_rows": 3, "name": 1, "hours": 2,
        "number": 0, "number_in_name": False,
        "objectives": 7,          # ← ошибка модели: тут личностные результаты
        "skills": [5, 6],         # ← а цели лежат в колонке 5
        "resources": 9, "note": 8,
    }],
}

CORRECT_LITERATURE = {
    **MODEL_ANSWER_LITERATURE,
    "tables": [{**MODEL_ANSWER_LITERATURE["tables"][0],
                "objectives": 5, "skills": [6], "note": 7}],
}


class ClassifyTests(unittest.TestCase):
    def test_objectives_recognised_by_opening_verb(self):
        profile = classify_column([
            "Научиться определять идейно-исторический замысел произведения",
            "Уметь анализировать стихотворный текст",
            "Оценивать, складывать и вычитать целые числа",
        ])
        self.assertEqual(profile["objective"], 1.0)
        self.assertEqual(profile["personal"], 0.0)

    def test_personal_results_recognised(self):
        profile = classify_column([
            "Формирование «стартовой» мотивации к обучению",
            "Формирование навыков исследовательской деятельности",
            "Воспитание чувства ответственности за свои поступки",
        ])
        self.assertEqual(profile["personal"], 1.0)
        self.assertEqual(profile["objective"], 0.0)

    def test_uud_recognised(self):
        profile = classify_column([
            "Познавательные: уметь искать и выделять необходимую информацию",
            "Регулятивные: выбирать действия в соответствии с задачей",
        ])
        self.assertEqual(profile["uud"], 1.0)

    def test_empty_column_is_not_judged(self):
        self.assertEqual(classify_column([])["samples"], 0)


class VerifyUnitTests(unittest.TestCase):
    @staticmethod
    def _extraction(objective_column: int, personal_column: int):
        rows = []
        for i in range(10):
            row = ["", ""] * 0 + [str(i), f"Тема {i}", "1", "", "", "", "", "", ""]
            row[objective_column] = f"Научиться определять признак номер {i}"
            row[personal_column] = f"Формирование устойчивой мотивации номер {i}"
            rows.append(row)
        return Extraction(source_kind="docx", header_text="", tables=[rows])

    def test_wrong_objectives_column_is_swapped(self):
        extraction = self._extraction(objective_column=5, personal_column=7)
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=7, skills=[5], header_rows=0)
        fixed, warnings = verify_objectives_column(extraction, mapping)
        self.assertEqual(fixed.objectives, 5)
        self.assertNotIn(5, fixed.skills)
        self.assertTrue(warnings)

    def test_correct_objectives_column_is_left_alone(self):
        extraction = self._extraction(objective_column=5, personal_column=7)
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=5, note=7, header_rows=0)
        fixed, warnings = verify_objectives_column(extraction, mapping)
        self.assertEqual(fixed.objectives, 5)
        self.assertEqual(warnings, [])

    def test_displaced_column_is_not_thrown_away(self):
        extraction = self._extraction(objective_column=5, personal_column=7)
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=7, skills=[5], header_rows=0)
        fixed, _ = verify_objectives_column(extraction, mapping)
        self.assertTrue(fixed.note == 7 or 7 in fixed.skills,
                        "личностные результаты должны куда-то попасть, а не пропасть")

    def test_no_swap_when_there_is_no_better_candidate(self):
        rows = [[str(i), f"Тема {i}", "1", "Формирование мотивации"] for i in range(10)]
        extraction = Extraction(source_kind="docx", header_text="", tables=[rows])
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=3, header_rows=0)
        fixed, warnings = verify_objectives_column(extraction, mapping)
        self.assertEqual(fixed.objectives, 3, "менять не на что — трогать нельзя")
        self.assertTrue(any("вручную" in w for w in warnings))

    def test_too_few_rows_to_judge(self):
        rows = [["1", "Тема", "1", "Формирование мотивации"]]
        extraction = Extraction(source_kind="docx", header_text="", tables=[rows])
        mapping = ColumnMap(name=1, hours=2, number=0, objectives=3, header_rows=0)
        fixed, warnings = verify_objectives_column(extraction, mapping)
        self.assertEqual(fixed.objectives, 3)
        self.assertEqual(warnings, [])


@unittest.skipUnless(LITERATURE.is_file(), "нет testdata/literature.docx")
class LiteratureRegressionTests(unittest.TestCase):
    """Тот самый разбор, что уехал в черновик с неверными целями."""

    @classmethod
    def setUpClass(cls):
        cls.extraction = extract(LITERATURE.read_bytes(), LITERATURE.name)

    def _topics(self, payload):
        draft = build_draft(self.extraction, payload)
        return draft, [t for s in draft["sections"] for t in s["topics"]]

    def test_model_mistake_is_corrected(self):
        draft, topics = self._topics(MODEL_ANSWER_LITERATURE)
        self.assertEqual(len(topics), 61)
        leaked = [t for t in topics if t["learning_objectives"].startswith("Формирование")]
        self.assertEqual(leaked, [], "личностные результаты снова попали в цели")
        self.assertTrue(topics[0]["learning_objectives"].startswith("Научиться определять"))

    def test_correction_is_announced_not_silent(self):
        draft, _ = self._topics(MODEL_ANSWER_LITERATURE)
        self.assertTrue(
            any("исправлена по содержимому" in w for w in draft["warnings"]),
            "молча подменять колонку нельзя — это должно быть видно",
        )

    def test_correct_map_is_not_broken_by_the_check(self):
        draft, topics = self._topics(CORRECT_LITERATURE)
        self.assertTrue(topics[0]["learning_objectives"].startswith("Научиться определять"))
        self.assertFalse(any("исправлена по содержимому" in w for w in draft["warnings"]))

    def test_both_maps_give_the_same_objectives(self):
        _, from_wrong = self._topics(MODEL_ANSWER_LITERATURE)
        _, from_right = self._topics(CORRECT_LITERATURE)
        self.assertEqual(
            [t["learning_objectives"] for t in from_wrong],
            [t["learning_objectives"] for t in from_right],
        )

    def test_structure_survives_the_correction(self):
        draft, topics = self._topics(MODEL_ANSWER_LITERATURE)
        self.assertEqual(len(draft["sections"]), 28)
        self.assertEqual(draft["hours_per_year"], 61)


@unittest.skipUnless(MATH.is_file(), "нет testdata/math.pdf")
class MathNotBrokenTests(unittest.TestCase):
    """У математики карта верная — проверка не должна в неё лезть."""

    def test_correct_math_map_is_untouched(self):
        from test_ktp_assemble import MATH_PAYLOAD
        extraction = extract(MATH.read_bytes(), MATH.name)
        draft = build_draft(extraction, MATH_PAYLOAD)
        topics = [t for s in draft["sections"] for t in s["topics"]]
        self.assertEqual(len(topics), 87)
        self.assertTrue(topics[0]["learning_objectives"].startswith("Оценивать"))
        self.assertFalse(any("исправлена по содержимому" in w for w in draft["warnings"]))


if __name__ == "__main__":
    unittest.main()
