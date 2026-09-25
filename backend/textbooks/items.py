"""Элементы параграфа: определения, формулы, примеры, вопросы, задачи, опыты.

Их выделяет модель по тексту параграфа (одинаково для текстовых PDF и сканов).
Генератор уроков берёт отсюда итоговые задачи и образцы для аналогов.
"""

from __future__ import annotations

from typing import Any

ITEMS_MAX_TOKENS = 12000
ITEM_KINDS = ("definition", "formula", "example", "question", "exercise", "experiment", "fact")

ITEMS_TOOL: dict[str, Any] = {
    "name": "textbook_items",
    "description": "Учебные элементы параграфа с точными номерами и страницами.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": list(ITEM_KINDS)},
                        "label": {"type": "string", "description": "Метка как в книге: «Упражнение 1, №2», «Пример 3», «Вопрос 4»; пусто для определений."},
                        "page": {"type": "integer", "description": "Печатный номер страницы."},
                        "text": {"type": "string", "description": "Дословный текст элемента, формулы в $…$."},
                        "answer": {"type": "string", "description": "Ответ, если он есть в книге (в тексте или разделе «Ответы»); иначе пусто."},
                        "difficulty": {"type": "integer", "enum": [1, 2, 3], "description": "1 — одно действие по образцу, 2 — несколько шагов, 3 — нестандартная."},
                    },
                    "required": ["kind", "page", "text"],
                },
            },
        },
        "required": ["items"],
    },
}

ITEMS_PROMPT = (
    "Ниже текст параграфа школьного учебника со страницами. Выдели учебные элементы: определения понятий, "
    "формулы (с поясняющей строкой), разобранные примеры с решением, вопросы к параграфу, упражнения и задачи "
    "(каждую задачу отдельно), опыты, ключевые факты (даты, числа). Текст — дословно, ничего не придумывай "
    "и не решай за книгу. Метки и номера — как в книге."
)


def parse_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict) or raw.get("kind") not in ITEM_KINDS or not str(raw.get("text") or "").strip():
            continue
        page = raw.get("page")
        difficulty = raw.get("difficulty")
        items.append({
            "kind": raw["kind"],
            "label": str(raw.get("label") or "").strip()[:120],
            "page": page if isinstance(page, int) and page > 0 else None,
            "text": str(raw["text"]).strip(),
            "answer": str(raw.get("answer") or "").strip() or None,
            "difficulty": difficulty if difficulty in (1, 2, 3) else None,
        })
    return items
