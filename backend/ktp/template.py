"""Deterministic parser for the official Intellect KTP XLSX template."""

from __future__ import annotations

from topic_semantics import infer_lesson_type, ambiguous_lesson_name, join_topic_details, split_topic_title

import re
from typing import Any

from .extract import Extraction


HEADER_ALIASES = {
    "section": {"раздел", "модуль", "section", "unit", "module", "strand", "unit title"},
    "number": {"№ урока", "номер урока", "№", "lesson number", "lesson no", "lesson no.", "no", "no.", "#"},
    "name": {"тема урока", "тема", "topic", "lesson topic", "lesson title", "topic title"},
    "hours": {"часы", "количество часов", "hours", "number of hours", "teaching hours", "periods", "number of lessons"},
    "lesson_type": {"тип урока", "lesson type", "type of lesson"},
    "objectives": {"цели обучения", "ожидаемые результаты", "learning objectives", "learning objective", "learning outcomes", "objectives", "expected outcomes"},
    "objective_codes": {"коды целей", "код цели", "objective code", "objective codes", "learning objective code", "learning objective codes", "curriculum code", "curriculum codes"},
    "skills": {"навыки", "компетенции", "skills", "key skills", "competencies", "competences"},
    "resources": {"ресурсы", "учебные ресурсы", "resources", "learning resources", "teaching resources", "textbook", "textbook references"},
    "note": {"примечание", "примечания", "notes", "note", "comments", "remarks"},
}

METADATA_ALIASES = {
    "subject_name": {"предмет", "subject", "subject name"},
    "grade": {"класс", "grade", "class", "year group"},
    "stage": {"stage", "cambridge stage"},
    "instruction_language": {"язык обучения", "language", "instruction language", "language of instruction", "teaching language"},
    "hours_per_week": {"часов в неделю", "hours per week", "weekly hours", "lessons per week"},
    "hours_per_year": {"часов в год", "hours per year", "annual hours", "total hours"},
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().replace("ё", "е").split()).rstrip(":")


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
    explicit = {
        "study": "study", "new learning": "study", "new material": "study",
        "review": "review", "revision": "review", "consolidation": "review",
        "assessment": "assessment", "test": "assessment", "quiz": "assessment", "exam": "assessment",
        "reflection": "reflection", "error analysis": "reflection", "test review": "reflection",
        "project": "project", "project work": "project",
    }
    if _norm(value) in explicit:
        return explicit[_norm(value)]
    title = _norm(name)
    # Whole activity labels only: "blood test" or "projectile motion" are study topics.
    for label in sorted(explicit, key=len, reverse=True):
        if title == label or title.startswith(label + ":") or title.startswith(label + " —"):
            return explicit[label]
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
        topic_name, details = split_topic_title(topic_name)
        if details:
            warnings.append(
                f"Строка {row_number}: название темы сокращено до «{topic_name}», "
                "подпункты и практические работы перенесены в ресурсы темы."
            )
        if ambiguous_lesson_name(topic_name):
            warnings.append(f"Строка {row_number}: проверьте тип занятия «{topic_name}».")
        objective = cell(row, "objectives")
        objective_codes = cell(row, "objective_codes")
        if objective_codes:
            objective = f"{objective_codes}: {objective}" if objective else objective_codes
        section["topics"].append({
            "ktp_number": cell(row, "number"),
            "name": topic_name,
            "hours": hours,
            "lesson_type": _lesson_type(cell(row, "lesson_type"), topic_name),
            "review_required": ambiguous_lesson_name(topic_name),
            "learning_objectives": objective,
            "skills": _skills(cell(row, "skills")),
            "resources": join_topic_details(details, cell(row, "resources")),
            "note": cell(row, "note"),
            "confidence": "high" if objective else "low",
        })
        section["total_hours"] += hours

    total_hours = sum(section["total_hours"] for section in sections)
    declared_hours = _positive_int(meta.get("hours_per_year", ""))
    if declared_hours and declared_hours != total_hours:
        warnings.append(f"В шапке указано {declared_hours} час., по темам получилось {total_hours} час.")

    language = _norm(meta.get("instruction_language"))
    english_headers = _norm(table[header_index][columns["objectives"]]) in {
        "learning objectives", "learning objective", "learning outcomes", "objectives", "expected outcomes",
    }
    languages = {"ru": "ru", "русский": "ru", "russian": "ru", "ky": "ky", "кыргызский": "ky",
                 "кыргызча": "ky", "kyrgyz": "ky", "en": "en", "английский": "en", "english": "en", "англисче": "en"}
    instruction_language = languages.get(language, "en" if english_headers else "ru")
    if language not in languages:
        warnings.append("Язык обучения не указан или не распознан; выбран по заголовкам таблицы. Проверьте поле «Язык».")
    if meta.get("stage"):
        warnings.append(f"Cambridge Stage: {meta['stage']}. Проверьте класс школы: Stage не переводится в класс автоматически.")
    if not _positive_int(meta.get("grade", "")):
        warnings.append("Укажите класс школы в поле «Класс» перед сохранением КТП.")
    return {
        "subject_name": meta.get("subject_name") or "Предмет",
        "grade": _positive_int(meta.get("grade", "")),
        "hours_per_week": _positive_float(meta.get("hours_per_week", ""), 1.0),
        "hours_per_year": total_hours,
        "instruction_language": instruction_language,
        "column_mapping": {f"колонка {index}": field for field, index in columns.items()},
        "sections": sections,
        "warnings": warnings,
    }
