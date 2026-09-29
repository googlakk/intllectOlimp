"""Разбор КТП: карта колонок от модели + детерминированная сборка.

Порядок работы:
  1. extract   — вытащить таблицы из docx/pdf (код, без модели);
  2. columns   — понять, какая колонка что означает (ОДИН вызов модели);
  3. assemble  — собрать разделы и темы построчно (код, без модели).

Содержимое плана через модель не проходит. Поэтому потерять тему нельзя в
принципе, а дословность целей обеспечена самим способом, а не проверкой
постфактум. Прежняя версия гоняла через модель каждую строку и теряла темы,
когда ответ упирался в потолок.
"""

from __future__ import annotations

import re
from typing import Any

from languages import normalize_language

from .assemble import ColumnMap, assemble
from .columns import detect_columns, to_column_maps
from .extract import Extraction
from .validate import verify_maps
from .template import is_standard_template, map_standard_template

FIELD_NAMES = {
    "number": "ktp_number",
    "name": "name",
    "hours": "hours",
    "objectives": "learning_objectives",
    "resources": "resources",
    "note": "note",
}

_NOT_A_WARNING = ("совпадает с заявленн", "совпадает с указанн", "не включены в sections",
                  "пояснительная записка")


def _clean_warnings(warnings: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if not isinstance(warning, str):
            continue
        text = " ".join(warning.split())
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _NOT_A_WARNING):
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _column_mapping(maps: list[ColumnMap]) -> dict[str, str]:
    """Читаемая расшифровка карты — чтобы было видно, что куда легло."""
    mapping: dict[str, str] = {}
    for item in maps:
        prefix = f"таблица {item.table_index}, колонка"
        for attribute, field in FIELD_NAMES.items():
            index = getattr(item, attribute)
            if index is not None:
                mapping[f"{prefix} {index}"] = field
        for index in item.skills:
            mapping[f"{prefix} {index}"] = "skills"
        if item.number_in_name:
            mapping[f"таблица {item.table_index}"] = "номер темы — в начале названия"
    return mapping


def _hours_per_week(payload: dict[str, Any], header_text: str) -> float:
    value = payload.get("hours_per_week")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*час[а-яё]*\s+в\s+недел", header_text, re.IGNORECASE)
    return float(match.group(1).replace(",", ".")) if match else 1.0


def _grade(payload: dict[str, Any], header_text: str) -> int:
    value = payload.get("grade")
    if isinstance(value, int) and 1 <= value <= 11:
        return value
    match = re.search(r"(\d{1,2})\s*класс", header_text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def build_draft(
    extraction: Extraction,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Собирает черновик из карты колонок. Без сети — отсюда и тестируется."""
    maps, problems = to_column_maps(payload)
    # Модель предлагает карту, код её проверяет по настоящим ячейкам.
    # Она умеет верно распознать перепутанные подписи и всё равно поставить
    # в карту не ту колонку — тогда целью становится «Формирование мотивации».
    maps, corrections = verify_maps(extraction, maps)
    built = assemble(extraction, maps)

    warnings = _clean_warnings(
        corrections
        + [w for w in (payload.get("notes") or []) if isinstance(w, str)]
        + problems
        + built["warnings"]
    )

    declared = payload.get("hours_per_year")
    total = built["total_hours"]
    if isinstance(declared, (int, float)) and declared and abs(float(declared) - total) > 0.01:
        warnings.append(
            f"Часов в год в документе заявлено {float(declared):g}, по темам получилось {total}."
        )

    return {
        "subject_name": str(payload.get("subject_name") or "").strip() or "Предмет",
        "grade": _grade(payload, extraction.header_text),
        "hours_per_week": _hours_per_week(payload, extraction.header_text),
        "hours_per_year": total,
        "instruction_language": normalize_language(payload.get("instruction_language")),
        "column_mapping": _column_mapping(maps),
        "sections": built["sections"],
        "warnings": warnings,
    }


async def map_to_schema(extraction: Extraction) -> dict[str, Any]:
    """Разбирает извлечённый документ в черновик плана."""
    if is_standard_template(extraction):
        return map_standard_template(extraction)
    payload = await detect_columns(extraction)
    return build_draft(extraction, payload)
