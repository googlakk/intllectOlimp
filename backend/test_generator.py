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


class ShowPathTests(unittest.TestCase):
    """Объяснение показывает путь к результату: $3^2 = 3 \\cdot 3 = 9$, а не сразу «9»."""

    def test_system_prompt_has_rule_and_reference_example(self):
        from ai.generator import SYSTEM_PROMPT
        self.assertIn("покажи путь, а не только результат", SYSTEM_PROMPT)
        self.assertIn("$3^2 = 3 \\cdot 3$", SYSTEM_PROMPT)
        self.assertIn("3–6 шагов, каждый шаг — одно действие", SYSTEM_PROMPT)

    def test_every_subject_family_says_how_to_show_the_path(self):
        from ai.generator import SUBJECT_FAMILY_PROFILES
        for family, profile in SUBJECT_FAMILY_PROFILES.items():
            self.assertTrue(str(profile.get("show_path", "")).strip(), family)

    def test_lesson_request_carries_the_subject_path(self):
        import asyncio
        from unittest.mock import patch
        from ai.generator import SUBJECT_FAMILY_PROFILES, generate_lesson
        from llm import ToolResult
        from llm.base import STOP_TOOL

        prompts = []

        async def fake_call_tool(task, **kwargs):
            prompts.append(kwargs["user"])
            return ToolResult(data={"blocks": [GOOD_BLOCK]}, stop_reason=STOP_TOOL)

        with patch("llm.call_tool", fake_call_tool):
            asyncio.run(generate_lesson("Степень с натуральным показателем", "Алгебра", "Вычислять степени", None, None, grade=7))
        self.assertIn("Как показывать ход мысли: " + SUBJECT_FAMILY_PROFILES["mathematical"]["show_path"], prompts[0])


