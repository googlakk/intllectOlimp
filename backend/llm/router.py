"""Какая модель на какую задачу.

Разные задачи стоят разного. Разбор колонок КТП — это десяток чисел в ответ,
туда хватит дешёвой модели. Генерация урока — содержательная работа, там
нужна сильная. Раньше обе шли через одну модель, и за разбор структуры
платилось как за урок.

Настраивается переменными окружения, без правки кода:

    LLM_PROVIDER=anthropic              # поставщик по умолчанию
    LLM_MODEL_KTP_COLUMNS=claude-haiku-4-5
    LLM_PROVIDER_KTP_COLUMNS=openrouter # поставщик для одной задачи
    LLM_MODEL_LESSON=claude-sonnet-4-6

Имя задачи в переменной — заглавными, дефисы заменены подчёркиванием.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .anthropic_provider import AnthropicProvider
from .base import LLMError, LLMProvider, SystemBlock, ToolResult
from .openrouter_provider import OpenRouterProvider

# Задачи, которые сейчас есть в продукте.
TASK_KTP_COLUMNS = "ktp-columns"
TASK_LESSON = "lesson"
TASK_TUTOR = "tutor"

# Значения по умолчанию: без единой настройки всё работает как раньше —
# прямой Anthropic. Переход на шлюз включается переменными окружения.
DEFAULTS: dict[str, dict[str, str]] = {
    TASK_KTP_COLUMNS: {
        "anthropic": "claude-sonnet-4-6",
        "openrouter": "anthropic/claude-haiku-4.5",
    },
    TASK_LESSON: {
        "anthropic": "claude-sonnet-4-6",
        "openrouter": "anthropic/claude-sonnet-4.6",
    },
    # Тьютор отвечает ученику в реальном времени: нужна сильная модель,
    # но короткие ответы. Модель меняется переменной LLM_MODEL_TUTOR.
    TASK_TUTOR: {
        "anthropic": "claude-sonnet-5",
        "openrouter": "anthropic/claude-sonnet-5",
    },
}

PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openrouter": OpenRouterProvider,
}


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    task: str


def _env_suffix(task: str) -> str:
    return task.upper().replace("-", "_")


def resolve_route(task: str, env: dict[str, str] | None = None) -> Route:
    """Куда идёт эта задача. Частная настройка важнее общей."""
    env = os.environ if env is None else env
    suffix = _env_suffix(task)

    provider = (
        env.get(f"LLM_PROVIDER_{suffix}")
        or env.get("LLM_PROVIDER")
        or "anthropic"
    ).strip().lower()
    if provider not in PROVIDERS:
        raise LLMError(
            f"Неизвестный поставщик «{provider}». Доступны: "
            + ", ".join(sorted(PROVIDERS))
        )

    model = (env.get(f"LLM_MODEL_{suffix}") or "").strip()
    if not model:
        model = DEFAULTS.get(task, {}).get(provider, "")
    if not model:
        raise LLMError(
            f"Для задачи «{task}» не задана модель. Укажите LLM_MODEL_{suffix}.",
            provider=provider,
        )
    return Route(provider=provider, model=model, task=task)


def build_provider(name: str, **kwargs: Any) -> LLMProvider:
    factory = PROVIDERS.get(name)
    if factory is None:
        raise LLMError(f"Неизвестный поставщик «{name}»")
    return factory(**kwargs)


async def call_tool(
    task: str,
    *,
    system: str,
    user: str,
    tool: dict[str, Any],
    max_tokens: int,
    provider: LLMProvider | None = None,
    env: dict[str, str] | None = None,
    route: Route | None = None,
    system_blocks: list[SystemBlock] | None = None,
    timeout: float | None = None,
    extra: dict[str, Any] | None = None,
) -> ToolResult:
    """Единственная точка входа для приложения.

    Код вызывающей стороны не знает ни поставщика, ни модели — только задачу.
    Поэтому переезд на свои сервера не затрагивает бизнес-логику.
    """
    # Явный маршрут — выбор учителя из проверенного каталога (catalog.py).
    route = route or resolve_route(task, env)
    engine = provider if provider is not None else build_provider(route.provider)
    # Новые параметры передаются, только если заданы: старые поставщики и
    # тестовые подмены их не знают.
    optional = {
        key: value
        for key, value in (("system_blocks", system_blocks), ("timeout", timeout), ("extra", extra))
        if value is not None
    }
    return await engine.call_tool(
        system=system, user=user, tool=tool,
        model=route.model, max_tokens=max_tokens, **optional,
    )
