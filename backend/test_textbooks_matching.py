import unittest

from textbooks.matching import SectionInfo, ktp_references, stems, suggest_sections

CHIO = [
    SectionInfo(1, "§ 1", "Личность и её структура", 6, 13, "Личность — социальная сущность человека. Индивидуальность, темперамент, характер."),
    SectionInfo(2, "§ 2", "Факторы формирования личности", 14, 18, "Наследственность, среда, воспитание, самовоспитание."),
    SectionInfo(3, "§ 3", "Представления человека о самом себе (Я-концепция)", 19, 24, "Самооценка, самопознание, образ себя."),
    SectionInfo(5, "§ 5", "Буллинг", 31, 41, "Травля в школе, как распознать и остановить буллинг."),
    SectionInfo(6, "§ 6", "Структура общества", 42, 48, "Социальные группы, институты, социальная стратификация."),
]
PHYSICS = [
    SectionInfo(11, "1.2", "Плотность вещества", 20, 24, "Плотность — масса вещества в единице объёма. ρ = m/V."),
    SectionInfo(12, "1.3", "Давление твёрдых тел", 25, 30, "Давление — сила, действующая на единицу площади."),
]


class MatchingTests(unittest.TestCase):
    def test_ktp_reference_by_number_and_pages(self):
        self.assertEqual(ktp_references(CHIO, "Учебник, § 5"), [5])
        self.assertEqual(ktp_references(PHYSICS, "п. 1.3"), [12])
        self.assertEqual(ktp_references(CHIO, "стр. 17–20"), [2, 3])
        self.assertEqual(ktp_references(CHIO, "Презентация, видео"), [])

    def test_ordinary_words_and_years_are_not_references(self):
        for text in ("Задачи 8 класс 7 четверть", "Лабораторная работа №2, с 10 минут", "Кыргызстан с 1991 года", "тип. 3", "§ 12"):
            self.assertEqual(ktp_references(CHIO, text), [], text)
        self.assertEqual(ktp_references(CHIO, "с. 31"), [5])

    def test_repeated_numbers_are_ambiguous(self):
        parts = [SectionInfo(1, "§ 1", "Часть I", 5, 9), SectionInfo(2, "§ 1", "Часть II", 60, 64)]
        self.assertEqual(ktp_references(parts, "§ 1"), [])

    def test_different_wording_still_matches_by_objectives(self):
        suggestions = suggest_sections("Масса и плотность", "Ученик вычисляет плотность вещества по массе и объёму", "", PHYSICS)
        self.assertEqual(suggestions[0].section_id, 11)
        self.assertEqual(suggestions[0].source, "match")

    def test_topic_matches_its_paragraph(self):
        suggestions = suggest_sections("Что такое травля и как ей противостоять", "распознавать буллинг в школе", "", CHIO)
        self.assertEqual([s.section_id for s in suggestions][:1], [5])
        suggestions = suggest_sections("Самооценка и самопознание", "", "", CHIO)
        self.assertEqual(suggestions[0].section_id, 3)

    def test_ktp_reference_wins_and_unrelated_topic_gets_nothing(self):
        self.assertEqual(suggest_sections("Буллинг", "", "§ 6", CHIO)[0].source, "ktp")
        self.assertEqual(suggest_sections("Контрольная работа по разделу", "", "", CHIO), [])

    def test_generic_words_are_ignored(self):
        self.assertEqual(stems("Урок: основные понятия темы"), set())


if __name__ == "__main__":
    unittest.main()
