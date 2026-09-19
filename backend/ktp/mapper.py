"""Сопоставление извлечённых таблиц КТП со схемой платформы через Anthropic.

Модель НЕ придумывает содержание. Она получает уже извлечённые строки таблицы
и только раскладывает их по полям: где раздел, где тема, сколько часов,
какой текст является целями обучения. Любой текст в результате обязан
дословно присутствовать во входных данных.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from .extract import Extraction

MODEL = os.getenv("KTP_MAPPER_MODEL", "claude-sonnet-4-6")
MAX_ROWS_PER_CALL = 40
MAX_TOKENS = 16000


TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "ktp_number": {"type": "string"},
        "name": {"type": "string"},
        "hours": {"type": "integer"},
        "lesson_type": {"type": "string", "enum": ["study", "assessment", "project"]},
        "learning_objectives": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "resources": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "low"]},
        "note": {"type": "string"},
    },
    "required": ["ktp_number", "name", "hours", "lesson_type",
                 "learning_objectives", "skills", "resources", "confidence", "note"],
}

KTP_TOOL = {
    "name": "submit_ktp",
    "description": "Передать разобранный календарно-тематический план.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_name": {"type": "string"},
            "grade": {"type": "integer"},
            "hours_per_week": {"type": "number"},
            "hours_per_year": {"type": "integer"},
            "instruction_language": {"type": "string", "enum": ["ru", "ky"]},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total_hours": {"type": "integer"},
                        "topics": {"type": "array", "items": TOPIC_SCHEMA},
                    },
                    "required": ["name", "total_hours", "topics"],
                },
            },
            "column_mapping": {"type": "object", "additionalProperties": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["subject_name", "grade", "hours_per_week", "hours_per_year",
                     "instruction_language", "sections", "column_mapping", "warnings"],
    },
}

SYSTEM_PROMPT = """
Ты разбираешь календарно-тематический план (КТП) школьного предмета и
раскладываешь его по заданной структуре.

ГЛАВНОЕ ПРАВИЛО: ты ничего не сочиняешь. Каждая строка текста в твоём ответе
обязана дословно присутствовать во входных данных. Нельзя переформулировать
темы, дописывать цели обучения, додумывать часы. Если данных нет — оставь
пустую строку или ноль.

Результат передай вызовом инструмента submit_ktp. Ничего не пиши текстом.

Как разбирать:
- Строка, где заполнено только название и нет номера и часов, — это РАЗДЕЛ.
  Часы раздела часто указаны в скобках: "ВВЕДЕНИЕ (1 Ч.)" → name "ВВЕДЕНИЕ",
  total_hours 1. Скобки с часами из названия убери.
- Строка с номером и часами — это ТЕМА внутри последнего встреченного раздела.
- lesson_type: "assessment" для контрольных, зачётов, тестов, сочинений;
  "project" для проектов и исследований; иначе "study". Определяй по словам
  в названии темы, а не по догадке.
- learning_objectives: дословный текст колонки целей обучения. Если явной
  колонки целей нет, возьми дословно текст колонок с планируемыми
  результатами (предметными) и укажи источник в column_mapping.
- skills: пункты колонки умений и навыков, разбитые по маркерам списка.
- resources: дословный текст колонки ресурсов, учебников, домашних заданий.
- confidence "low" и пояснение в note — для строк, где разметка неочевидна:
  склеенные колонки, пропущенные часы, непонятный номер.
- column_mapping: какая колонка исходной таблицы во что превратилась.
- warnings: расхождения в документе (например, класс в заголовке не совпадает
  с классом в таблице), потерянные строки, испорченная разметка.

Служебные таблицы — учебники, методические материалы, списки литературы —
в sections не попадают. Упомяни их в warnings.

ВАЖНО про части: документ разрезан на части чисто технически, по числу строк.
Это не структура документа. Не пиши в warnings, что документ неполный, что
глава представлена частично или что чего-то не хватает из-за разбиения —
недостающее находится в соседних частях и будет склеено автоматически.
В warnings пиши только про реальные дефекты самого документа.

