"""Модели, которые учитель может выбрать в интерфейсе.

Список закрытый: из браузера приходит только id варианта, произвольную
строку модели сервер не примет. Модель по умолчанию по-прежнему задаётся
переменными окружения (router.py, media.py) и всегда есть в списке.
Добавить вариант — дописать строку сюда, фронтенд подхватит сам.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .base import LLMError
from .media import image_model
from .router import TASK_LESSON, Route, resolve_route


@dataclass(frozen=True)
class ModelOption:
    provider: str
    model: str
    label: str
    note: str = ""
    # Параметры, которые модель картинок принимает на /images.
    # None — неизвестно, отправляем всё как раньше.
    image_params: frozenset[str] | None = None

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.model}"


LESSON_MODELS: tuple[ModelOption, ...] = (
    ModelOption("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", "Anthropic · $3 / $15 за 1 млн токенов"),
    ModelOption("anthropic", "claude-sonnet-5", "Claude Sonnet 5", "Anthropic · $2 / $10 за 1 млн токенов"),
    ModelOption("anthropic", "claude-opus-5", "Claude Opus 5", "Anthropic · $5 / $25 за 1 млн токенов"),
    ModelOption("openrouter", "openai/gpt-6-sol", "GPT-6 Sol", "OpenAI через OpenRouter · $2 / $10 за 1 млн токенов"),
    ModelOption("openrouter", "google/gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)", "Google через OpenRouter · $2 / $12 за 1 млн токенов"),
)

_GEMINI_PARAMS = frozenset({"resolution", "aspect_ratio", "n"})

IMAGE_MODELS: tuple[ModelOption, ...] = (
    ModelOption("openrouter", "google/gemini-2.5-flash-image", "Gemini 2.5 Flash Image", "Google · самая дешёвая",
                frozenset({"aspect_ratio", "n"})),
    ModelOption("openrouter", "google/gemini-3.1-flash-image", "Gemini 3.1 Flash Image", "Google · быстрая, новое поколение",
                _GEMINI_PARAMS),
    ModelOption("openrouter", "google/gemini-3-pro-image", "Gemini 3 Pro Image", "Google · самая детальная, дороже",
                _GEMINI_PARAMS),
    ModelOption("openrouter", "openai/gpt-image-2", "GPT Image 2", "OpenAI · сильна в реалистичных сценах",
                frozenset({"aspect_ratio", "quality", "n"})),
)

_PROVIDER_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


class ModelChoiceError(LLMError):
    """Выбранной модели нет в списке или у сервера нет ключа поставщика."""


def provider_available(provider: str, env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    key = _PROVIDER_KEYS.get(provider)
    return bool(key and (source.get(key) or "").strip())


def _serialize(option: ModelOption, default_id: str, env: dict[str, str] | None) -> dict[str, Any]:
    return {
        "id": option.id,
        "provider": option.provider,
        "model": option.model,
        "label": option.label,
        "note": option.note,
        "available": provider_available(option.provider, env),
        "default": option.id == default_id,
    }


def _with_default(options: tuple[ModelOption, ...], default: ModelOption) -> tuple[ModelOption, ...]:
    if any(option.id == default.id for option in options):
        return options
    return (ModelOption(default.provider, default.model, default.model, "Из настроек сервера"), *options)


def _lesson_default(env: dict[str, str] | None) -> ModelOption:
    route = resolve_route(TASK_LESSON, env)
    return ModelOption(route.provider, route.model, route.model)


def _image_default(env: dict[str, str] | None) -> ModelOption:
    return ModelOption("openrouter", image_model(env), image_model(env))


def model_catalog(env: dict[str, str] | None = None) -> dict[str, Any]:
    lesson_default = _lesson_default(env)
    image_default = _image_default(env)
    return {
        "lesson": {
            "default": lesson_default.id,
            "options": [_serialize(o, lesson_default.id, env) for o in _with_default(LESSON_MODELS, lesson_default)],
        },
        "image": {
            "default": image_default.id,
            "options": [_serialize(o, image_default.id, env) for o in _with_default(IMAGE_MODELS, image_default)],
        },
    }


def _find(options: tuple[ModelOption, ...], choice: str) -> ModelOption | None:
    return next((option for option in options if option.id == choice), None)


def resolve_lesson_choice(choice: str | None, env: dict[str, str] | None = None) -> Route | None:
    """None — модель по умолчанию из настроек. Иначе проверенный маршрут."""
    if not choice:
        return None
    option = _find(_with_default(LESSON_MODELS, _lesson_default(env)), choice)
    if option is None:
        raise ModelChoiceError(f"Модель «{choice}» недоступна для генерации урока")
    if not provider_available(option.provider, env):
        raise ModelChoiceError(f"Для модели «{option.label}» на сервере не настроен ключ поставщика", provider=option.provider)
    return Route(provider=option.provider, model=option.model, task=TASK_LESSON)


def resolve_image_choice(choice: str | None, env: dict[str, str] | None = None) -> str | None:
    """Принимает id варианта (openrouter:<model>) или чистое имя модели."""
    if not choice:
        return None
    options = _with_default(IMAGE_MODELS, _image_default(env))
    option = _find(options, choice) or _find(options, f"openrouter:{choice}")
    if option is None:
        raise ModelChoiceError(f"Модель «{choice}» недоступна для изображений")
    return option.model


def image_supported_params(model: str) -> frozenset[str] | None:
    option = next((o for o in IMAGE_MODELS if o.model == model), None)
    return option.image_params if option else None
