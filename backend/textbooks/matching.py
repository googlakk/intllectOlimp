"""Подбор параграфов учебника к теме КТП. Чистые функции, без базы и модели.

От надёжного к менее надёжному:
1. ссылка в КТП («§ 5», «п. 1.2», «стр. 31–35») — прямая связь;
2. совпадение по смыслу: основы слов из названия и ЦЕЛЕЙ темы сравниваются
   с названием и текстом параграфа («Масса и плотность» → «§12. Плотность вещества»).
Подтверждает связь учитель; автоматически — только ссылка из КТП.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STEM = 5
MIN_WORD = 4
TEXT_HEAD = 4000
SUGGEST_MIN_SCORE = 0.25
SUGGEST_RELATIVE = 0.6
SUGGEST_LIMIT = 3

# Слова, которые есть почти в любой теме и ничего не говорят о параграфе.
_STOP = frozenset(
    stem[:STEM] for stem in (
        "урок", "тема", "темы", "понятие", "понятия", "основные", "основы", "виды", "роль", "значение", "общая",
        "характеристика", "изучение", "знакомство", "повторение", "обобщение", "контрольная", "работа", "практическая",
        "лабораторная", "решение", "задач", "задачи", "учащиеся", "ученики", "умеют", "знают", "научатся", "могут",
        "определять", "объяснять", "описывать", "называть", "приводить", "примеры", "использовать", "применять",
        "понимать", "различать", "сравнивать", "формирование", "развитие", "является", "между", "также", "которые",
    )
)
# Только отдельные слова: «класс 7», «тип. 3», «с 1991 года» — не ссылки.
_SECTION_REF = re.compile(r"(?:§|(?<![а-яёa-z])параграф|(?<![а-яёa-z])п\.)\s*(\d+(?:\.\d+)?)(?![\d.])", re.IGNORECASE)
_PAGE_REF = re.compile(r"(?<![а-яёa-z])(?:стр\.?|с\.)\s*(\d{1,3})(?!\d)(?:\s*[-–—]\s*(\d{1,3})(?!\d))?", re.IGNORECASE)


@dataclass(frozen=True)
class SectionInfo:
    id: int
    number: str
    title: str
    printed_from: int | None
    printed_to: int | None
    text: str = ""


@dataclass(frozen=True)
class Suggestion:
    section_id: int
    score: float
    source: str            # ktp | match


def stems(text: str) -> set[str]:
    words = re.findall(r"[а-яёa-z]+", text.casefold().replace("ё", "е"))
    return {word[:STEM] for word in words if len(word) >= MIN_WORD and word[:STEM] not in _STOP}


def _number_key(number: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", number or "")
    return match.group(0) if match else ""


def ktp_references(sections: list[SectionInfo], reference_text: str) -> list[int]:
    """Параграфы, на которые прямо ссылается КТП: по номеру или по страницам."""
    found: list[int] = []
    numbers = [_number_key(section.number) for section in sections]
    # Нумерация может начинаться заново в каждой части — повторяющийся номер неоднозначен.
    by_number = {key: section.id for key, section in zip(numbers, sections) if key and numbers.count(key) == 1}
    for match in _SECTION_REF.finditer(reference_text or ""):
        section_id = by_number.get(match.group(1))
        if section_id is not None and section_id not in found:
            found.append(section_id)
    for match in _PAGE_REF.finditer(reference_text or ""):
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        for section in sections:
            if section.printed_from is None or section.printed_to is None:
                continue
            if section.printed_from <= last and first <= section.printed_to and section.id not in found:
                found.append(section.id)
    return found


def match_score(topic_stems: set[str], section: SectionInfo) -> float:
    """Доля слов темы в названии параграфа важнее, чем в его тексте."""
    if not topic_stems:
        return 0.0
    title = stems(section.title)
    text = stems(section.text[:TEXT_HEAD])
    # Короткий заголовок («Сила») не должен давать полное совпадение по одному слову.
    title_part = len(topic_stems & title) / max(2, min(len(title), len(topic_stems)))
    text_part = len(topic_stems & text) / len(topic_stems)
    return round(0.6 * title_part + 0.4 * text_part, 3)


def suggest_sections(topic_name: str, objectives: str, reference_text: str, sections: list[SectionInfo]) -> list[Suggestion]:
    direct = ktp_references(sections, reference_text)
    if direct:
        return [Suggestion(section_id, 1.0, "ktp") for section_id in direct]
    topic = stems(f"{topic_name} {objectives}")
    scored = sorted(
        ((match_score(topic, section), section.id) for section in sections),
        reverse=True,
    )
    if not scored or scored[0][0] < SUGGEST_MIN_SCORE:
        return []
    best = scored[0][0]
    return [
        Suggestion(section_id, score, "match")
        for score, section_id in scored[:SUGGEST_LIMIT]
        if score >= SUGGEST_MIN_SCORE and score >= best * SUGGEST_RELATIVE
    ]