НИЧЕГО НЕ ДОСОЧИНЯЙ — но и не теряй то, что есть:
- Если номер стоит в начале названия темы ("1.1. Четыре операции над целыми
  числами"), это НОМЕР ИЗ ИСТОЧНИКА. Вынеси его в ktp_number ("1.1"), а из
  name убери ("Четыре операции над целыми числами"). Отдельной колонки с
  номерами может не быть вовсе — это нормально.
- Если номера нет нигде — ни отдельной колонкой, ни в начале названия —
  ktp_number оставь пустой строкой. Не присваивай номера по порядку.
- Часть начинается без заголовка раздела — не восстанавливай заголовок по смыслу.
  Оставь name раздела пустой строкой, поставь confidence "low" у его тем и
  напиши в warnings, что раздел не определён. Склейка с соседней частью
  произойдёт автоматически.
""".strip()


def _rows_payload(extraction: Extraction, limit: int = MAX_ROWS_PER_CALL) -> list[str]:
    """Готовит текстовое представление таблиц, порезанное на части по строкам."""
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for table_index, table in enumerate(extraction.tables):
        for row in table:
            current.append(f"т{table_index + 1}\t" + "\t".join(row))
            count += 1
            if count >= limit:
                chunks.append("\n".join(current))
                current, count = [], 0
    if current:
        chunks.append("\n".join(current))
    return chunks


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Модель вернула не объект JSON")
    return value


# Подтверждения ("сумма совпадает") и дубли по частям учителю не нужны —
# в редакторе он должен видеть только то, что требует его внимания.
_NOT_A_WARNING = ("совпадает с заявленн", "совпадает с указанн", "не включены в sections",
                  "служебн", "пояснительная записка")

# Про часы модель пишет по разу в каждой части и разными словами. Своё
# посчитанное значение мы добавляем ниже сами — оно и остаётся.
_HOURS_NOISE = ("не указан", "не указаны", "явно не указан")


def _clean_warnings(warnings: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        text = " ".join(warning.split())
        lowered = text.lower()
        if any(marker in lowered for marker in _NOT_A_WARNING):
            continue
        if ("час" in lowered and any(marker in lowered for marker in _HOURS_NOISE)
                and "посчитано" not in lowered):
            continue
        key = text[:70].lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _merge(parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Склеивает результаты по частям: разделы с одинаковым именем объединяются."""
    if not parts:
        raise ValueError("Не удалось разобрать ни одной части документа")
    result = dict(parts[0])
    sections: list[dict[str, Any]] = []
    warnings: list[str] = []
    mapping: dict[str, str] = {}
    for part in parts:
        mapping.update(part.get("column_mapping") or {})
        warnings.extend(part.get("warnings") or [])
        for section in part.get("sections") or []:
            existing = next((s for s in sections if s.get("name") == section.get("name")), None)
            if existing:
                existing.setdefault("topics", []).extend(section.get("topics") or [])
            else:
                sections.append(section)
    result["sections"] = sections
    result["column_mapping"] = mapping
    result["warnings"] = _clean_warnings(warnings)

    # Часы считаем сами: модель видит только свою часть и ставит нули.
    topics = [t for s in sections for t in (s.get("topics") or [])]
    total_hours = sum(int(t.get("hours") or 0) for t in topics)
    if not result.get("hours_per_year") and total_hours:
        result["hours_per_year"] = total_hours
        result["warnings"].append(
            f"Часов в год в документе не указано — посчитано по темам: {total_hours}"
        )
    for section in sections:
        if not section.get("total_hours"):
            section["total_hours"] = sum(int(t.get("hours") or 0) for t in (section.get("topics") or []))
    return result


async def map_to_schema(extraction: Extraction) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не настроен")
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    if workspace_id:
        client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
    client = AsyncAnthropic(**client_kwargs)

    parts: list[dict[str, Any]] = []
    chunks = _rows_payload(extraction)
    seen_sections: list[str] = []
    for index, chunk in enumerate(chunks):
        context = ""
        if seen_sections:
            context = (
                "Разделы, уже найденные в предыдущих частях (по порядку):\n"
                + "\n".join(f"  - {name}" for name in seen_sections)
                + "\nЕсли эта часть начинается сразу с тем, без заголовка раздела, —\n"
                  "это продолжение ПОСЛЕДНЕГО раздела из списка. Укажи его имя\n"
                  "дословно, не помечай как неопределённый и не пиши об этом в warnings.\n\n"
            )
        user_prompt = (
            f"Заголовок документа:\n{extraction.header_text[:2000]}\n\n"
            f"{context}"
            f"Часть {index + 1} из {len(chunks)}. Строки таблиц "
            f"(первая колонка — номер таблицы, дальше ячейки через табуляцию):\n{chunk}\n\n"
            "Результат передай вызовом submit_ktp."
        )
        message = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[KTP_TOOL],
            tool_choice={"type": "tool", "name": "submit_ktp"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        tool_block = next((b for b in message.content if b.type == "tool_use"), None)
        if tool_block is not None:
            part = dict(tool_block.input)
            parts.append(part)
            for section in part.get("sections") or []:
                name = (section.get("name") or "").strip()
                if name and name not in seen_sections:
                    seen_sections.append(name)
            continue

        # Инструмент не заполнен — сохраняем сырой ответ, чтобы не гадать вслепую
        text_block = next((b for b in message.content if b.type == "text"), None)
        dump = Path(tempfile.gettempdir()) / f"ktp-raw-{index + 1}.txt"
        dump.write_text(
            f"stop_reason={message.stop_reason}\n\n" + (text_block.text if text_block else "<пусто>"),
            encoding="utf-8",
        )
        if message.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Часть {index + 1}: ответ не поместился в лимит. "
                f"Уменьшите MAX_ROWS_PER_CALL. Сырой ответ: {dump}"
            )
        raise RuntimeError(f"Часть {index + 1}: модель не вызвала инструмент. Сырой ответ: {dump}")
    return _merge(parts)
