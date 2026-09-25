"""Нейтральный слой над поставщиками моделей.

Смысл слоя — портируемость. Продукт должен переезжать на свои сервера без
переписывания, поэтому код приложения не знает, кто именно отвечает:
Anthropic напрямую, OpenRouter или что-то следующее. Он знает только задачу
(«разобрать колонки КТП», «сгенерировать урок») и получает ответ в одном виде.

Инструмент описывается в форме Anthropic (name / description / input_schema).
Это не привязка к поставщику: форма выбрана потому, что она уже используется
в проекте, а провайдер OpenRouter переводит её в форму OpenAI сам.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

# Нормализованные причины остановки — одинаковые у всех поставщиков.
STOP_TOOL = "tool_use"        # инструмент заполнен, данные есть
STOP_MAX_TOKENS = "max_tokens"  # ответ не поместился
STOP_OTHER = "other"          # модель ответила текстом или чем-то ещё


class SystemBlock(TypedDict):
    """Часть системного промпта. cache=True — поставщик может закэшировать
    её и всё, что идёт до неё (у Anthropic — cache_control: ephemeral)."""

    text: str
    cache: bool


class UserImage(TypedDict):
    """Картинка в сообщении пользователя (например, скан страницы учебника).
    data — base64 без префикса data:, media_type — image/png или image/jpeg."""
    media_type: str
    data: str


class LLMError(RuntimeError):
    """Ошибка обращения к модели с указанием поставщика и модели."""

    def __init__(self, message: str, *, provider: str = "", model: str = "") -> None:
        self.provider = provider
        self.model = model
        where = " / ".join(part for part in (provider, model) if part)
        super().__init__(f"{message} ({where})" if where else message)


@dataclass
class ToolResult:
    """Ответ модели в едином виде, не зависящем от поставщика."""

    data: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = STOP_OTHER
    text: str = ""
    provider: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.stop_reason == STOP_TOOL and bool(self.data)

    @property
    def truncated(self) -> bool:
        return self.stop_reason == STOP_MAX_TOKENS


class LLMProvider(Protocol):
    """Что обязан уметь поставщик. Ничего сверх одного вызова с инструментом."""

    name: str

    async def call_tool(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        model: str,
        max_tokens: int,
        system_blocks: list[SystemBlock] | None = None,
        timeout: float | None = None,
        extra: dict[str, Any] | None = None,
        user_images: list[UserImage] | None = None,
    ) -> ToolResult:
        """system_blocks, timeout, extra и user_images необязательны: старые вызовы их не передают."""
        ...
