"""Тесты шлюза к моделям.

Сеть не трогаем: у Anthropic подменяется клиент, у OpenRouter — транспорт
httpx. Проверяется то, что ломается в жизни: разная форма инструмента у
поставщиков, аргументы строкой вместо объекта, обрыв по лимиту и выбор
модели под задачу.
"""

import asyncio
import json
import unittest

from llm._http import HTTP_LIBRARY, MockTransport, Response
from llm._http import AsyncClient

from llm import (
    DEFAULTS, STOP_MAX_TOKENS, STOP_OTHER, STOP_TOOL, TASK_KTP_COLUMNS,
    TASK_LESSON, LLMError, ToolResult, call_tool, resolve_route,
)
from llm.anthropic_provider import AnthropicProvider
from llm.openrouter_provider import OpenRouterProvider, parse_arguments, to_openai_tool

TOOL = {
    "name": "submit_columns",
    "description": "Передать карту колонок.",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "integer"}},
        "required": ["name"],
    },
}


def run(coro):
    return asyncio.run(coro)


class RouteTests(unittest.TestCase):
    def test_default_is_direct_anthropic(self):
        # Без единой настройки ничего не меняется — важно для перехода.
        route = resolve_route(TASK_LESSON, env={})
        self.assertEqual(route.provider, "anthropic")
        self.assertEqual(route.model, DEFAULTS[TASK_LESSON]["anthropic"])

    def test_global_provider_switch(self):
        route = resolve_route(TASK_LESSON, env={"LLM_PROVIDER": "openrouter"})
        self.assertEqual(route.provider, "openrouter")
        self.assertEqual(route.model, DEFAULTS[TASK_LESSON]["openrouter"])

    def test_per_task_provider_beats_global(self):
        env = {"LLM_PROVIDER": "anthropic", "LLM_PROVIDER_KTP_COLUMNS": "openrouter"}
        self.assertEqual(resolve_route(TASK_KTP_COLUMNS, env=env).provider, "openrouter")
        self.assertEqual(resolve_route(TASK_LESSON, env=env).provider, "anthropic")

    def test_explicit_model_wins(self):
        env = {"LLM_PROVIDER": "openrouter", "LLM_MODEL_LESSON": "google/gemini-3-pro"}
        self.assertEqual(resolve_route(TASK_LESSON, env=env).model, "google/gemini-3-pro")

    def test_cheap_and_strong_tasks_can_differ(self):
        env = {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL_KTP_COLUMNS": "дешёвая",
            "LLM_MODEL_LESSON": "сильная",
        }
        self.assertEqual(resolve_route(TASK_KTP_COLUMNS, env=env).model, "дешёвая")
        self.assertEqual(resolve_route(TASK_LESSON, env=env).model, "сильная")

    def test_unknown_provider_is_rejected_with_a_readable_message(self):
        with self.assertRaises(LLMError) as ctx:
            resolve_route(TASK_LESSON, env={"LLM_PROVIDER": "какой-то"})
        self.assertIn("anthropic", str(ctx.exception))

    def test_unknown_task_without_model_is_rejected(self):
        with self.assertRaises(LLMError):
            resolve_route("новая-задача", env={"LLM_PROVIDER": "anthropic"})

    def test_env_name_derived_from_task(self):
        env = {"LLM_MODEL_KTP_COLUMNS": "X"}
        self.assertEqual(resolve_route(TASK_KTP_COLUMNS, env=env).model, "X")


class ToolShapeTests(unittest.TestCase):
    def test_anthropic_shape_converted_to_openai(self):
        converted = to_openai_tool(TOOL)
        self.assertEqual(converted["type"], "function")
        self.assertEqual(converted["function"]["name"], "submit_columns")
        self.assertEqual(converted["function"]["parameters"], TOOL["input_schema"])

    def test_tool_without_schema_gets_empty_object(self):
        converted = to_openai_tool({"name": "x"})
        self.assertEqual(converted["function"]["parameters"]["type"], "object")


