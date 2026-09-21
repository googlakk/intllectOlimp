"""Проверка шлюза до того, как потрачены деньги.

Показывает: куда настроена каждая задача, жив ли ключ, сколько на нём
осталось, есть ли выбранная модель и сколько она стоит. По флагу --call
делает один настоящий, самый дешёвый вызов — чтобы убедиться, что связка
работает целиком, а не только на бумаге.

Запуск из каталога backend:
    ../.venv/bin/python -m llm.probe
    ../.venv/bin/python -m llm.probe --call
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from ._http import AsyncClient, HTTPError
from .base import LLMError
from .openrouter_provider import BASE_URL
from .router import DEFAULTS, TASK_KTP_COLUMNS, TASK_LESSON, resolve_route

TASKS = (TASK_KTP_COLUMNS, TASK_LESSON)

# Самый дешёвый честный вызов: схема из одного поля, ответ в пару токенов.
PROBE_TOOL = {
    "name": "answer",
    "description": "Вернуть ответ одним словом.",
    "input_schema": {
        "type": "object",
        "properties": {"word": {"type": "string"}},
        "required": ["word"],
    },
}


def _money(value: Any) -> str:
    try:
        return f"${float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "—"


async def _get(path: str, key: str) -> tuple[int, Any]:
    async with AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {key}"},
        )
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.text[:300]


async def check_openrouter_key() -> list[str]:
    """Что известно о ключе: баланс, расход, тариф."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return ["  OPENROUTER_API_KEY не задан — проверять нечего"]
    if not key.isascii():
        return ["  ✗ ключ содержит не-ASCII символы (кириллица при копировании?)"]

    try:
        status, body = await _get("/key", key)
    except HTTPError as exc:
        return [f"  ✗ не удалось связаться со шлюзом: {exc}"]

    if status == 401:
        return ["  ✗ ключ не принят (401) — проверьте, что скопирован целиком"]
    if status >= 400:
        return [f"  ✗ шлюз ответил {status}: {str(body)[:160]}"]

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return [f"  ? неожиданный ответ: {str(body)[:160]}"]

    lines = ["  ✓ ключ принят"]
    limit = data.get("limit")
    remaining = data.get("limit_remaining")
    if limit is None:
        lines.append("    лимит на ключе: не установлен")
    else:
        lines.append(f"    лимит на ключе: {_money(limit)}, осталось {_money(remaining)}")
    lines.append(
        f"    израсходовано: всего {_money(data.get('usage'))}, "
        f"за сегодня {_money(data.get('usage_daily'))}, "
        f"за месяц {_money(data.get('usage_monthly'))}"
    )
    if data.get("is_free_tier"):
        lines.append(
            "    ⚠ бесплатный тариф: платные модели недоступны, "
            "у бесплатных — 50 запросов в сутки"
        )
    if isinstance(remaining, (int, float)) and remaining <= 0:
        lines.append("    ⚠ остаток исчерпан — запросы будут падать с 402")
    return lines


async def check_model(model: str) -> list[str]:
    """Есть ли такая модель у шлюза и сколько стоит."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return []
    try:
        status, body = await _get(f"/model/{model}", key)
    except HTTPError as exc:
        return [f"    ✗ не удалось проверить модель: {exc}"]

    if status == 404:
        return [f"    ✗ модель «{model}» у шлюза не найдена — опечатка в названии?"]
    if status >= 400:
        return [f"    ? проверка модели вернула {status}"]

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return ["    ? неожиданный ответ при проверке модели"]

    lines = [f"    ✓ модель доступна: {data.get('name') or model}"]
    pricing = data.get("pricing") or {}
    prompt = pricing.get("prompt")
    completion = pricing.get("completion")
    if prompt is not None and completion is not None:
        try:
            lines.append(
                f"      цена за 1M токенов: вход {_money(float(prompt) * 1_000_000)}, "
                f"выход {_money(float(completion) * 1_000_000)}"
            )
        except (TypeError, ValueError):
            pass
    supported = data.get("supported_parameters") or []
    if "tools" not in supported:
        lines.append(
            "      ⚠ модель не заявляет поддержку инструментов (tools) — "
            "разбор КТП и генерация урока работать не будут"
        )
    return lines


async def try_call(task: str) -> list[str]:
    """Один настоящий вызов — самый дешёвый из возможных."""
    from .router import call_tool
    try:
        result = await call_tool(
            task,
            system="Отвечай одним словом через инструмент answer.",
            user="Скажи слово: готово",
            tool=PROBE_TOOL,
            max_tokens=100,
        )
    except LLMError as exc:
        return [f"    ✗ вызов не прошёл: {exc}"]
    except Exception as exc:  # noqa: BLE001 — показать любую причину
        return [f"    ✗ вызов не прошёл: {type(exc).__name__}: {exc}"]

    if result.ok:
        word = str(result.data.get("word", ""))[:40]
        usage = ""
        if result.usage:
            usage = f", токенов: {result.usage}"
        return [f"    ✓ вызов прошёл, модель ответила «{word}»{usage}"]
    return [f"    ✗ модель не заполнила инструмент (stop={result.stop_reason})"]


async def main(do_call: bool, load_env: bool = True) -> int:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if load_env and env_path.is_file():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    print("=== МАРШРУТЫ ЗАДАЧ ===")
    routes = []
    problems = 0
    for task in TASKS:
        try:
            route = resolve_route(task)
        except LLMError as exc:
            print(f"  {task}: ✗ {exc}")
            problems += 1
            continue
        routes.append(route)
        default = DEFAULTS.get(task, {}).get(route.provider)
        mark = "" if route.model != default else "  (по умолчанию)"
        print(f"  {task}: {route.provider} → {route.model}{mark}")

    uses_gateway = any(route.provider == "openrouter" for route in routes)
    if not uses_gateway:
        print()
        print("Шлюз OpenRouter не задействован — все задачи идут напрямую в Anthropic.")
        print("Чтобы попробовать шлюз, добавьте в .env:")
        print("  OPENROUTER_API_KEY=sk-or-...")
        print("  LLM_PROVIDER_KTP_COLUMNS=openrouter")
        print("  LLM_MODEL_KTP_COLUMNS=anthropic/claude-haiku-4.5")
        return 1 if problems else 0

    print()
    print("=== КЛЮЧ OPENROUTER ===")
    for line in await check_openrouter_key():
        print(line)
        if "✗" in line:
            problems += 1

    print()
    print("=== МОДЕЛИ ===")
    for route in routes:
        if route.provider != "openrouter":
            continue
        print(f"  {route.task}: {route.model}")
        for line in await check_model(route.model):
            print(line)
            if "✗" in line:
                problems += 1

    if do_call:
        print()
        print("=== ПРОБНЫЙ ВЫЗОВ (стоит доли цента) ===")
        for route in routes:
            print(f"  {route.task} → {route.provider} / {route.model}")
            for line in await try_call(route.task):
                print(line)
                if "✗" in line:
                    problems += 1

    print()
    if problems:
        print(f"Проблем: {problems}. Разбор КТП запускать рано.")
    else:
        print("Всё на месте." + ("" if do_call else " Добавьте --call для живой проверки."))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--call" in sys.argv)))
