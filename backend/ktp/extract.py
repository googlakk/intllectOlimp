"""Детерминированное извлечение таблиц КТП из docx и pdf.

Здесь нет ИИ. Задача модуля — достать из файла таблицы ровно такими, какие
они есть, и заголовочный текст документа. Сопоставление колонок со схемой
делает mapper.py; разделение нужно, чтобы модель работала с реальным
текстом документа и не могла придумать тему, которой в нём нет.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field


@dataclass
class Extraction:
    source_kind: str                      # "docx" | "pdf"
    header_text: str                      # заголовок документа: предмет, класс, часы
    tables: list[list[list[str]]] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return sum(len(t) for t in self.tables)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _collapse_repeats(row: list[str]) -> list[str]:
    """Объединённые ячейки python-docx отдаёт повторами. Схлопываем подряд идущие."""
    out: list[str] = []
    for cell in row:
        if out and cell and cell == out[-1]:
            out.append("")
        else:
            out.append(cell)
    return out


def extract_docx(data: bytes) -> Extraction:
    import docx

    document = docx.Document(io.BytesIO(data))
    header_lines: list[str] = []
    for paragraph in document.paragraphs:
        text = _clean(paragraph.text)
        if text:
            header_lines.append(text)
        if len(header_lines) >= 15:
            break

    tables: list[list[list[str]]] = []
    for table in document.tables:
        # Схлопываем повторы ТОЛЬКО в шапке (первые 3 строки). В строках данных
        # одинаковые соседние значения законны — например, две темы по 2 часа
        # подряд, — и их затирание молча испортило бы часы.
        rows = []
        for index, row in enumerate(table.rows):
            cells = [_clean(c.text) for c in row.cells]
            rows.append(_collapse_repeats(cells) if index < 3 else cells)
        rows = [r for r in rows if any(r)]
        if len(rows) >= 3:                # служебные таблицы на 1-2 строки пропускаем
            tables.append(rows)
    return Extraction("docx", "\n".join(header_lines), tables)


def extract_pdf(data: bytes) -> Extraction:
    import pdfplumber

    header_lines: list[str] = []
    tables: list[list[list[str]]] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            if index < 2:
                text = _clean(page.extract_text() or "")
                if text:
                    header_lines.append(text)
            for raw in page.extract_tables():
                rows = [[_clean(c) for c in row] for row in raw]
                rows = [r for r in rows if any(r)]
                if len(rows) >= 2:
                    tables.append(rows)
    merged = [_join_continuation_rows(t) for t in _merge_page_splits(tables)]
    return Extraction("pdf", "\n".join(header_lines), merged)


def _merge_page_splits(tables: list[list[list[str]]]) -> list[list[list[str]]]:
    """PDF режет одну таблицу по страницам. Соседние куски с одинаковым числом
    колонок — это продолжение, а не новая таблица. Склеиваем их, иначе ячейка,
    разорванная границей страницы, приходит моделью как отдельная строка без темы.
    """
    merged: list[list[list[str]]] = []
    for table in tables:
        width = len(table[0]) if table else 0
        if merged and width and len(merged[-1][0]) == width:
            merged[-1].extend(table)
        else:
            merged.append(list(table))
    return merged


def _join_continuation_rows(table: list[list[str]], header_rows: int = 3) -> list[list[str]]:
    """Ячейка, разорванная границей страницы, приходит отдельной строкой без
    номера и названия темы. Приклеиваем её к предыдущей строке по колонкам —
    иначе модели приходится сшивать текст догадками, и уверенность падает.
    """
    out: list[list[str]] = []
    for index, row in enumerate(table):
        is_continuation = (
            index >= header_rows
            and out
            and not any(c.strip() for c in row[:2])      # нет номера и названия
            and any(c.strip() for c in row[2:])          # но текст есть
        )
        if is_continuation:
            previous = out[-1]
            for col, cell in enumerate(row):
                if cell.strip() and col < len(previous):
                    previous[col] = (previous[col] + " " + cell).strip()
        else:
            out.append(list(row))
    return out


def extract(data: bytes, filename: str) -> Extraction:
    name = filename.lower()
    if name.endswith(".docx"):
        return extract_docx(data)
    if name.endswith(".pdf"):
        return extract_pdf(data)
    raise ValueError(f"Неподдерживаемый формат файла: {filename}. Нужен .docx или .pdf")