class ParseArgumentsTests(unittest.TestCase):
    def test_json_string_is_parsed(self):
        self.assertEqual(parse_arguments('{"name": 1}'), {"name": 1})

    def test_object_passes_through(self):
        self.assertEqual(parse_arguments({"name": 1}), {"name": 1})

    def test_truncated_json_returns_none(self):
        self.assertIsNone(parse_arguments('{"name": 1, "other'))

    def test_non_object_json_returns_none(self):
        self.assertIsNone(parse_arguments("[1, 2]"))

    def test_empty_returns_none(self):
        self.assertIsNone(parse_arguments(""))
        self.assertIsNone(parse_arguments(None))


def _openrouter_client(handler):
    return AsyncClient(transport=MockTransport(handler))


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.env = {"OPENROUTER_API_KEY": "sk-or-test"}

    def _call(self, handler, env=None):
        import os
        saved = dict(os.environ)
        os.environ.update(env or self.env)
        try:
            client = _openrouter_client(handler)
            provider = OpenRouterProvider(client=client)
            return run(provider.call_tool(
                system="s", user="u", tool=TOOL, model="m", max_tokens=100,
            ))
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def test_tool_call_with_string_arguments(self):
        def handler(request):
            return Response(200, json={
                "model": "anthropic/claude-haiku-4.5",
                "choices": [{"finish_reason": "tool_calls", "message": {
                    "tool_calls": [{"function": {
                        "name": "submit_columns",
                        "arguments": json.dumps({"name": 1}),
                    }}],
                }}],
                "usage": {"total_tokens": 42},
            })
        result = self._call(handler)
        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"name": 1})
        self.assertEqual(result.stop_reason, STOP_TOOL)
        self.assertEqual(result.model, "anthropic/claude-haiku-4.5")

    def test_request_shape_sent_to_gateway(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            seen["auth"] = request.headers.get("authorization")
            return Response(200, json={"choices": [{"message": {
                "tool_calls": [{"function": {"arguments": "{}"}}]}}]})

        self._call(handler)
        self.assertEqual(seen["tool_choice"]["function"]["name"], "submit_columns")
        self.assertEqual(seen["tools"][0]["type"], "function")
        self.assertEqual(seen["messages"][0]["role"], "system")
        self.assertEqual(seen["auth"], "Bearer sk-or-test")

    def test_truncated_arguments_reported_as_max_tokens(self):
        def handler(request):
            return Response(200, json={"choices": [{
                "finish_reason": "length",
                "message": {"tool_calls": [{"function": {"arguments": '{"na'}}]},
            }]})
        result = self._call(handler)
        self.assertEqual(result.stop_reason, STOP_MAX_TOKENS)
        self.assertTrue(result.truncated)
        self.assertFalse(result.ok)

    def test_length_with_parseable_arguments_is_still_truncation(self):
        def handler(request):
            return Response(200, json={"choices": [{
                "finish_reason": "length",
                "message": {"tool_calls": [{"function": {"arguments": '{"blocks": []}'}}]},
            }]})
        result = self._call(handler)
        self.assertTrue(result.truncated)
        self.assertFalse(result.ok)

    def test_broken_arguments_without_length_are_not_called_truncation(self):
        def handler(request):
            return Response(200, json={"choices": [{
                "finish_reason": "tool_calls",
                "message": {"tool_calls": [{"function": {"arguments": "не json"}}]},
            }]})
        result = self._call(handler)
        self.assertEqual(result.stop_reason, STOP_OTHER)

    def test_text_answer_without_tool_call(self):
        def handler(request):
            return Response(200, json={"choices": [{
                "finish_reason": "stop", "message": {"content": "просто текст"},
            }]})
        result = self._call(handler)
        self.assertFalse(result.ok)
        self.assertEqual(result.text, "просто текст")

    def test_http_error_carries_provider_and_model(self):
        def handler(request):
            return Response(429, text="rate limited")
        with self.assertRaises(LLMError) as ctx:
            self._call(handler)
        message = str(ctx.exception)
        self.assertIn("429", message)
        self.assertIn("openrouter", message)

    def test_error_body_without_choices(self):
        def handler(request):
            return Response(200, json={"error": {"message": "нет денег"}})
        with self.assertRaises(LLMError) as ctx:
            self._call(handler)
        self.assertIn("нет денег", str(ctx.exception))

    def test_non_ascii_key_gets_a_readable_message(self):
        # Кириллица в ключе иначе вылезает UnicodeEncodeError из недр httpx.
        def handler(request):
            return Response(200, json={"choices": []})
        with self.assertRaises(LLMError) as ctx:
            self._call(handler, env={"OPENROUTER_API_KEY": "ключ-с-кириллицей"})
        self.assertIn("не-ASCII", str(ctx.exception))

    def test_missing_api_key_is_named_plainly(self):
        def handler(request):
            return Response(200, json={"choices": []})
        with self.assertRaises(LLMError) as ctx:
            self._call(handler, env={"OPENROUTER_API_KEY": ""})
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))