class LessonPartsTests(unittest.TestCase):
    """Большой урок генерируется по частям, обычный — одним вызовом."""

    THREE = "Вычислять степени. Сравнивать степени. Применять свойства степеней."
    TWO = "Вычислять степени. Сравнивать степени."

    def run_generation(self, objectives, replies, hours=1):
        import asyncio
        from unittest.mock import patch
        from ai.generator import generate_lesson

        prompts = []

        async def fake_call_tool(task, **kwargs):
            prompts.append(kwargs["user"])
            reply = replies[len(prompts) - 1]
            if isinstance(reply, Exception):
                raise reply
            return reply

        with patch("llm.call_tool", fake_call_tool):
            lesson = asyncio.run(generate_lesson("Степени", "Алгебра", objectives, None, None, grade=7, hours=hours))
        return lesson, prompts

    @staticmethod
    def reply(*components, intro=None, term=None):
        from llm import ToolResult
        from llm.base import STOP_TOOL
        blocks = [{"component": name, "content": {"objective_ids": ["x"]}} for name in components]
        if term:
            blocks.append({"component": "KeyConcept", "content": {"term": term}})
        data = {"blocks": blocks, **({"intro": intro} if intro else {})}
        return ToolResult(data=data, stop_reason=STOP_TOOL, model="m")

    def test_regular_lesson_is_one_call(self):
        _, prompts = self.run_generation(self.TWO, [self.reply("ShortExplanation")], hours=2)
        self.assertEqual(len(prompts), 1)
        self.assertNotIn("Сейчас ты генерируешь только часть", prompts[0])

    def test_large_lesson_goes_part_by_part_and_keeps_order(self):
        # 3 цели → 5 частей: [разминка, объяснение], [пример, практика], цель 2, цель 3, финал.
        intro = {"title": "Большая идея", "hook": "Загадка"}
        replies = [
            self.reply("RetrievalCheck", intro=intro, term="Степень"),
            self.reply("WorkedExample"),
            self.reply("ShortExplanation"),
            self.reply("GuidedPractice"),
            self.reply("MasteryCheck", "Reflection"),
        ]
        lesson, prompts = self.run_generation(self.THREE, replies)
        self.assertEqual(len(prompts), 5)
        for index, prompt in enumerate(prompts):
            self.assertIn(f"часть {index + 1} из 5", prompt)
        self.assertIn("Введённые термины: Степень", prompts[1])
        self.assertIn("Не добавляй титул intro", prompts[1])
        self.assertIn("Не добавляй MasteryCheck и Reflection", prompts[0])
        self.assertNotIn("Не добавляй MasteryCheck и Reflection", prompts[4])
        self.assertEqual(
            [block["component"] for block in lesson],
            ["RetrievalCheck", "KeyConcept", "WorkedExample", "ShortExplanation", "GuidedPractice", "MasteryCheck", "Reflection"],
        )
        self.assertEqual(lesson.intro, intro)

    def test_truncated_single_call_falls_back_to_parts(self):
        from llm import ToolResult
        from llm.base import STOP_MAX_TOKENS
        truncated = ToolResult(stop_reason=STOP_MAX_TOKENS, model="m")
        # 2 цели, 2 часа — обычный урок: сначала одним вызовом, после обрыва — 4 части.
        replies = [truncated, *(self.reply(name) for name in ("ShortExplanation", "WorkedExample", "GuidedPractice", "MasteryCheck"))]
        lesson, prompts = self.run_generation(self.TWO, replies, hours=2)
        self.assertEqual(len(prompts), 5)
        self.assertIn("часть 1 из 4", prompts[1])
        self.assertEqual([block["component"] for block in lesson], ["ShortExplanation", "WorkedExample", "GuidedPractice", "MasteryCheck"])

    def test_failed_part_names_the_part_and_saves_nothing(self):
        from llm import LLMError
        replies = [self.reply("ShortExplanation"), self.reply("WorkedExample"), LLMError("сеть", provider="p", model="m")]
        with self.assertRaises(RuntimeError) as failed:
            self.run_generation(self.THREE, replies)
        self.assertIn("часть 3 из 5", str(failed.exception))
        self.assertIn("Сравнивать степени", str(failed.exception))

    def test_assessment_is_never_split(self):
        from ai.generator import should_generate_in_parts
        self.assertFalse(should_generate_in_parts({"volume": "extended", "lesson_shape": "assessment_only"}, 5))
        self.assertTrue(should_generate_in_parts({"volume": "standard", "lesson_shape": "concept_intro"}, 3))
        self.assertFalse(should_generate_in_parts({"volume": "standard", "lesson_shape": "concept_intro"}, 2))

    def test_stray_mastery_check_in_a_middle_part_is_dropped(self):
        replies = [
            self.reply("ShortExplanation", "MasteryCheck"),
            self.reply("WorkedExample"),
            self.reply("ShortExplanation"),
            self.reply("GuidedPractice"),
            self.reply("MasteryCheck", "Reflection"),
        ]
        lesson, prompts = self.run_generation(self.THREE, replies)
        self.assertEqual([block["component"] for block in lesson].count("MasteryCheck"), 1)
        self.assertEqual(lesson[-2]["component"], "MasteryCheck")
        from objectives import decompose_objectives
        for objective in decompose_objectives(self.THREE):
            self.assertIn(objective["id"], prompts[-1].split("MasteryCheck содержит")[1])

    def test_timeout_of_single_call_falls_back_to_parts(self):
        from llm import LLMError

        class ReadTimeout(Exception):
            pass

        timeout = LLMError("Запрос не прошёл", provider="openrouter", model="m")
        timeout.__cause__ = ReadTimeout("timed out")
        replies = [timeout, *(self.reply(name) for name in ("ShortExplanation", "WorkedExample", "GuidedPractice", "MasteryCheck"))]
        lesson, prompts = self.run_generation(self.TWO, replies, hours=2)
        self.assertEqual(len(prompts), 5)

    def test_other_errors_of_single_call_are_not_retried_as_parts(self):
        from llm import LLMError
        with self.assertRaises(LLMError):
            self.run_generation(self.TWO, [LLMError("Шлюз ответил 401", provider="p", model="m")], hours=2)

    def test_truncated_one_part_plan_reports_truncation(self):
        import asyncio
        from unittest.mock import patch
        from ai.generator import LessonTruncated, generate_lesson
        from llm import ToolResult
        from llm.base import STOP_MAX_TOKENS

        async def fake_call_tool(task, **kwargs):
            return ToolResult(stop_reason=STOP_MAX_TOKENS, model="m")

        plan = [{"role": "assess", "objective_ids": [], "allowed_components": ["MasteryCheck"]}]
        with patch("llm.call_tool", fake_call_tool), self.assertRaises(LessonTruncated):
            asyncio.run(generate_lesson("Т", "Алгебра", "Цель.", None, None, topic_contract={"volume": "micro"}, component_plan=plan))

    def test_truncated_part_is_named(self):
        from llm import ToolResult
        from llm.base import STOP_MAX_TOKENS
        replies = [self.reply("ShortExplanation"), ToolResult(stop_reason=STOP_MAX_TOKENS, model="m")]
        with self.assertRaises(RuntimeError) as failed:
            self.run_generation(self.THREE, replies)
        self.assertIn("часть 2 из 5", str(failed.exception))
        self.assertIn("не поместился", str(failed.exception))

    def test_text_parsed_first_part_has_no_intro_and_does_not_crash(self):
        from llm import ToolResult
        text_reply = ToolResult(text=json.dumps([{"component": "ShortExplanation", "content": {}}]), model="m")
        replies = [text_reply, *(self.reply(name) for name in ("WorkedExample", "ShortExplanation", "GuidedPractice", "MasteryCheck"))]
        lesson, _ = self.run_generation(self.THREE, replies)
        self.assertIsNone(lesson.intro)
        self.assertEqual(len(lesson), 5)

    def test_geography_single_objective_three_hours_goes_in_parts(self):
        # Повод: тема по географии, одна цель, 3 часа — не влезла в один ответ.
        replies = [self.reply("RetrievalCheck", "Presentation"), self.reply("WorkedExample", "GuidedPractice"),
                   self.reply("IndependentProblem", "MasteryCheck", "Reflection")]
        lesson, prompts = self.run_generation(
            "Характеризовать природу Юго-Западного Тенир-Тоо и сравнивать его провинции.", replies, hours=3,
        )
        self.assertEqual(len(prompts), 3)
        self.assertEqual(len(lesson), 7)

    def test_regular_one_objective_lesson_is_one_call_first(self):
        _, prompts = self.run_generation("Вычислять степени.", [self.reply("ShortExplanation")], hours=1)
        self.assertEqual(len(prompts), 1)

    def test_last_part_names_objectives_even_without_catalog(self):
        from llm import ToolResult
        from llm.base import STOP_MAX_TOKENS
        replies = [ToolResult(stop_reason=STOP_MAX_TOKENS, model="m"), *(self.reply("ShortExplanation") for _ in range(3))]
        _, prompts = self.run_generation(None, replies, hours=1)
        self.assertIn("по каждой цели урока: obj-general", prompts[-1])

    def test_failed_final_part_of_one_objective_lesson_is_labelled(self):
        from llm import LLMError
        replies = [self.reply("ShortExplanation"), self.reply("WorkedExample"), LLMError("сеть", provider="p", model="m")]
        with self.assertRaises(RuntimeError) as failed:
            self.run_generation("Характеризовать природу Юго-Западного Тенир-Тоо.", replies, hours=3)
        self.assertIn("итоговая проверка и рефлексия", str(failed.exception))

    def test_summary_survives_broken_slides_and_keeps_examples(self):
        from ai.generator import summarize_blocks
        blocks = [
            {"component": "Presentation", "content": {"slides": 5}},
            {"component": "Presentation", "content": {"slides": [{"heading": "Слайд " + "х" * 80} for _ in range(40)]}},
            {"component": "WorkedExample", "content": {"problem": "Вычисли $3^2$"}},
        ]
        summary = summarize_blocks(blocks)
        self.assertIn("Разобранные примеры и задачи: Вычисли $3^2$", summary)
        self.assertLessEqual(len(summary), 1500 + 3)


