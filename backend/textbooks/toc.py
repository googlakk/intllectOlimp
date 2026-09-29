"""Оглавление учебника → параграфы с диапазонами страниц PDF.

Заголовки в книгах оформлены по-разному («§ 1.», «1.2.», просто заглавными),
а оглавление есть в каждой. Его разбирает модель (текст бывает «грязным»:
слипшиеся слова, две колонки), а код сверяет печатные номера страниц с PDF.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .extract import PageText

TOC_EDGE_PAGES = 12
# Маркер — отдельной короткой строкой, а не слово в тексте («содержание кислорода»).
TOC_MARKER_LINE = re.compile(r"^\W*(содержание|оглавление|мазмуну|contents|table of contents)\W*$", re.IGNORECASE)
TOC_MARKER_MAX_LINE = 40
MIN_CALIBRATION_SHARE = 0.3
OFFSET_RANGE = range(-10, 41)
TITLE_WORDS = 3

TOC_TOOL: dict[str, Any] = {
    "name": "textbook_toc",
    "description": "Оглавление учебника: разделы, главы и параграфы с печатным номером первой страницы.",
    "input_schema": {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["part", "chapter", "section"]},
                        "number": {"type": "string", "description": "Номер как в книге: «§ 3», «1.2», «Глава II»; пусто, если нет."},
                        "title": {"type": "string", "description": "Название без номера и точек-заполнителей, слова разделены пробелами."},
                        "page": {"type": "integer", "description": "Печатный номер страницы из оглавления."},
                    },
                    "required": ["kind", "title", "page"],
                },
            },
        },
        "required": ["entries"],
    },
}

TOC_PROMPT = (
    "Ниже текст страниц оглавления школьного учебника, извлечённый из PDF. Он может быть «грязным»: "
    "слипшиеся слова, точки-заполнители, соседняя колонка (словарь терминов) вперемешку. "
    "Верни только пункты оглавления по порядку. section — параграф или урок (наименьшая единица с номером "
    "страницы), chapter — глава или тема, part — раздел. Введение, предисловие, словарь и приложения — section. "
    "Разделяй слипшиеся слова. Ничего не придумывай: пункта нет в тексте — не добавляй."
)


@dataclass(frozen=True)
class TocEntry:
    kind: str
    number: str
    title: str
    page: int


@dataclass(frozen=True)
class Section:
    number: str
    title: str
    chapter: str
    printed_page: int
    pdf_from: int       # индекс первой страницы в PDF
    pdf_to: int         # индекс последней страницы (включительно)


def find_toc_pages(pages: list[PageText]) -> list[int]:
    """Оглавление — в первых или последних страницах; берём и следующую, если оно продолжается."""
    edge = [page for page in pages if page.index < TOC_EDGE_PAGES or page.index >= len(pages) - TOC_EDGE_PAGES]
    found: list[int] = []
    for page in edge:
        if any(len(line) <= TOC_MARKER_MAX_LINE and TOC_MARKER_LINE.match(line.strip())
               for line in page.text.splitlines()[:6]):
            found.append(page.index)
            following = page.index + 1
            # Оглавление может занимать несколько страниц.
            while following < len(pages) and _looks_like_toc(pages[following].text):
                found.append(following)
                following += 1
    return sorted(set(found))


def _looks_like_toc(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and sum(bool(re.search(r"\d{1,3}\s*$", line)) for line in lines) / len(lines) > 0.4


def parse_toc_entries(data: dict[str, Any]) -> list[TocEntry]:
    entries = []
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        title = " ".join(str(raw.get("title") or "").split())
        page = raw.get("page")
        if not title or not isinstance(page, int) or page < 0:
            continue
        kind = raw.get("kind") if raw.get("kind") in {"part", "chapter", "section"} else "section"
        entries.append(TocEntry(kind=kind, number=str(raw.get("number") or "").strip(), title=title, page=page))
    return entries


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold().replace("ё", "е")).split())


def _title_key(title: str) -> frozenset[str]:
    """Первые значимые слова заголовка: в тексте страницы между ними могут стоять «и», «её»."""
    words = [word for word in _normalize(title).split() if len(word) > 2]
    return frozenset(words[:TITLE_WORDS])


def calibrate_offset(entries: list[TocEntry], pages: list[PageText], toc_pages: list[int] | None = None) -> tuple[int, float]:
    """Сдвиг «индекс PDF − печатная страница» и доля пунктов, подтвердивших его.

    Страницы оглавления не учитываются: там перечислены все заголовки.
    Доля ниже MIN_CALIBRATION_SHARE — сверка ненадёжна, диапазоны нужно проверить.
    """
    skip = set(toc_pages or [])
    words = {page.index: set(_normalize(page.text).split()) for page in pages if page.index not in skip}
    sections = [entry for entry in entries if entry.kind == "section" and _title_key(entry.title)]
    votes: Counter[int] = Counter()
    for entry in sections:
        key = _title_key(entry.title)
        for offset in OFFSET_RANGE:
            if key <= words.get(entry.page + offset, set()):
                votes[offset] += 1
                break
    if not votes:
        return 0, 0.0
    offset, count = votes.most_common(1)[0]
    return offset, count / len(sections)


def build_sections(entries: list[TocEntry], page_total: int, offset: int, stop_index: int | None = None) -> list[Section]:
    """Параграф длится до начала следующего пункта оглавления.

    stop_index — первая служебная страница в конце книги (оглавление, ответы):
    последний параграф на неё не заходит.
    """
    if stop_index is not None:
        page_total = max(1, min(page_total, stop_index))
    sections: list[Section] = []
    chapter = ""
    ordered = sorted(entries, key=lambda entry: entry.page)
    starts = [entry.page + offset for entry in ordered]
    for position, entry in enumerate(ordered):
        if entry.kind != "section":
            chapter = entry.title
            continue
        start = max(0, min(starts[position], page_total - 1))
        later = [value for value in starts[position + 1:] if value > start]
        end = (later[0] - 1) if later else page_total - 1
        sections.append(Section(entry.number, entry.title, chapter, entry.page, start, max(start, end)))
    return sections