class _AnthropicBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for key, value in kwargs.items():
            setattr(self, key, value)


class _AnthropicMessage:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = None


class _FakeAnthropic:
    def __init__(self, message):
        self._message = message
        self.seen = {}

        outer = self

        class _Messages:
            async def create(self, **kwargs):
                outer.seen = kwargs
                return outer._message

        self.messages = _Messages()


class AnthropicProviderTests(unittest.TestCase):
    def test_tool_use_returns_data(self):
        client = _FakeAnthropic(_AnthropicMessage(
            [_AnthropicBlock("tool_use", input={"name": 1})]
        ))
        result = run(AnthropicProvider(client=client).call_tool(
            system="s", user="u", tool=TOOL, model="m", max_tokens=100,
        ))
        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"name": 1})
        self.assertEqual(client.seen["tool_choice"], {"type": "tool", "name": "submit_columns"})

    def test_max_tokens_is_normalised(self):
        client = _FakeAnthropic(_AnthropicMessage(
            [_AnthropicBlock("text", text="обрыв")], stop_reason="max_tokens",
        ))
        result = run(AnthropicProvider(client=client).call_tool(
            system="s", user="u", tool=TOOL, model="m", max_tokens=100,
        ))
        self.assertEqual(result.stop_reason, STOP_MAX_TOKENS)
        self.assertTrue(result.truncated)

    def test_tool_use_cut_by_max_tokens_is_truncation_not_data(self):
        # Повод: урок по географии — модель упёрлась в лимит посреди вызова
        # инструмента, blocks пришли неполными, и ошибка выглядела как
        # «дважды вернула урок в неожиданном виде» вместо перехода на части.
        client = _FakeAnthropic(_AnthropicMessage(
            [_AnthropicBlock("tool_use", input={})], stop_reason="max_tokens",
        ))
        result = run(AnthropicProvider(client=client).call_tool(
            system="s", user="u", tool=TOOL, model="m", max_tokens=100,
        ))
        self.assertTrue(result.truncated)
        self.assertFalse(result.ok)

    def test_complete_tool_use_still_returns_data(self):
        client = _FakeAnthropic(_AnthropicMessage(
            [_AnthropicBlock("tool_use", input={"name": 1})], stop_reason="tool_use",
        ))
        result = run(AnthropicProvider(client=client).call_tool(
            system="s", user="u", tool=TOOL, model="m", max_tokens=100,
        ))
        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"name": 1})

    def test_both_providers_return_the_same_shape(self):
        # Ради этого весь слой и существует: вызывающий код одинаков.
        anthropic_result = run(AnthropicProvider(
            client=_FakeAnthropic(_AnthropicMessage([_AnthropicBlock("tool_use", input={"name": 1})]))
        ).call_tool(system="s", user="u", tool=TOOL, model="m", max_tokens=10))

        import os
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        try:
            def handler(request):
                return Response(200, json={"choices": [{"message": {
                    "tool_calls": [{"function": {"arguments": '{"name": 1}'}}]}}]})
            gateway_result = run(OpenRouterProvider(
                client=_openrouter_client(handler)
            ).call_tool(system="s", user="u", tool=TOOL, model="m", max_tokens=10))
        finally:
            os.environ.pop("OPENROUTER_API_KEY", None)

        self.assertEqual(anthropic_result.data, gateway_result.data)
        self.assertEqual(anthropic_result.stop_reason, gateway_result.stop_reason)
        self.assertIsInstance(anthropic_result, ToolResult)
        self.assertIsInstance(gateway_result, ToolResult)


