"""Определение карты колонок — единственное место, где нужна модель.

Модель получает шапку документа и по нескольку строк-образцов из каждой
таблицы, а возвращает десяток чисел: где название темы, где часы, где цели.
Содержимое КТП через модель не проходит вовсе — его разбирает код.

Почему образцы, а не заголовки колонок: в КТП подписи врут. В плане по
литературе колонка подписана «Личностные», а внутри лежат предметные
результаты («Научиться определять жанровое своеобразие»). Решение можно
принять только по содержимому.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .assemble import ColumnMap
from .extract import Extraction

MAX_TOKENS = 4000          # ответ — только числа, объём не растёт с размером КТП
SAMPLE_ROWS = 6            # столько строк каждой таблицы показываем модели
SAMPLE_CELL = 160          # и столько знаков от каждой ячейки

TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "table_index": {"type": "integer", "description": "Номер таблицы, начиная с 0."},
        "is_plan": {
            "type": "boolean",
            "description": "Это таблица самого плана. Перечень оборудования, "
                           "список литературы, методические материалы — false.",
        },
        "header_rows": {
            "type": "integer",
            "description": "Сколько первых строк занимает шапка таблицы. "
                           "У продолжения таблицы с прошлой страницы обычно 0.",
        },
        "name": {"type": "integer", "description": "Колонка с названием темы или раздела."},
        "hours": {"type": "integer", "description": "Колонка с количеством часов. -1, если её нет."},
        "number": {"type": "integer", "description": "Колонка с номером темы. -1, если её нет."},
        "number_in_name": {
            "type": "boolean",
            "description": "Номер стоит в начале названия темы («1.1. Четыре операции»).",
        },
        "objectives": {
            "type": "integer",
            "description": "Колонка с целями обучения или предметными результатами. -1, если нет.",
        },
        "skills": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Колонки с умениями, навыками, УУД. Пустой список, если нет.",
        },
        "resources": {"type": "integer", "description": "Колонка с учебником, ресурсами, д/з. -1, если нет."},
        "note": {"type": "integer", "description": "Колонка с формой контроля или примечанием. -1, если нет."},
    },
    "required": ["table_index", "is_plan", "header_rows", "name", "hours", "number",
                 "number_in_name", "objectives", "skills", "resources", "note"],
}

COLUMNS_TOOL = {
    "name": "submit_columns",
    "description": "Передать карту колонок и общие сведения о плане.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_name": {"type": "string"},
            "grade": {"type": "integer"},
            "hours_per_week": {"type": "number"},
            "hours_per_year": {"type": "integer", "description": "0, если в документе не указано."},
            "instruction_language": {"type": "string", "enum": ["ru", "ky"]},
            "tables": {"type": "array", "items": TABLE_SCHEMA},
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Замечания: перепутанные подписи колонок, "
                               "расхождения в шапке документа.",
            },
        },
        "required": ["subject_name", "grade", "hours_per_week", "hours_per_year",
                     "instruction_language", "tables", "notes"],
    },
}

SYSTEM_PROMPT = """
Ты определяешь СТРУКТУРУ календарно-тематического плана: какая колонка
таблицы что означает. Содержимое плана разбирать не надо — его извлечёт код.

Тебе показывают шапку документа и по нескольку строк из каждой таблицы.
Ячейки пронумерованы: [0] [1] [2] — это индексы колонок. Верни индексы.

Главное правило: колонку определяй ПО СОДЕРЖИМОМУ ячеек, а не по подписи.
В КТП подписи часто перепутаны. Пример из реального плана по литературе:
колонка [5] подписана "Личностные", а внутри "Научиться определять жанровое
своеобразие преданий" — это предметный результат, то есть ЦЕЛЬ ОБУЧЕНИЯ.
Колонка [7] подписана "Предметные", а внутри "Формирование мотивации к
обучению" — это личностный результат, ему место в note.
Правильный ответ для такого плана: objectives = 5, note = 7.

ЗАМЕТИЛ ПОДМЕНУ — СТАВЬ В КАРТУ ИНДЕКС ПО СОДЕРЖИМОМУ. Самая частая ошибка:
верно описать перепутанные подписи в notes, а в objectives всё равно указать
колонку с нужной ПОДПИСЬЮ. Так делать нельзя: код берёт колонку по индексу и
подписей не читает. Если пишешь в notes, что подписи перепутаны, — индекс в
objectives обязан указывать на колонку с целями, а не с тем заголовком.

Проверь себя перед ответом: открой ячейку той колонки, которую ставишь в
objectives. Она начинается со слова "Научиться", "Уметь", "Оценивать",
"Понимать"? Тогда верно. Начинается с "Формирование" или "Воспитание"?
Это личностный результат — значит, ты выбрал не ту колонку.

