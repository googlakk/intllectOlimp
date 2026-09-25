import json
import unittest

from llm import TASK_LESSON, Route, ToolResult, call_tool
from llm.catalog import (
    ModelChoiceError,
    image_supported_params,
    model_catalog,
    resolve_image_choice,
    resolve_lesson_choice,
)
from llm.media import OpenRouterMediaProvider
from test_media import Env, media_client, run

BOTH_KEYS = {"ANTHROPIC_API_KEY": "sk-ant-test", "OPENROUTER_API_KEY": "sk-or-test"}


class CatalogTests(unittest.TestCase):
    def test_catalog_marks_default_and_availability(self):
        catalog = model_catalog({"ANTHROPIC_API_KEY": "sk-ant-test"})
        lesson = catalog["lesson"]
        self.assertEqual(lesson["default"], "anthropic:claude-sonnet-4-6")
        by_id = {item["id"]: item for item in lesson["options"]}
        self.assertTrue(by_id["anthropic:claude-sonnet-4-6"]["default"])
        self.assertTrue(by_id["anthropic:claude-opus-5"]["available"])
        self.assertFalse(by_id["openrouter:openai/gpt-6-sol"]["available"])
        self.assertEqual(catalog["image"]["default"], "openrouter:google/gemini-2.5-flash-image")

    def test_env_default_outside_catalog_is_listed_first(self):
        env = {**BOTH_KEYS, "LLM_MODEL_LESSON": "claude-custom", "OPENROUTER_IMAGE_MODEL": "vendor/custom-image"}
        catalog = model_catalog(env)
        self.assertEqual(catalog["lesson"]["options"][0]["id"], "anthropic:claude-custom")
        self.assertTrue(catalog["lesson"]["options"][0]["default"])
        self.assertEqual(catalog["image"]["options"][0]["id"], "openrouter:vendor/custom-image")

    def test_lesson_choice_resolves_to_route(self):
        self.assertIsNone(resolve_lesson_choice(None, BOTH_KEYS))
        route = resolve_lesson_choice("openrouter:openai/gpt-6-sol", BOTH_KEYS)
        self.assertEqual(route, Route(provider="openrouter", model="openai/gpt-6-sol", task=TASK_LESSON))

    def test_lesson_choice_rejects_unknown_model(self):
        with self.assertRaises(ModelChoiceError):
            resolve_lesson_choice("openrouter:evil/any-model", BOTH_KEYS)

    def test_lesson_choice_rejects_provider_without_key(self):
        with self.assertRaises(ModelChoiceError) as rejected:
            resolve_lesson_choice("openrouter:openai/gpt-6-sol", {"ANTHROPIC_API_KEY": "sk-ant-test"})
        self.assertIn("ключ", str(rejected.exception))

    def test_image_choice_accepts_id_or_bare_model(self):
        self.assertEqual(resolve_image_choice("openrouter:openai/gpt-image-2", {}), "openai/gpt-image-2")
        self.assertEqual(resolve_image_choice("openai/gpt-image-2", {}), "openai/gpt-image-2")
        self.assertIsNone(resolve_image_choice("", {}))
        with self.assertRaises(ModelChoiceError):
            resolve_image_choice("vendor/unlisted", {})


class ImageParamFilterTests(unittest.TestCase):
    def _sent_body(self, model):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return {"data": [{"b64_json": "aGVsbG8="}]}

        from llm._http import Response

        with Env(OPENROUTER_API_KEY="sk-or-test"):
            provider = OpenRouterMediaProvider(client=media_client(lambda r: Response(200, json=handler(r))))
            run(provider.generate_image(prompt="cell", model=model))
        return seen["body"]

    def test_openai_model_gets_only_supported_params(self):
        body = self._sent_body("openai/gpt-image-2")
        self.assertEqual(body["quality"], "medium")
        self.assertEqual(body["aspect_ratio"], "16:9")
        self.assertNotIn("resolution", body)
        self.assertNotIn("output_format", body)

    def test_gemini_model_drops_quality(self):
        body = self._sent_body("google/gemini-3-pro-image")
        self.assertEqual(body["resolution"], "1K")
        self.assertNotIn("quality", body)

    def test_unknown_model_keeps_previous_payload(self):
        self.assertIsNone(image_supported_params("image/requested"))
        body = self._sent_body("image/requested")
        for key in ("resolution", "quality", "output_format", "aspect_ratio"):
            self.assertIn(key, body)


class ExplicitRouteTests(unittest.TestCase):
    def test_call_tool_uses_explicit_route(self):
        seen = {}

        class FakeProvider:
            async def call_tool(self, **kwargs):
                seen.update(kwargs)
                return ToolResult(data={"ok": True})

        route = Route(provider="anthropic", model="claude-opus-5", task=TASK_LESSON)
        run(call_tool(
            TASK_LESSON, system="s", user="u", tool={"name": "t"}, max_tokens=10,
            provider=FakeProvider(), env={}, route=route,
        ))
        self.assertEqual(seen["model"], "claude-opus-5")


if __name__ == "__main__":
    unittest.main()