class CallToolTests(unittest.TestCase):
    def test_injected_provider_is_used_and_model_comes_from_route(self):
        seen = {}

        class _Spy:
            name = "spy"

            async def call_tool(self, **kwargs):
                seen.update(kwargs)
                return ToolResult(data={"ok": True}, stop_reason=STOP_TOOL)

        result = run(call_tool(
            TASK_LESSON, system="s", user="u", tool=TOOL, max_tokens=99,
            provider=_Spy(), env={"LLM_MODEL_LESSON": "выбранная"},
        ))
        self.assertTrue(result.ok)
        self.assertEqual(seen["model"], "выбранная")
        self.assertEqual(seen["max_tokens"], 99)


if __name__ == "__main__":
    unittest.main()


class GatewayIntegrationTests(unittest.TestCase):
    """Разбор КТП идёт одинаково, кто бы ни ответил — в этом весь смысл слоя."""

    PAYLOAD = {
        "subject_name": "Литература", "grade": 8, "hours_per_week": 1.8,
        "hours_per_year": 61, "instruction_language": "ru", "notes": [],
        "tables": [{
            "table_index": 0, "is_plan": True, "header_rows": 3, "name": 1,
            "hours": 2, "number": 0, "number_in_name": False, "objectives": 5,
            "skills": [6], "resources": 9, "note": 7,
        }],
    }

    def _detect_through(self, provider_result):
        import os
        from pathlib import Path
        from ktp.extract import extract
        from ktp.mapper import build_draft

        sample = Path(__file__).parent / "testdata" / "literature.docx"
        if not sample.is_file():
            self.skipTest("нет testdata/literature.docx")

        class _Fixed:
            name = "fixed"

            async def call_tool(self, **kwargs):
                return provider_result

        import ktp.columns as columns
        extraction = extract(sample.read_bytes(), sample.name)

        async def detect():
            result = await call_tool(
                TASK_KTP_COLUMNS, system=columns.SYSTEM_PROMPT, user="u",
                tool=columns.COLUMNS_TOOL, max_tokens=columns.MAX_TOKENS,
                provider=_Fixed(), env={"LLM_MODEL_KTP_COLUMNS": "любая"},
            )
            return result

        result = run(detect())
        return build_draft(extraction, result.data), result

    def test_same_draft_from_anthropic_style_answer(self):
        draft, _ = self._detect_through(
            ToolResult(data=self.PAYLOAD, stop_reason=STOP_TOOL, provider="anthropic")
        )
        topics = [t for s in draft["sections"] for t in s["topics"]]
        self.assertEqual(len(topics), 61)
        self.assertTrue(topics[0]["learning_objectives"].startswith("Научиться"))

    def test_same_draft_from_openrouter_style_answer(self):
        # У шлюза аргументы приходят строкой — после разбора результат тот же.
        parsed = parse_arguments(json.dumps(self.PAYLOAD))
        draft, _ = self._detect_through(
            ToolResult(data=parsed, stop_reason=STOP_TOOL, provider="openrouter")
        )
        topics = [t for s in draft["sections"] for t in s["topics"]]
        self.assertEqual(len(topics), 61)
        self.assertEqual(draft["hours_per_year"], 61)
