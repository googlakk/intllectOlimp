"""Распознавание страницы-скана моделью: текст с формулами в LaTeX."""

from __future__ import annotations

from typing import Any

OCR_MAX_TOKENS = 4000

OCR_TOOL: dict[str, Any] = {
    "name": "textbook_page",
    "description": "Точная расшифровка страницы школьного учебника.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Весь текст страницы по порядку чтения в markdown. Формулы — LaTeX в $…$, "
                               "заголовки — «## …», нумерованные задачи — «1. …». Колонтитулы и номер страницы не включать.",
            },
            "printed_page": {"type": "integer", "description": "Печатный номер страницы, если виден; иначе 0."},
            "figures": {
                "type": "array", "items": {"type": "string"},
                "description": "Короткое описание каждого рисунка, схемы или таблицы на странице.",
            },
            "uncertain": {
                "type": "array", "items": {"type": "string"},
                "description": "Фрагменты, прочитанные неуверенно (плохо видно, сложная формула).",
            },
        },
        "required": ["text", "printed_page", "uncertain"],
    },
}

OCR_PROMPT = (
    "Это скан страницы школьного учебника. Перепиши её дословно, ничего не добавляя и не исправляя. "
    "Сохраняй числа, единицы и обозначения точно как в книге; дроби — \\frac{}{}, степени — ^{}, индексы — _{}. "
    "Номера упражнений, задач и примеров сохраняй («УПРАЖНЕНИЕ 1», «Пример 2»). "
    "Если фрагмент не читается — напиши [неразборчиво] и добавь его в uncertain."
)


def parse_ocr_page(data: dict[str, Any]) -> dict[str, Any]:
    printed = data.get("printed_page")
    return {
        "text": str(data.get("text") or "").strip(),
        "printed_page": printed if isinstance(printed, int) and printed > 0 else None,
        "figures": [str(item) for item in data.get("figures") or [] if str(item).strip()],
        "uncertain": [str(item) for item in data.get("uncertain") or [] if str(item).strip()],
    }
