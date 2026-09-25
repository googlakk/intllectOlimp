"""Поставщик Anthropic — прямое обращение, без посредника.

Остаётся в проекте намеренно: за прямой доступ не берётся комиссия шлюза,
и это запасной путь, если шлюз окажется недоступен.
"""

from __future__ import annotations

import os
from typing import Any

from .base import STOP_MAX_TOKENS, STOP_OTHER, STOP_TOOL, LLMError, ToolResult


def _system_param(system: str, blocks: list[dict[str, Any]] | None) -> Any:
    """Строка, как раньше, или список блоков с кэшем для повторяющихся частей."""
    if not blocks:
        return system
    parts = ([{"text": system, "cache": False}] if system else []) + list(blocks)
    return [
        {"type": "text", "text": part["text"], **({"cache_control": {"type": "ephemeral"}} if part.get("cache") else {})}
        for part in parts
    ]


def _user_content(user: str, images: list[dict[str, str]] | None) -> Any:
    """Без картинок — строка, как раньше; с картинками — сначала изображения, потом текст."""
    if not images:
        return user
    return [
        *({"type": "image", "source": {"type": "base64", "media_type": image["media_type"], "data": image["data"]}}
          for image in images),
        {"type": "text", "text": user},
    ]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _build_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY не настроен", provider=self.name)
        kwargs: dict[str, Any] = {"api_key": api_key}
        # Workspace нужен не всем ключам, поэтому он необязателен.
        workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
        if workspace_id:
            kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(**kwargs)
        return self._client

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
        client = self._build_client()
        if timeout is not None and hasattr(client, "with_options"):
            client = client.with_options(timeout=timeout, max_retries=0)
        try:
            message = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=_system_param(system, system_blocks),
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": _user_content(user, user_images)}],
                **(extra or {}),
            )
        except Exception as exc:  # сеть, ключ, лимиты — наверх с контекстом
            raise LLMError(f"Запрос не прошёл: {exc}", provider=self.name, model=model) from exc

        text = "".join(
            block.text for block in message.content
            if getattr(block, "type", "") == "text"
        )
        usage = {}
        if getattr(message, "usage", None) is not None:
            usage = {
                "input_tokens": getattr(message.usage, "input_tokens", None),
                "output_tokens": getattr(message.usage, "output_tokens", None),
                "cache_read_input_tokens": getattr(message.usage, "cache_read_input_tokens", None),
                "cache_creation_input_tokens": getattr(message.usage, "cache_creation_input_tokens", None),
            }

        tool_block = next(
            (b for b in message.content if getattr(b, "type", "") == "tool_use"), None
        )
        # Обрыв на лимите посреди вызова инструмента тоже приходит блоком
        # tool_use, но с неполными данными — это обрыв, а не готовый ответ.
        if message.stop_reason == "max_tokens":
            return ToolResult(
                stop_reason=STOP_MAX_TOKENS, text=text, provider=self.name, model=model, usage=usage,
            )
        if tool_block is not None:
            return ToolResult(
                data=dict(tool_block.input),
                stop_reason=STOP_TOOL,
                text=text,
                provider=self.name,
                model=model,
                usage=usage,
            )

        stop = STOP_MAX_TOKENS if message.stop_reason == "max_tokens" else STOP_OTHER
        return ToolResult(
            stop_reason=stop, text=text, provider=self.name, model=model, usage=usage,
        )
