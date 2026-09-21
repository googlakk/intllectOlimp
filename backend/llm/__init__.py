"""Шлюз к моделям: одна точка входа, сменный поставщик.

    from llm import call_tool, TASK_LESSON

    result = await call_tool(TASK_LESSON, system=..., user=..., tool=..., max_tokens=16000)
    if result.truncated: ...
    if result.ok: result.data
"""

from .base import (
    STOP_MAX_TOKENS, STOP_OTHER, STOP_TOOL, LLMError, LLMProvider, ToolResult,
)

_ROUTER_EXPORTS = {
    "TASK_KTP_COLUMNS", "TASK_LESSON", "Route", "DEFAULTS", "PROVIDERS",
    "call_tool", "resolve_route", "build_provider",
}


def __getattr__(name: str):
    if name in _ROUTER_EXPORTS:
        from . import router

        value = getattr(router, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "LLMError", "LLMProvider", "ToolResult",
    "STOP_TOOL", "STOP_MAX_TOKENS", "STOP_OTHER",
    "TASK_KTP_COLUMNS", "TASK_LESSON", "Route", "DEFAULTS", "PROVIDERS",
    "call_tool", "resolve_route", "build_provider",
]
