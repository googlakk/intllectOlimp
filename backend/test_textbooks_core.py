import unittest

from textbooks.cleanup import clean_page_text, fix_lookalikes, fix_mojibake
from textbooks.extract import PageText, page_is_scan, render_scale
from textbooks.items import parse_items
from textbooks.ocr import parse_ocr_page
from textbooks.toc import TocEntry, build_sections, calibrate_offset, find_toc_pages, parse_toc_entries


class CleanupTests(unittest.TestCase):
    def test_history_cp1251_read_as_latin1_is_repaired(self):
        self.assertEqual(fix_mojibake("§ 1. ÇÀÂÎÅÂÀÍÈÅ ÞÆÍÎÃÎ ÊÛÐÃÛÇÑÒÀÍÀ"), "§ 1. ЗАВОЕВАНИЕ ЮЖНОГО КЫРГЫЗСТАНА")
        self.assertEqual(fix_mojibake("Café au lait"), "Café au lait")  # обычный латинский текст не трогаем

    def test_glyph_garbage_and_lookalikes(self):
        raw = "(cid:17)(cid:10)\n/g44/g3/g605\nê ïðÿìîé arpeccèè ïóòåì"
        self.assertEqual(clean_page_text(raw), "к прямой агрессии путем")

    def test_formulas_keep_latin_symbols(self):
        self.assertEqual(fix_lookalikes("давление $p_{атм}$ и слово Мapс"), "давление $p_{атм}$ и слово Марс")
        self.assertEqual(fix_lookalikes("CO2 и pH"), "CO2 и pH")

    def test_watermarks_are_removed(self):
        raw = "ГЕОГРАФИЧЕСКОЕ ПОЛОЖЕНИЕ wwwwww..bbiizzddiinn..kkgg\n1.2. Границы\nСкачан с vk.com/material100\nТекст"
        self.assertEqual(clean_page_text(raw), "ГЕОГРАФИЧЕСКОЕ ПОЛОЖЕНИЕ\n1.2. Границы\nТекст")

    def test_hyphenation_joined_only_before_lowercase(self):
        self.assertEqual(clean_page_text("обязательно форми-\nруется скелет"), "обязательно формируется скелет")
        self.assertEqual(clean_page_text("Кыргызско-\nРоссийские"), "Кыргызско-\nРоссийские")
        self.assertEqual(clean_page_text("на северо-\nзапад из-\nза гор кто-\nто"), "на северо-запад из-за гор кто-то")

    def test_physics_notation_is_not_russified(self):
        for symbol in ("pатм", "Eк", "Tпл", "Cн", "Bб"):
            self.assertEqual(fix_lookalikes(f"значение {symbol} равно"), f"значение {symbol} равно")

    def test_numero_sign_repaired(self):
        self.assertEqual(fix_mojibake("Óïðàæíåíèå ¹ 3"), "Упражнение № 3")


class ExtractTests(unittest.TestCase):
    def test_scan_detection(self):
        self.assertTrue(page_is_scan("13", has_images=True))
        self.assertFalse(page_is_scan("13", has_images=False))
        self.assertFalse(page_is_scan("x" * 80, has_images=True))

    def test_render_scale_bounds_huge_pages(self):
        self.assertAlmostEqual(render_scale(400, 588), 170 / 72)       # страница учебника — полные 170 dpi
        self.assertAlmostEqual(842 * render_scale(595, 842), 1800)     # A4 при 170 dpi больше предела — ужимаем
        scale = render_scale(14400, 14400)
        self.assertLessEqual(14400 * scale, 1800 + 1e-6)


def pages(texts):
    return [PageText(index=i, text=t, is_scan=False) for i, t in enumerate(texts)]