class RetryLoopTests(unittest.TestCase):
    """Цикл запроса перенесён в _BlocksRequest — поведение прежнее."""

    def request(self, replies):
        from ai.generator import _BlocksRequest
        prompts = []

        async def fake_call_tool(task, **kwargs):
            prompts.append(kwargs["user"])
            return replies[len(prompts) - 1]

        return _BlocksRequest(call_tool=fake_call_tool, task="lesson", route=None), prompts

    def test_parse_failure_then_success(self):
        import asyncio
        from llm import ToolResult
        from llm.base import STOP_TOOL
        request, prompts = self.request([ToolResult(text="не JSON", model="m"), ToolResult(data={"blocks": [GOOD_BLOCK]}, stop_reason=STOP_TOOL)])
        self.assertEqual(asyncio.run(request.blocks("урок")), [GOOD_BLOCK])
        self.assertIn("Предыдущий ответ не удалось разобрать", prompts[1])

    def test_two_parse_failures_raise(self):
        import asyncio
        from llm import ToolResult
        request, _ = self.request([ToolResult(text="нет", model="m"), ToolResult(text="опять нет", model="m")])
        with self.assertRaises(RuntimeError) as failed:
            asyncio.run(request.blocks("урок"))
        self.assertIn("дважды", str(failed.exception))

    def test_dump_shows_what_the_model_put_into_the_tool(self):
        import asyncio
        import tempfile
        from pathlib import Path
        from llm import ToolResult
        from llm.base import STOP_TOOL
        odd = ToolResult(data={"blocks": "не список"}, stop_reason=STOP_TOOL, model="m")
        request, _ = self.request([odd, odd])
        with self.assertRaises(RuntimeError):
            asyncio.run(request.blocks("урок"))
        dump = (Path(tempfile.gettempdir()) / "lesson-raw.txt").read_text(encoding="utf-8")
        self.assertIn("tool input:", dump)
        self.assertIn("не список", dump)

    def test_truncation_on_retry_raises_at_once(self):
        import asyncio
        from ai.generator import LessonTruncated
        from llm import ToolResult
        from llm.base import STOP_MAX_TOKENS
        request, prompts = self.request([ToolResult(text="нет", model="m"), ToolResult(stop_reason=STOP_MAX_TOKENS, model="m")])
        with self.assertRaises(LessonTruncated):
            asyncio.run(request.blocks("урок"))
        self.assertEqual(len(prompts), 2)


if __name__ == "__main__":
    unittest.main()
