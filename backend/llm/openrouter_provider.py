"""Поставщик OpenRouter — один ключ, много моделей.

OpenRouter говорит на диалекте OpenAI, поэтому инструмент из формы Anthropic
(input_schema) переводится в форму OpenAI (function.parameters).

Важное отличие, из-за которого тут отдельная обработка: OpenAI отдаёт
аргументы инструмента СТРОКОЙ с JSON внутри, а не объектом. Строку надо
разобрать, и она может оказаться битой или обрезанной — это обычное дело,
а не исключительный случай.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ._http import AsyncClient, HTTPError
from .base import STOP_MAX_TOKENS, STOP_OTHER, STOP_TOOL, LLMError, ToolResult

BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
TIMEOUT = float(os.getenv("OPENROUTER_TIMEOUT", "180"))


def to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Инструмент из формы Anthropic в форму OpenAI."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    }


def parse_arguments(raw: Any) -> dict[str, Any] | None:
    """Аргументы инструмента. None — разобрать не удалось.

    Строка с JSON — штатный случай для OpenAI-диалекта. Объект тоже
    встречается: некоторые поставщики за шлюзом отдают уже разобранное.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def system_content(system: str, blocks: list[dict[str, Any]] | None, model: str) -> Any:
    """Для моделей Anthropic шлюз передаёт cache_control, остальным — просто текст."""
    if not blocks:
        return system
    parts = ([{"text": system, "cache": False}] if system else []) + list(blocks)
    if not model.startswith("anthropic/"):
        return "\n\n".join(part["text"] for part in parts)
    return [
        {"type": "text", "text": part["text"], **({"cache_control": {"type": "ephemeral"}} if part.get("cache") else {})}
        for part in parts
    ]


def user_content(user: str, images: list[dict[str, str]] | None) -> Any:
    """Картинки в форме OpenAI: data-URL в image_url, затем текст."""
    if not images:
        return user
    return [
        *({"type": "image_url", "image_url": {"url": f"data:{image['media_type']};base64,{image['data']}"}}
          for image in images),
        {"type": "text", "text": user},
    ]


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _headers(self) -> dict[str, str]:
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY не настроен", provider=self.name)
        # Заголовки HTTP — только ASCII. Без этой проверки опечатка в ключе
        # (кириллица, случайно скопированный пробел-неразрывник) вылезает
        # невнятным UnicodeEncodeError из недр httpx.
        if not api_key.isascii():
            raise LLMError(
                "OPENROUTER_API_KEY содержит не-ASCII символы — проверьте, "
                "не попала ли в ключ кириллица или лишние знаки при копировании",
                provider=self.name,
            )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter просит помечать приложение — влияет на рейтинги и лимиты.
        referer = os.getenv("OPENROUTER_SITE_URL")
        if referer:
            headers["HTTP-Referer"] = referer
        title = os.getenv("OPENROUTER_APP_TITLE", "Intellect Olimp")
        if title:
            headers["X-Title"] = title
        return headers

    async def call_tool(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        model: str,
        max_tokens: int,
        system_blocks: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        extra: dict[str, Any] | None = None,
        user_images: list[dict[str, str]] | None = None,
    ) -> ToolResult:
        # extra — параметры Anthropic (например, thinking); шлюзу они не передаются.
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content(system, system_blocks, model)},
                {"role": "user", "content": user_content(user, user_images)},
            ],
            "tools": [to_openai_tool(tool)],
            "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
        }
        headers = self._headers()

        client = self._client
        own_client = client is None
        if own_client:
            client = AsyncClient(timeout=TIMEOUT)
        try:
            response = await client.post(
                f"{BASE_URL}/chat/completions", json=payload, headers=headers,
                **({"timeout": timeout} if timeout is not None else {}),
            )
        except HTTPError as exc:
            raise LLMError(f"Запрос не прошёл: {exc}", provider=self.name, model=model) from exc
        finally:
            if own_client:
                await client.aclose()

        if response.status_code >= 400:
            raise LLMError(
                f"Шлюз ответил {response.status_code}: {response.text[:300]}",
                provider=self.name, model=model,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise LLMError("Шлюз вернул не JSON", provider=self.name, model=model) from exc

        return self._to_result(body, model)

    def _to_result(self, body: dict[str, Any], model: str) -> ToolResult:
        choices = body.get("choices") or []
        if not choices:
            error = (body.get("error") or {}).get("message")
            raise LLMError(
                f"Шлюз не вернул ответа{': ' + error if error else ''}",
                provider=self.name, model=model,
            )
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") or {}
        finish = choice.get("finish_reason") or ""
        text = message.get("content") or ""
        if not isinstance(text, str):
            text = ""
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        # Модель, которая реально ответила, может отличаться от запрошенной:
        # шлюз умеет подменять её при недоступности.
        served = body.get("model") or model

        calls = message.get("tool_calls") or []
        # Обрыв по лимиту — всегда обрыв, даже если оборванный JSON случайно
        # разобрался: данные в нём неполные.
        if finish == "length":
            return ToolResult(
                stop_reason=STOP_MAX_TOKENS, text=text, provider=self.name, model=served, usage=usage,
            )
        if calls and isinstance(calls[0], dict):
            arguments = ((calls[0].get("function") or {}).get("arguments"))
            data = parse_arguments(arguments)
            if data is not None:
                return ToolResult(
                    data=data, stop_reason=STOP_TOOL, text=text,
                    provider=self.name, model=served, usage=usage,
                )
            # Аргументы не разобрались, а обрыва не было — честно сообщаем про битый JSON.
            return ToolResult(
                stop_reason=STOP_OTHER, text=str(arguments)[:2000],
                provider=self.name, model=served, usage=usage,
            )

        stop = STOP_MAX_TOKENS if finish == "length" else STOP_OTHER
        return ToolResult(
            stop_reason=stop, text=text, provider=self.name, model=served, usage=usage,
        )
