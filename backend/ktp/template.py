"""Deterministic parser for the official Intellect KTP XLSX template."""

from __future__ import annotations

from topic_semantics import infer_lesson_type, ambiguous_lesson_name

import re
from typing import Any

from .extract import Extraction


HEADER_ALIASES = {
    "section": {"раздел", "модуль"},
    "number": {"№ урока", "номер урока", "№"},
    "name": {"тема урока", "тема"},
    "hours": {"часы", "количество часов"},
    "lesson_type": {"тип урока"},
    "objectives": {"цели обучения", "ожидаемые результаты"},
    "skills": {"навыки", "компетенции"},
    "resources": {"ресурсы", "учебные ресурсы"},
    "note": {"примечание", "примечания"},
}

METADATA_ALIASES = {
    "subject_name": {"предмет"},
    "grade": {"класс"},
    "instruction_language": {"язык обучения"},
    "hours_per_week": {"часов в неделю"},
    "hours_per_year": {"часов в год"},
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().replace("ё", "е").split())


def _column_map(row: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, value in enumerate(row):
        normalized = _norm(value)
        for field, aliases in HEADER_ALIASES.items():
            if normalized in aliases:
                result[field] = index
                break
    return result


def _find_template_table(extraction: Extraction) -> tuple[list[list[str]], int, dict[str, int]] | None:
    for table in extraction.tables:
        for row_index, row in enumerate(table[:30]):
            columns = _column_map(row)
            if {"section", "name", "hours", "objectives"}.issubset(columns):
                return table, row_index, columns
    return None


def is_standard_template(extraction: Extraction) -> bool:
    return extraction.source_kind == "xlsx" and _find_template_table(extraction) is not None


def _metadata(table: list[list[str]], header_index: int) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in table[:header_index]:
        for index, cell in enumerate(row):
            label = _norm(cell)
            for field, aliases in METADATA_ALIASES.items():
                if label in aliases:
                    candidate = row[index + 1] if index + 1 < len(row) else ""
                    values[field] = str(candidate or "").strip()
    return values


def _positive_int(value: str, fallback: int = 0) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else fallback


def _positive_float(value: str, fallback: float = 0) -> float:
    match = re.search(r"\d+(?:[.,]\d+)?", str(value or ""))
    return float(match.group().replace(",", ".")) if match else fallback


def _lesson_type(value: str, name: str) -> str:
    return infer_lesson_type(f"{value} {name}")


def _skills(value: str) -> list[str]:
    return [part.strip(" •●▪;-") for part in re.split(r"[\n;]+", value or "") if part.strip(" •●▪;-")]


def map_standard_template(extraction: Extraction) -> dict[str, Any]:
    found = _find_template_table(extraction)
    if found is None:
        raise ValueError("В Excel-файле не найдена таблица шаблона КТП")
    table, header_index, columns = found
    meta = _metadata(table, header_index)

    sections: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    current_section = ""
    warnings: list[str] = []

    def cell(row: list[str], field: str) -> str:
        index = columns.get(field)
        return str(row[index] or "").strip() if index is not None and index < len(row) else ""

    for row_number, row in enumerate(table[header_index + 1:], start=header_index + 2):
        if not any(str(value or "").strip() for value in row):
            continue
        section_name = cell(row, "section") or current_section
        topic_name = cell(row, "name")
        if not topic_name:
            warnings.append(f"Строка {row_number}: нет темы урока, строка пропущена.")
            continue
        if not section_name:
            section_name = "Без раздела"
            warnings.append(f"Строка {row_number}: не указан раздел.")
        current_section = section_name
        section = by_name.get(section_name)
        if section is None:
            section = {"name": section_name, "total_hours": 0, "topics": []}
            by_name[section_name] = section
            sections.append(section)

        hours = _positive_int(cell(row, "hours"), 1)
        if hours <= 0:
            hours = 1
            warnings.append(f"Строка {row_number}: часы заменены на 1.")
        if ambiguous_lesson_name(topic_name):
            warnings.append(f"Строка {row_number}: проверьте тип занятия «{topic_name}».")
        objective = cell(row, "objectives")
        section["topics"].append({
            "ktp_number": cell(row, "number"),
            "name": topic_name,
            "hours": hours,
            "lesson_type": _lesson_type(cell(row, "lesson_type"), topic_name),
            "review_required": ambiguous_lesson_name(topic_name),
            "learning_objectives": objective,
            "skills": _skills(cell(row, "skills")),
            "resources": cell(row, "resources"),
            "note": cell(row, "note"),
            "confidence": "high" if objective else "low",
        })
        section["total_hours"] += hours

    total_hours = sum(section["total_hours"] for section in sections)
    declared_hours = _positive_int(meta.get("hours_per_year", ""))
    if declared_hours and declared_hours != total_hours:
        warnings.append(f"В шапке указано {declared_hours} час., по темам получилось {total_hours} час.")

    language = _norm(meta.get("instruction_language"))
    return {
        "subject_name": meta.get("subject_name") or "Предмет",
        "grade": _positive_int(meta.get("grade", "")),
        "hours_per_week": _positive_float(meta.get("hours_per_week", ""), 1.0),
        "hours_per_year": total_hours,
        "instruction_language": "ky" if language in {"ky", "кыргызский", "кыргызча"} else "ru",
        "column_mapping": {f"колонка {index}": field for field, index in columns.items()},
        "sections": sections,
        "warnings": warnings,
    }
