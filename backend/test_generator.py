"""Тесты разбора ответа модели при генерации урока.

Повод: урок литературы не генерировался, сообщение — «Модель дважды вернула
некорректный JSON урока». JSON был корректным ровно до места обрыва: ответ не
помещался в 8192 токена. Сообщение называло следствие, а не причину, и повтор
тем же запросом был заведомо бесполезен.

Теперь урок приходит вызовом инструмента (структура гарантирована схемой),
потолок поднят, а обрыв по лимиту распознаётся отдельно и называется вслух.
"""

import json
import unittest

from ai.generator import (
    LESSON_TOOL, MAX_TOKENS, GeneratedBlocks, _blocks_from_tool, _parse_blocks, _validate_blocks, clean_intro,
)
from objectives import ALLOWED_COMPONENTS

GOOD_BLOCK = {"component": "ShortExplanation", "content": {"objective_ids": ["obj-1"]}}


class _Block:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Response:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class ToolSchemaTests(unittest.TestCase):
    def test_component_enum_matches_allowed_components(self):
        enum = LESSON_TOOL["input_schema"]["properties"]["blocks"]["items"] \
            ["properties"]["component"]["enum"]
        self.assertEqual(set(enum), ALLOWED_COMPONENTS)

    def test_max_tokens_below_sdk_streaming_threshold(self):
        # Выше 21333 SDK требует стриминг — см. ktp/mapper.py.
        self.assertLessEqual(MAX_TOKENS, 21_333)

    def test_max_tokens_raised_above_the_old_limit(self):
        self.assertGreater(MAX_TOKENS, 8192, "именно 8192 не хватало уроку литературы")


class ToolAnswerTests(unittest.TestCase):
    def test_blocks_taken_from_tool_call(self):
        response = _Response([_Block("tool_use", input={"blocks": [GOOD_BLOCK]})])
        self.assertEqual(_blocks_from_tool(response), [GOOD_BLOCK])

    def test_no_tool_call_returns_none_not_error(self):
        response = _Response([_Block("text", text="[]")])
        self.assertIsNone(_blocks_from_tool(response))

    def test_tool_call_without_blocks_list_returns_none(self):
        response = _Response([_Block("tool_use", input={"blocks": "не список"})])
        self.assertIsNone(_blocks_from_tool(response))

    def test_malformed_block_inside_tool_call_is_rejected(self):
        response = _Response([_Block("tool_use", input={"blocks": [{"component": "X"}]})])
        with self.assertRaises(ValueError):
            _blocks_from_tool(response)


class ValidateBlocksTests(unittest.TestCase):
    def test_empty_lesson_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_blocks([])

    def test_non_list_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_blocks({"component": "ShortExplanation"})

    def test_block_without_content_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_blocks([{"component": "ShortExplanation"}])

    def test_content_must_be_an_object(self):
        with self.assertRaises(ValueError):
            _validate_blocks([{"component": "ShortExplanation", "content": "текст"}])

    def test_good_lesson_passes(self):
        self.assertEqual(_validate_blocks([GOOD_BLOCK]), [GOOD_BLOCK])


class TextFallbackTests(unittest.TestCase):
    """Разбор текста остаётся запасным путём — он не должен сломаться."""

    def test_plain_json_array(self):
        self.assertEqual(_parse_blocks(json.dumps([GOOD_BLOCK])), [GOOD_BLOCK])

    def test_json_in_markdown_fence(self):
        raw = "```json\n" + json.dumps([GOOD_BLOCK]) + "\n```"
        self.assertEqual(_parse_blocks(raw), [GOOD_BLOCK])

    def test_truncated_json_raises(self):
        # Ровно то, что происходило при обрыве по лимиту.
        raw = json.dumps([GOOD_BLOCK])[:-12]
        with self.assertRaises(json.JSONDecodeError):
            _parse_blocks(raw)


if __name__ == "__main__":
    unittest.main()


class IntroTests(unittest.TestCase):
    def test_tool_accepts_optional_intro(self):
        schema = LESSON_TOOL["input_schema"]
        self.assertIn("intro", schema["properties"])
        self.assertEqual(schema["required"], ["blocks"])

    def test_clean_intro_keeps_short_strings(self):
        intro = clean_intro({"title": " Большая идея. ", "accent": "Квадратный сад.", "hook": "Как превратить площадь в сторону?", "cta": 5})
        self.assertEqual(intro, {"title": "Большая идея.", "accent": "Квадратный сад.", "hook": "Как превратить площадь в сторону?"})

    def test_clean_intro_drops_broken_or_too_long(self):
        self.assertIsNone(clean_intro(None))
        self.assertIsNone(clean_intro({"title": "Без крючка"}))
        self.assertIsNone(clean_intro({"title": "Т", "hook": "х" * 281}))

    def test_generated_blocks_still_a_list(self):
        blocks = GeneratedBlocks([GOOD_BLOCK])
        blocks.intro = {"title": "Т", "hook": "Х"}
        self.assertEqual(blocks, [GOOD_BLOCK])
        self.assertEqual(blocks.intro["title"], "Т")
