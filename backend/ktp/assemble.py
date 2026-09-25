"""Сборка плана из таблицы по карте колонок — без модели.

Почему так. Первая версия гоняла через модель КАЖДУЮ строку КТП, требуя
вернуть её текст дословно. Это перекладывание данных из кармана в карман:
модель не решает ничего, она переписывает. Зато появляются потери — ответ
упирается в потолок, часть тем исчезает, и каждая новая порция стоит денег.

Модель нужна ровно для одного решения: какая колонка что означает. Это одно
решение на документ, а не на строку. Всё остальное — детерминированный код,
который не теряет строк и не стоит ничего.

Карта колонок (ColumnMap) описывает, где что лежит. Дальше эта сборка молча
проходит по строкам и выдаёт план.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .extract import Extraction
from topic_semantics import infer_lesson_type, ambiguous_lesson_name, join_topic_details, split_topic_title


ASSESSMENT_WORDS = (
    "контрольн", "зачёт", "зачет", "тест", "сочинени", "изложени",
    "диктант", "проверочн", "экзамен", "аттестац",
)
PROJECT_WORDS = ("проект", "исследован")

# Номер в начале названия: "1.1. Четыре операции", "12) Тема", "3 Тема".
NUMBER_PREFIX = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(?=\S)")
# Часы раздела пишут по-разному, поэтому шаблонов два:
#   "ВВЕДЕНИЕ (1 Ч.)", "ГОГОЛЬ (8 ч)"        — в скобках;
#   "Глава 1. Числа Общая продолжительность: 12 ур"  — хвостом.
SECTION_HOURS = re.compile(r"\(\s*(\d+)\s*(?:ч|час)[^)]*\)\s*$", re.IGNORECASE)
# Граница перед видом УУД: режем так, чтобы «Регулятивные:» начинало пункт.
UUD_BOUNDARY = re.compile(
    r"\s*(?=(?:Познавательные|Регулятивные|Коммуникативные|Личностные)\s*:)",
)
SECTION_HOURS_TAIL = re.compile(
    r"\s*(?:общая\s+)?продолжительность\s*:?\s*(\d+)\s*(?:ур|ч)[а-яё.]*\s*$",
    re.IGNORECASE,
)


@dataclass
class ColumnMap:
    """Что в какой колонке. Индексы — позиции в строке таблицы."""

    name: int
    hours: int | None = None
    number: int | None = None
    objectives: int | None = None
    skills: list[int] = field(default_factory=list)
    resources: int | None = None
    note: int | None = None
    header_rows: int = 1
    table_index: int = 0
    number_in_name: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnMap":
        return cls(
            name=int(data["name"]),
            hours=_opt_int(data.get("hours")),
            number=_opt_int(data.get("number")),
            objectives=_opt_int(data.get("objectives")),
            skills=[int(i) for i in (data.get("skills") or [])],
            resources=_opt_int(data.get("resources")),
            note=_opt_int(data.get("note")),
            header_rows=int(data.get("header_rows") or 1),
            table_index=int(data.get("table_index") or 0),
            number_in_name=bool(data.get("number_in_name")),
        )


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _filled(row: list[str]) -> list[str]:
    return [cell for cell in row if cell and cell.strip()]


def _hours(value: str) -> int:
    match = re.search(r"\d+", value.replace(",", "."))
    return int(match.group()) if match else 0


def _lesson_type(name: str) -> str:
    return infer_lesson_type(name)


def _split_skills(row: list[str], columns: list[int]) -> list[str]:
    """Пункты навыков: режем по маркерам списка и по видам УУД.

    В одних КТП навыки идут списком через «●», в других — сплошным текстом
    «Познавательные: … Регулятивные: … Коммуникативные: …» в одной ячейке.
    Второй случай без разрезания превращается в неразборчивый абзац.
    """
    result: list[str] = []
    for index in columns:
        text = _cell(row, index)
        if not text:
            continue
        for piece in re.split(r"\s*[•●▪]\s*|\n+", text):
            for part in UUD_BOUNDARY.split(piece):
                part = part.strip(" ;")
                if part:
                    result.append(part)
    return result


def _is_section_row(row: list[str], mapping: ColumnMap) -> bool:
    """Заголовок раздела: название есть, а номера и часов нет."""
    if not _cell(row, mapping.name):
        return False
    if len(_filled(row)) == 1:
        return True
    has_number = bool(_cell(row, mapping.number)) if mapping.number is not None else False
    has_hours = bool(_cell(row, mapping.hours)) if mapping.hours is not None else False
    return not has_number and not has_hours


def _consume_row(
    row: list[str],
    mapping: ColumnMap,
    sections: list[dict[str, Any]],
    warnings: list[str],
    current: dict[str, Any] | None,
    order: int,
) -> tuple[dict[str, Any] | None, int]:
    """Обрабатывает одну строку таблицы: заголовок раздела либо тема."""
    if not _filled(row):
        return current, order

    if _is_section_row(row, mapping):
        title = _cell(row, mapping.name) or " ".join(_filled(row))
        declared = 0
        for pattern in (SECTION_HOURS, SECTION_HOURS_TAIL):
            match = pattern.search(title)
            if match:
                declared = int(match.group(1))
                title = pattern.sub("", title)
        current = {
            "name": title.strip(" .-\u2014\u2013:"),
            "total_hours": declared,
            "topics": [],
        }
        sections.append(current)
        return current, order

    name = _cell(row, mapping.name)
    if not name:
        return current, order

    number = _cell(row, mapping.number) if mapping.number is not None else ""
    if mapping.number_in_name or not number:
        prefix = NUMBER_PREFIX.match(name)
        if prefix:
            number = number or prefix.group(1)
            name = name[prefix.end():].strip()

    if current is None:
        # Импорт требует непустое имя раздела, поэтому не оставляем его пустым:
        # иначе тема, найденная до первого заголовка, уронила бы загрузку в базу.
        current = {"name": "Без раздела", "total_hours": 0, "topics": []}
        sections.append(current)
        warnings.append(
            "Первые темы идут до первого заголовка раздела — "
            "они собраны в раздел без названия."
        )

    name, details = split_topic_title(name)
    if details:
        warnings.append(
            f"Название темы сокращено до «{name}», "
            "подпункты и практические работы перенесены в ресурсы темы."
        )
    if ambiguous_lesson_name(name):
        warnings.append(f"Проверьте тип занятия «{name}».")
    order += 1
    current["topics"].append({
        "ktp_number": number,
        "name": name,
        "hours": _hours(_cell(row, mapping.hours)) if mapping.hours is not None else 1,
        "lesson_type": _lesson_type(name),
        "review_required": ambiguous_lesson_name(name),
        "learning_objectives": _cell(row, mapping.objectives),
        "skills": _split_skills(row, mapping.skills),
        "resources": join_topic_details(details, _cell(row, mapping.resources)),
        "note": _cell(row, mapping.note),
        "confidence": "high",
        "sort_order": order,
    })
    return current, order


def assemble(
    extraction: Extraction,
    mappings: ColumnMap | list[ColumnMap],
) -> dict[str, Any]:
    """Собирает разделы и темы из таблиц. Ничего не теряет и не сочиняет.

    Карт может быть несколько — по одной на таблицу. Это не прихоть: при
    разрыве страницы в PDF вторая половина плана приходит с другим числом
    колонок, и общая карта к ней не подходит. Раздел при этом продолжается
    через границу таблиц — счётчик разделов сквозной.
    """
    if isinstance(mappings, ColumnMap):
        mappings = [mappings]
    by_table = {mapping.table_index: mapping for mapping in mappings}
    missing = [i for i in by_table if i >= len(extraction.tables)]
    if missing:
        raise ValueError(f"В документе нет таблицы №{missing[0] + 1}")

    sections: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None
    order = 0

    for table_index in sorted(by_table):
        mapping = by_table[table_index]
        rows = extraction.tables[table_index][mapping.header_rows:]
        for row in rows:
            current, order = _consume_row(
                row, mapping, sections, warnings, current, order,
            )

    for section in sections:
        counted = sum(topic["hours"] for topic in section["topics"])
        if not section["total_hours"]:
            section["total_hours"] = counted
        elif section["total_hours"] != counted and section["topics"]:
            warnings.append(
                f"Раздел «{section['name'][:40]}»: в заголовке {section['total_hours']} ч, "
                f"по темам {counted} ч."
            )

    topics = [topic for section in sections for topic in section["topics"]]
    empty_objectives = sum(1 for topic in topics if not topic["learning_objectives"])
    if empty_objectives:
        warnings.append(f"Тем без целей обучения: {empty_objectives} из {len(topics)}.")

    return {
        "sections": sections,
        "warnings": warnings,
        "total_topics": len(topics),
        "total_hours": sum(topic["hours"] for topic in topics),
    }