class TocTests(unittest.TestCase):
    def test_toc_found_at_the_end_with_continuation(self):
        book = pages(["обложка"] + ["текст"] * 30 + ["СОДЕРЖАНИЕ\n§ 1. Личность 6\n§ 2. Факторы 14", "§ 3. Я-концепция 19\n§ 4. Гражданин 25"])
        self.assertEqual(find_toc_pages(book), [31, 32])

    def test_toc_three_pages_and_word_in_text_is_not_a_toc(self):
        book = pages(["Введение: содержание учебника разбито на разделы"] + ["текст"] * 30
                     + ["СОДЕРЖАНИЕ\n§ 1. А 6", "§ 2. Б 14\n§ 3. В 19", "§ 4. Г 25\n§ 5. Д 31"])
        self.assertEqual(find_toc_pages(book), [31, 32, 33])

    def test_no_votes_is_reported(self):
        entries = parse_toc_entries({"entries": [{"kind": "section", "title": "Нет такого заголовка", "page": 5}]})
        self.assertEqual(calibrate_offset(entries, pages(["x"] * 10)), (0, 0.0))

    def test_toc_page_is_not_counted_and_last_section_stops_before_it(self):
        texts = ["обложка"] * 20
        texts[3] = "§ 1. Давление твёрдых тел"
        texts[18] = "СОДЕРЖАНИЕ\n§ 1. Давление твёрдых тел 2"
        entries = parse_toc_entries({"entries": [{"kind": "section", "number": "§ 1", "title": "Давление твёрдых тел", "page": 2}]})
        self.assertEqual(calibrate_offset(entries, pages(texts), toc_pages=[18]), (1, 1.0))
        self.assertEqual(build_sections(entries, 20, 1, stop_index=18)[0].pdf_to, 17)

    def test_offset_calibration_and_section_ranges(self):
        # Печатная страница 6 — это индекс 7 в PDF (обложка и форзацы).
        texts = ["обложка"] * 40
        texts[7] = "§ 1. Личность и её структура\nЛичность — это..."
        texts[15] = "§ 2. Факторы формирования личности\n..."
        texts[20] = "§ 3. Представления человека о самом себе"
        entries = parse_toc_entries({"entries": [
            {"kind": "part", "title": "Раздел I. Личность", "page": 6},
            {"kind": "section", "number": "§ 1", "title": "Личность и её структура", "page": 6},
            {"kind": "section", "number": "§ 2", "title": "Факторы формирования личности", "page": 14},
            {"kind": "section", "number": "§ 3", "title": "Представления человека о самом себе (Я-концепция)", "page": 19},
            {"kind": "section", "title": "", "page": 30},  # пустой пункт отбрасывается
        ]})
        offset, share = calibrate_offset(entries, pages(texts))
        self.assertEqual((offset, share), (1, 1.0))
        sections = build_sections(entries, page_total=40, offset=offset)
        self.assertEqual([(s.number, s.pdf_from, s.pdf_to) for s in sections], [("§ 1", 7, 14), ("§ 2", 15, 19), ("§ 3", 20, 39)])
        self.assertEqual(sections[0].chapter, "Раздел I. Личность")


class ModelOutputTests(unittest.TestCase):
    def test_ocr_page_normalized(self):
        page = parse_ocr_page({"text": " ## УПРАЖНЕНИЕ 1\n1. $\\rho = \\frac{m}{V}$ ", "printed_page": 0, "uncertain": [""]})
        self.assertEqual(page["text"], "## УПРАЖНЕНИЕ 1\n1. $\\rho = \\frac{m}{V}$")
        self.assertIsNone(page["printed_page"])
        self.assertEqual(page["uncertain"], [])

    def test_items_filtered_and_bounded(self):
        items = parse_items({"items": [
            {"kind": "exercise", "label": "Упражнение 1, №2", "page": 13, "text": "Если ткань пропитана маслом…", "difficulty": 2},
            {"kind": "unknown", "page": 1, "text": "x"},
            {"kind": "definition", "page": 8, "text": "  "},
            {"kind": "formula", "page": "8", "text": "$\\rho = m/V$", "difficulty": 7},
        ]})
        self.assertEqual([item["kind"] for item in items], ["exercise", "formula"])
        self.assertIsNone(items[1]["page"])
        self.assertIsNone(items[1]["difficulty"])


if __name__ == "__main__":
    unittest.main()
