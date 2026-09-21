"""Проверка карты колонок по содержимому — код не верит модели на слово.

Зачем. Модель умеет правильно РАСПОЗНАТЬ, что колонки в КТП подписаны неверно,
и при этом поставить в карту ту самую неверную колонку. Реальный случай на
плане по литературе: в предупреждениях модель написала «колонка 5 подписана
"Личностные", но содержит цели обучения», а в карту поставила objectives = 7.
В итоге во всех 61 теме целью оказалось «Формирование мотивации к обучению».

Проверять это легко: цель обучения и личностный результат различаются на слух
с первого слова. «Научиться определять жанровое своеобразие» — цель.
«Формирование устойчивой мотивации» — личностный результат. Поэтому карта
проверяется по настоящим ячейкам, и при явной ошибке колонки меняются местами.

Правило: код исправляет только очевидное — когда назначенная колонка не похожа
на цели совсем, а другая похожа явно. В спорных случаях ничего не трогаем и
пишем предупреждение: тихая самодеятельность хуже честного сомнения.
"""

from __future__ import annotations

import re
from typing import Any

from .assemble import ColumnMap
from .extract import Extraction

# Цель обучения почти всегда начинается с того, что ученик будет делать.
OBJECTIVE_START = re.compile(
    r"^\s*(?:научит[ьс]|уме[тн]|зна[тн]|понима|поня[тл]|оценива|определ|использ|"
    r"примен|выявля|владе[тн]|освои|изуча|анализир|сравнива|различа|объясня|"
    r"описыва|вычисля|склад|вычита|умнож|дели|стро|реша|распозна|проектир|"
    r"находи|формулир|характериз|интерпретир|обобща|устанавлив|помни)",
    re.IGNORECASE,
)
# Личностный результат — это про воспитание, а не про умение.
PERSONAL_START = re.compile(
    r"^\s*(?:формирован|воспитан|развити[ея]\s+(?:мотивац|интерес|чувств)|"
    r"осознан|принят|готовност|становлен)",
    re.IGNORECASE,
)
# Метапредметные УУД подписаны стандартно и узнаются надёжно.
UUD_MARKER = re.compile(
    r"\b(?:познавательные|регулятивные|коммуникативные)\s*:",
    re.IGNORECASE,
)

SAMPLE_LIMIT = 40          # столько строк достаточно, чтобы увидеть характер
MIN_SAMPLES = 5            # меньше — судить не берёмся
DECISIVE = 0.6             # доля, при которой характер колонки считается ясным


def _column_values(rows: list[list[str]], index: int) -> list[str]:
    values: list[str] = []
    for row in rows:
        if index < len(row):
            cell = (row[index] or "").strip()
            if len(cell) >= 15:
                values.append(cell)
        if len(values) >= SAMPLE_LIMIT:
            break
    return values


def classify_column(values: list[str]) -> dict[str, float]:
    """Доли строк каждого характера. Пустая выборка — все нули."""
    if not values:
        return {"objective": 0.0, "personal": 0.0, "uud": 0.0, "samples": 0}
    total = len(values)
    return {
        "objective": sum(1 for v in values if OBJECTIVE_START.match(v)) / total,
        "personal": sum(1 for v in values if PERSONAL_START.match(v)) / total,
        "uud": sum(1 for v in values if UUD_MARKER.search(v)) / total,
        "samples": total,
    }


def _data_rows(extraction: Extraction, mapping: ColumnMap) -> list[list[str]]:
    if mapping.table_index >= len(extraction.tables):
        return []
    return extraction.tables[mapping.table_index][mapping.header_rows:]


def verify_objectives_column(
    extraction: Extraction,
    mapping: ColumnMap,
) -> tuple[ColumnMap, list[str]]:
    """Сверяет колонку целей с тем, что в ней на самом деле написано."""
    rows = _data_rows(extraction, mapping)
    if not rows:
        return mapping, []

    warnings: list[str] = []
    busy = {mapping.name, mapping.number, mapping.hours}
    width = max((len(row) for row in rows), default=0)
    profiles = {
        index: classify_column(_column_values(rows, index))
        for index in range(width)
        if index not in busy
    }

    current = profiles.get(mapping.objectives) if mapping.objectives is not None else None
    if current is not None and current["samples"] < MIN_SAMPLES:
        return mapping, warnings

    # Назначенная колонка похожа на цели — вмешиваться не нужно.
    if current is not None and current["objective"] >= DECISIVE:
        return mapping, warnings

    candidates = [
        (index, profile) for index, profile in profiles.items()
        if profile["samples"] >= MIN_SAMPLES
        and profile["objective"] >= DECISIVE
        and profile["uud"] < 0.3
        and index != mapping.objectives
    ]
    if not candidates:
        if current is not None and current["personal"] >= DECISIVE:
            warnings.append(
                f"Колонка {mapping.objectives} назначена целями обучения, но содержит "
                "личностные результаты («Формирование…»). Подходящей замены в таблице "
                "не нашлось — проверьте цели вручную."
            )
        return mapping, warnings

    best_index, best = max(candidates, key=lambda item: item[1]["objective"])
    was = mapping.objectives
    reason = (
        f"содержит личностные результаты ({current['personal']:.0%} строк)"
        if current is not None and current["personal"] >= DECISIVE
        else "не похожа на цели обучения"
    )
    warnings.append(
        f"Карта колонок исправлена по содержимому: цели обучения взяты из колонки "
        f"{best_index} ({best['objective']:.0%} строк начинаются с «Научиться», "
        f"«Уметь», «Оценивать»…), а не из колонки {was}, которая {reason}."
    )

    # Новая колонка целей не должна остаться заодно и в навыках.
    skills = [index for index in mapping.skills if index != best_index]
    changes: dict[str, Any] = {"objectives": best_index, "skills": skills}

    # Прежняя колонка не выбрасывается: личностные результаты — это note.
    # Занимаем note, только если он свободен, иначе данные не теряем — в skills.
    if was is not None and was != best_index:
        if mapping.note is None:
            changes["note"] = was
        elif was not in skills and was != mapping.note:
            changes["skills"] = skills + [was]

    return _replace(mapping, **changes), warnings


def _replace(mapping: ColumnMap, **changes: Any) -> ColumnMap:
    data = {
        "name": mapping.name, "hours": mapping.hours, "number": mapping.number,
        "objectives": mapping.objectives, "skills": list(mapping.skills),
        "resources": mapping.resources, "note": mapping.note,
        "header_rows": mapping.header_rows, "table_index": mapping.table_index,
        "number_in_name": mapping.number_in_name,
    }
    data.update(changes)
    return ColumnMap(**data)


def verify_maps(
    extraction: Extraction,
    maps: list[ColumnMap],
) -> tuple[list[ColumnMap], list[str]]:
    """Проверяет все карты. Возвращает исправленные и список правок."""
    checked: list[ColumnMap] = []
    warnings: list[str] = []
    for mapping in maps:
        fixed, problems = verify_objectives_column(extraction, mapping)
        checked.append(fixed)
        warnings.extend(problems)
    return checked, warnings