Каждое расхождение подписи и содержимого опиши в notes.

Как читать:
- name: где лежит название темы («Русская литература и история») и заголовок
  раздела («ВВЕДЕНИЕ (1 Ч.)»). Обычно это одна и та же колонка.
- hours: где число уроков. Если колонки нет — верни -1.
- number: отдельная колонка с номером («1», «29»). Если номера нет отдельной
  колонкой, но он стоит в начале названия («1.1. Четыре операции»), верни -1
  и поставь number_in_name true.
- objectives: цели обучения или предметные результаты.
- skills: умения, навыки, УУД. Их может быть несколько колонок — верни все.
- resources: учебник, страницы, ресурсы, домашнее задание.
- note: форма контроля, личностные результаты, примечания.
- header_rows: сколько первых строк — шапка. Если таблица начинается сразу с
  данных (продолжение с прошлой страницы) — 0.
- is_plan: false для служебных таблиц (перечень оборудования, список
  литературы, методическое обеспечение).

Таблицы могут иметь РАЗНОЕ число колонок: при разрыве страницы в PDF часть
пустых колонок пропадает. Поэтому карту давай для каждой таблицы отдельно,
глядя на её собственные строки.

Результат передай вызовом submit_columns. Ничего не пиши текстом.
""".strip()


def _sample(extraction: Extraction) -> str:
    """Шапка и несколько строк каждой таблицы с пронумерованными ячейками."""
    blocks: list[str] = []
    for index, table in enumerate(extraction.tables):
        lines = [f"=== Таблица {index} — всего строк {len(table)} ==="]
        for row in table[:SAMPLE_ROWS]:
            cells = " ".join(
                f"[{position}] {(cell or '').strip()[:SAMPLE_CELL]}"
                for position, cell in enumerate(row)
                if (cell or "").strip()
            )
            lines.append(cells or "(пустая строка)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _index(value: Any) -> int | None:
    """-1, None и мусор означают «колонки нет»."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def to_column_maps(payload: dict[str, Any]) -> tuple[list[ColumnMap], list[str]]:
    """Карты колонок из ответа модели. Служебные таблицы отбрасываются."""
    maps: list[ColumnMap] = []
    problems: list[str] = []
    for table in payload.get("tables") or []:
        if not isinstance(table, dict):
            problems.append("Элемент tables пришёл не объектом — пропущен.")
            continue
        if not table.get("is_plan"):
            continue
        name = _index(table.get("name"))
        if name is None:
            problems.append(
                f"Таблица {table.get('table_index')}: не указана колонка с названием — пропущена."
            )
            continue
        maps.append(ColumnMap(
            name=name,
            hours=_index(table.get("hours")),
            number=_index(table.get("number")),
            objectives=_index(table.get("objectives")),
            skills=[i for i in (_index(v) for v in (table.get("skills") or [])) if i is not None],
            resources=_index(table.get("resources")),
            note=_index(table.get("note")),
            header_rows=max(0, _index(table.get("header_rows")) or 0),
            table_index=_index(table.get("table_index")) or 0,
            number_in_name=bool(table.get("number_in_name")),
        ))
    if not maps:
        raise ValueError("Модель не нашла в документе ни одной таблицы плана")
    return maps, problems


async def detect_columns(extraction: Extraction) -> dict[str, Any]:
    """Один вызов модели на весь документ. Возвращает сырой ответ.

    Идёт через шлюз: какая модель отвечает — решает настройка, а не этот файл.
    Задача дешёвая (в ответе десяток чисел), поэтому её можно направить на
    модель попроще, не трогая генерацию урока.
    """
    from llm import TASK_KTP_COLUMNS, call_tool

    user_prompt = (
        f"Заголовок документа:\n{extraction.header_text[:2000]}\n\n"
        f"Строки-образцы:\n{_sample(extraction)}\n\n"
        "Определи карту колонок и вызови submit_columns."
    )
    result = await call_tool(
        TASK_KTP_COLUMNS,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        tool=COLUMNS_TOOL,
        max_tokens=MAX_TOKENS,
    )
    if result.ok:
        return result.data

    dump = Path(tempfile.gettempdir()) / "ktp-columns-raw.txt"
    try:
        dump.write_text(
            f"provider={result.provider} model={result.model} "
            f"stop={result.stop_reason}\n\n{result.text}",
            encoding="utf-8",
        )
        where = f" Сырой ответ: {dump}"
    except OSError:
        where = ""
    if result.truncated:
        raise RuntimeError(
            f"Карта колонок не поместилась в ответ ({MAX_TOKENS} токенов)."
            f" Модель: {result.model}.{where}"
        )
    raise RuntimeError(
        f"Модель {result.model} не вернула карту колонок.{where}"
    )
