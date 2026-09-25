"""Длинная ячейка темы в КТП: тема + все подпункты + практические работы.

Повод: КТП по географии, строки 13 и 15 — названия по 681 и 830 символов.
Поле темы в базе — 500 символов, импорт падал с 500, а слово «Анализ»
из подпунктов помечало тему как сомнительную по типу занятия.
"""

import unittest

from topic_semantics import TOPIC_TITLE_LIMIT, ambiguous_lesson_name, join_topic_details, split_topic_title

RELIEF = (
    "Рельеф, геологическое строение и полезные ископаемые. Орография. Эпохи горообразования. "
    "Геохронологическая таблица. История геологического развития территории. Преобладающие формы рельефа. "
    "Полезные ископаемые (минеральные ресурсы). Опасные природные явления, связанные с рельефом: оползни, "
    "лавины, землетрясения, сели, эрозия. Меры защиты от опасных природных явлений. Практическая работа № 2. "
    "Нанесение на контурную карту основных хребтов, высоких точек хребтов, долин и месторождений полезных "
    "ископаемых. Практическая (творческая) работа № 3-4. Анализ возможностей использования полезных ископаемых "
    "в хозяйстве своей области, района и разработка рекомендаций по их использованию."
)
WATERS = (
    "Внутренние воды и водные ресурсы. Условия образования и главные типы внутренних вод. Главные речные "
    "системы и бассейны рек. Питание и режим рек. Ледники и их типы, размеры, режим. Многолетняя мерзлота. "
    "Водохранилища и каналы. Практическая работа № 6. Нанесение на контурную карту крупных рек, ледников, озер. "
    "Практическая (исследовательская) работа № 7. Анализ обеспеченности водными ресурсами своей местности"
)


class TopicTitleSplitTests(unittest.TestCase):
    def test_long_cell_keeps_the_first_sentence_as_title(self):
        title, details = split_topic_title(RELIEF)
        self.assertEqual(title, "Рельеф, геологическое строение и полезные ископаемые")
        self.assertTrue(details.startswith("Орография"))
        self.assertIn("Практическая работа № 2", details)

    def test_words_in_details_no_longer_flag_the_lesson_type(self):
        self.assertTrue(ambiguous_lesson_name(WATERS))
        title, _ = split_topic_title(WATERS)
        self.assertEqual(title, "Внутренние воды и водные ресурсы")
        self.assertFalse(ambiguous_lesson_name(title))

    def test_short_names_are_untouched(self):
        name = "Физико-географическая область Юго-Западный Тенир-Тоо"
        self.assertEqual(split_topic_title(name), (name, ""))

    def test_long_single_sentence_is_cut_at_a_word(self):
        title, details = split_topic_title("слово " * 80)
        self.assertLessEqual(len(title), TOPIC_TITLE_LIMIT)
        self.assertTrue(details)

    def test_details_go_before_existing_resources(self):
        self.assertEqual(join_topic_details("Подпункты", "Учебник §5"), "Подпункты\n\nУчебник §5")
        self.assertEqual(join_topic_details("", "Учебник §5"), "Учебник §5")


if __name__ == "__main__":
    unittest.main()
