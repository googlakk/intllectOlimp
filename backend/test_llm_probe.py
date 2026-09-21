"""Тесты проверки шлюза.

Сам инструмент проверки тоже должен быть проверен: если он соврёт «всё на
месте», деньги уйдут впустую. Сеть подменяется, живых вызовов нет.
"""

import asyncio
import os
import unittest
from contextlib import contextmanager

from llm import probe
from llm._http import AsyncClient, MockTransport, Response


def run(coro):
    return asyncio.run(coro)


@contextmanager
def env(**values):
    saved = dict(os.environ)
    os.environ.update({k: v for k, v in values.items() if v is not None})
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


@contextmanager
def fake_gateway(handler):
    """Подменяет HTTP-клиент внутри probe на поддельный."""
    original = probe.AsyncClient

    class _Client(AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("timeout", None)
            super().__init__(transport=MockTransport(handler), **kwargs)

    probe.AsyncClient = _Client
    try:
        yield
    finally:
        probe.AsyncClient = original


KEY_OK = {"data": {
    "label": "проба", "limit": 10.0, "limit_remaining": 9.5,
    "usage": 0.5, "usage_daily": 0.1, "usage_monthly": 0.5,
    "is_free_tier": False,
}}

MODEL_OK = {"data": {
    "name": "Claude Haiku 4.5",
    "pricing": {"prompt": "0.0000008", "completion": "0.000004"},
    "supported_parameters": ["tools", "max_tokens"],
}}


class KeyCheckTests(unittest.TestCase):
    def test_missing_key_is_reported_not_crashed(self):
        with env(OPENROUTER_API_KEY=None):
            lines = run(probe.check_openrouter_key())
        self.assertTrue(any("не задан" in line for line in lines))

    def test_non_ascii_key_caught_before_any_request(self):
        with env(OPENROUTER_API_KEY="ключ"):
            lines = run(probe.check_openrouter_key())
        self.assertTrue(any("не-ASCII" in line for line in lines))

    def test_healthy_key_shows_balance(self):
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(200, json=KEY_OK)
        ):
            lines = run(probe.check_openrouter_key())
        text = "\n".join(lines)
        self.assertIn("✓ ключ принят", text)
        self.assertIn("осталось $9.5", text)

    def test_rejected_key_says_so_plainly(self):
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(401, json={"error": "no"})
        ):
            lines = run(probe.check_openrouter_key())
        self.assertTrue(any("не принят (401)" in line for line in lines))

    def test_exhausted_balance_is_flagged(self):
        body = {"data": {**KEY_OK["data"], "limit_remaining": 0}}
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(200, json=body)
        ):
            lines = run(probe.check_openrouter_key())
        self.assertTrue(any("402" in line for line in lines))

    def test_free_tier_is_flagged(self):
        body = {"data": {**KEY_OK["data"], "is_free_tier": True}}
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(200, json=body)
        ):
            lines = run(probe.check_openrouter_key())
        self.assertTrue(any("бесплатный тариф" in line for line in lines))


class ModelCheckTests(unittest.TestCase):
    def test_model_found_with_price(self):
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(200, json=MODEL_OK)
        ):
            lines = run(probe.check_model("anthropic/claude-haiku-4.5"))
        text = "\n".join(lines)
        self.assertIn("✓ модель доступна", text)
        self.assertIn("за 1M токенов", text)

    def test_typo_in_model_name_is_caught(self):
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(404, json={"error": "not found"})
        ):
            lines = run(probe.check_model("anthropic/claude-haikuu"))
        self.assertTrue(any("не найдена" in line for line in lines))

    def test_model_without_tool_support_is_flagged(self):
        body = {"data": {**MODEL_OK["data"], "supported_parameters": ["max_tokens"]}}
        with env(OPENROUTER_API_KEY="sk-or-x"), fake_gateway(
            lambda request: Response(200, json=body)
        ):
            lines = run(probe.check_model("some/model"))
        # Без инструментов ни разбор КТП, ни генерация урока не работают.
        self.assertTrue(any("не заявляет поддержку инструментов" in line for line in lines))


class MoneyTests(unittest.TestCase):
    def test_formats_and_trims(self):
        self.assertEqual(probe._money(9.5), "$9.5")
        self.assertEqual(probe._money(0), "$0")
        self.assertEqual(probe._money(None), "—")
        self.assertEqual(probe._money("не число"), "—")


class ExitCodeTests(unittest.TestCase):
    def test_without_gateway_configured_it_explains_how(self):
        with env(OPENROUTER_API_KEY=None, LLM_PROVIDER=None,
                 LLM_PROVIDER_KTP_COLUMNS=None, LLM_PROVIDER_LESSON=None,
                 LLM_MODEL_KTP_COLUMNS=None, LLM_MODEL_LESSON=None):
            code = run(probe.main(do_call=False, load_env=False))
        self.assertEqual(code, 0)

    def test_broken_model_name_gives_nonzero_exit(self):
        def handler(request):
            if str(request.url).endswith("/key"):
                return Response(200, json=KEY_OK)
            return Response(404, json={"error": "not found"})

        with env(OPENROUTER_API_KEY="sk-or-x",
                 LLM_PROVIDER_KTP_COLUMNS="openrouter",
                 LLM_MODEL_KTP_COLUMNS="anthropic/опечатка"), fake_gateway(handler):
            code = run(probe.main(do_call=False, load_env=False))
        self.assertEqual(code, 1, "проверка обязана падать, если модели нет")


if __name__ == "__main__":
    unittest.main()
