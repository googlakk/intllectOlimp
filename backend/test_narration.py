import unittest

from narration import fallback_avatar_script, is_screen_duplicate, spoken_text


class NarrationTests(unittest.TestCase):
    def test_verbalizes_math_and_removes_markdown(self):
        self.assertEqual(
            spoken_text("**Найдём:** $\\sqrt{49} = 7$, а $2^3 = 8$."),
            "Найдём: квадратный корень из 49 равно 7, а 2 в кубе равно 8.",
        )

    def test_fallback_explains_instead_of_reading_full_screen_text(self):
        script = fallback_avatar_script("ShortExplanation", {
            "text": "Очень длинный экранный текст, который не надо читать целиком.",
            "key_concepts": ["Корень — обратная операция к возведению в квадрат."],
        })
        self.assertIn("Разберём смысл простыми словами", script)
        self.assertNotIn("Очень длинный экранный текст", script)

    def test_detects_script_that_reads_the_slide(self):
        self.assertTrue(is_screen_duplicate(
            "Квадратный корень — это операция, обратная возведению в квадрат.",
            ["Квадратный корень — операция, обратная возведению числа в квадрат."],
        ))
        self.assertFalse(is_screen_duplicate(
            "Представьте площадь квадрата: корень помогает восстановить длину стороны.",
            ["Квадратный корень — операция, обратная возведению числа в квадрат."],
        ))


if __name__ == "__main__":
    unittest.main()
