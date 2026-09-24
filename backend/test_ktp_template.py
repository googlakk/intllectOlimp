import io
import unittest

from openpyxl import Workbook

from ktp.extract import extract_xlsx
from ktp.mapper import map_to_schema
from ktp.template import is_standard_template, map_standard_template


def template_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КТП"
    sheet.append(["Календарно-тематический план"])
    sheet.append([""])
    sheet.append(["Предмет", "Математика"])
    sheet.append(["Класс", 7])
    sheet.append(["Язык обучения", "ru"])
    sheet.append(["Часов в неделю", 4])
    sheet.append(["Часов в год", 3])
    sheet.append([""])
    sheet.append([
        "Раздел", "№ урока", "Тема урока", "Часы", "Тип урока",
        "Цели обучения", "Навыки", "Ресурсы", "Примечание",
    ])
    sheet.append(["Числа", "1", "Целые числа", 2, "Изучение", "Сравнивать числа", "сравнение; вычисление", "§1", ""])
    sheet.append(["", "2", "Контрольная работа", 1, "Контроль", "Применять правила", "", "", ""])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


class KtpTemplateTests(unittest.IsolatedAsyncioTestCase):
    def test_extracts_and_maps_official_xlsx_without_llm(self):
        extraction = extract_xlsx(template_bytes())
        self.assertTrue(is_standard_template(extraction))

        draft = map_standard_template(extraction)
        self.assertEqual(draft["subject_name"], "Математика")
        self.assertEqual(draft["grade"], 7)
        self.assertEqual(draft["hours_per_year"], 3)
        self.assertEqual(len(draft["sections"]), 1)
        self.assertEqual(len(draft["sections"][0]["topics"]), 2)
        self.assertEqual(draft["sections"][0]["topics"][1]["lesson_type"], "assessment")
        self.assertEqual(draft["sections"][0]["topics"][0]["skills"], ["сравнение", "вычисление"])

    async def test_mapper_uses_deterministic_template_path(self):
        draft = await map_to_schema(extract_xlsx(template_bytes()))
        self.assertEqual(draft["subject_name"], "Математика")
        self.assertEqual(draft["sections"][0]["total_hours"], 3)


if __name__ == "__main__":
    unittest.main()
