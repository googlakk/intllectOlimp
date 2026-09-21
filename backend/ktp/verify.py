"""Сверка черновика КТП с исходным файлом — без обращения к модели.

Смысл: не верить разбору на слово. Скрипт заново извлекает таблицы из docx/pdf
детерминированно и сравнивает их с тем, что вернула модель.

Проверки намеренно не зависят от формата таблицы — в разных КТП номер урока
то отдельной колонкой, то в начале названия, колонки называются по-разному.
Поэтому сверяется не «колонка 3 против колонки 3», а:

  1. дословность — каждая строка черновика (название, цели, навыки, ресурсы,
     заголовок раздела) обязана присутствовать в исходнике буква в букву;
  2. полнота — каждая строка исходника, похожая на урок, должна быть найдена
     в черновике;
  3. отсутствие дублей — одна строка исходника не может попасть в две темы;
  4. часы — сумма по темам против числа, заявленного в шапке документа.

Запуск:  python -m ktp.verify "путь/к/ктп.docx" "путь/к/черновика.json"
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .extract import extract


HEADER_WORDS = (
    "№", "п/п", "п.п", "раздел", "тема", "урок", "кол-во", "количество", "час",
    "дата", "план", "факт", "цел", "результат", "ууд", "ресурс", "навык", "умени",
    "контрол", "д/з", "домашн", "примечан", "личностн", "метапредметн", "предметн",
)


def _norm(value: str) -> str:
    """Нормализация для сравнения: регистр, ё, кавычки, тире, пробелы."""
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[«»“”„]", '"', value)
    value = re.sub(r"[’‘`]", "'", value)
    value = re.sub(r"[–—−]", "-", value)
    value = re.sub(r"[•●▪·]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n.;:,-")


def _squeeze(value: str) -> str:
    """Та же нормализация, но без пробелов вовсе.

    В PDF слова рвутся переносом («последователь ности»), и извлечение
    оставляет лишний пробел. Для сверки это не расхождение по смыслу,
    поэтому сравнение вторым заходом идёт без пробелов.
    """
    return re.sub(r"\s+", "", _norm(value))


def _cells(row: list[str]) -> list[str]:
    return [cell for cell in row if cell and cell.strip()]


def _is_table_header(row: list[str]) -> bool:
    """Шапка таблицы: почти каждая заполненная ячейка — служебное слово."""
    filled = _cells(row)
    if len(filled) < 2:
        return False
    matched = sum(
        1 for cell in filled
        if any(word in cell.casefold() for word in HEADER_WORDS) and len(cell) < 60
    )
    return matched >= max(2, len(filled) - 1)


def _row_text(row: list[str]) -> str:
    return _norm(" ".join(_cells(row)))


def _declared_hours(header_text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*час", header_text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _draft_topics(draft: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    pairs: list[tuple[str, dict[str, Any]]] = []
    for section in draft.get("sections") or []:
        name = str(section.get("name") or "")
        for topic in section.get("topics") or []:
            if isinstance(topic, dict):
                pairs.append((name, topic))
    return pairs


def verify(source_path: Path, draft_path: Path) -> dict[str, Any]:
    extraction = extract(source_path.read_bytes(), source_path.name)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    topics = _draft_topics(draft)
    sections = [str(s.get("name") or "") for s in (draft.get("sections") or [])]

    problems: list[str] = []
    notes: list[str] = []

    # --- какие таблицы вообще относятся к плану ---
    # В документах рядом с КТП лежат служебные таблицы (перечень оборудования,
    # список литературы). Считаем таблицу частью плана, если хотя бы одна тема
    # черновика находится в её строках.
    topic_keys = [_squeeze(str(topic.get("name") or "")) for _, topic in topics]
    topic_keys = [key for key in topic_keys if len(key) >= 8]
    plan_tables: list[list[list[str]]] = []
    skipped_tables = 0
    for table in extraction.tables:
        blob = _squeeze(" ".join(cell for row in table for cell in row))
        if any(key in blob for key in topic_keys):
            plan_tables.append(table)
        else:
            skipped_tables += 1
    if not plan_tables:
        plan_tables = extraction.tables
        skipped_tables = 0
    if skipped_tables:
        notes.append(f"служебных таблиц пропущено при сверке: {skipped_tables}")

    # --- разбор исходника на строки, без предположений о колонках ---
    lesson_rows: list[tuple[int, list[str]]] = []   # >= 2 заполненных ячеек
    heading_rows: list[tuple[int, list[str]]] = []  # ровно 1 заполненная ячейка
    index = 0
    for table in plan_tables:
        for row in table:
            index += 1
            filled = _cells(row)
            if not filled or _is_table_header(row):
                continue
            if len(filled) == 1:
                heading_rows.append((index, row))
            else:
                lesson_rows.append((index, row))

    corpus = " ␟ ".join(
        _norm(cell)
        for table in extraction.tables for row in table for cell in row
        if cell and cell.strip()
    )
    corpus_squeezed = _squeeze(
        " ".join(cell for table in extraction.tables for row in table for cell in row)
    )

    # --- 0. явные признаки испорченного разбора ---
    breakage = [w for w in (draft.get("warnings") or [])
                if isinstance(w, str) and w.lower().startswith("разбор ")]
    if breakage:
        problems.append(
            f"разбор сломался на части документа ({len(breakage)}): " + "; ".join(breakage[:4])
        )
    junk_sections = [name for name in sections if len(name.strip()) <= 2]
    if junk_sections:
        problems.append(
            f"разделы с названием в один-два символа ({len(junk_sections)}) — "
            "признак того, что список разделов пришёл строкой и был раскрошен посимвольно"
        )
    empty_sections = [name for name, section in
                      zip(sections, draft.get("sections") or [])
                      if isinstance(section, dict) and not (section.get("topics") or [])]
    if len(empty_sections) > max(3, len(sections) // 3):
        problems.append(
            f"разделов без единой темы: {len(empty_sections)} из {len(sections)} — "
            "темы этих разделов потеряны при разборе"
        )

    # --- 1. дословность ---
    fabricated: list[str] = []
    stitched: list[str] = []
    for label, value in (
        [(f"раздел «{name[:50]}»", name) for name in sections]
        + [
            item
            for _, topic in topics
            for item in _topic_fragments(topic)
        ]
    ):
        needle = _norm(value)
        if len(needle) < 12:
            continue
        if needle in corpus:
            continue
        # Второй заход — без пробелов: в PDF слова рвутся переносом строки.
        squeezed = _squeeze(value)
        if squeezed in corpus_squeezed:
            continue
        # Третий заход: начало текста нашлось, а целиком — нет. Это не выдумка,
        # а склейка ячейки, разорванной переносом страницы. Отделяем от подлога.
        if len(squeezed) > 40 and squeezed[:30] in corpus_squeezed:
            stitched.append(f"{label}: «{value[:60]}…»")
            continue
        fabricated.append(f"{label}: «{value[:70]}…»")
    if fabricated:
        problems.append(
            f"нет в исходнике дословно ({len(fabricated)}): " + "; ".join(fabricated[:6])
        )
    if stitched:
        notes.append(
            f"текст собран из частей, разорванных разрывом страницы ({len(stitched)}): "
            + "; ".join(stitched[:4])
        )

    # --- 2. полнота: каждая тема — своя строка исходника ---
    # Идём по порядку: КТП последователен, и одна строка не может обслужить
    # две темы. Ищем первое непривязанное совпадение начиная с текущей позиции,
    # и только потом отступаем назад — так порядок тем тоже проверяется.
    row_keys = [(idx, _squeeze(" ".join(_cells(row)))) for idx, row in lesson_rows]
    claimed: dict[int, str] = {}
    unmatched_topics: list[str] = []
    out_of_order = 0
    cursor = 0
    for _, topic in topics:
        key = _squeeze(str(topic.get("name") or ""))
        number = str(topic.get("ktp_number") or "").strip() or "—"
        if not key:
            unmatched_topics.append(f"№{number}: пустое название")
            continue
        position = next(
            (i for i in range(cursor, len(row_keys))
             if row_keys[i][0] not in claimed and key in row_keys[i][1]),
            None,
        )
        if position is None:
            position = next(
                (i for i in range(0, cursor)
                 if row_keys[i][0] not in claimed and key in row_keys[i][1]),
                None,
            )
            if position is not None:
                out_of_order += 1
        if position is None:
            unmatched_topics.append(f"№{number}: «{str(topic.get('name'))[:60]}»")
            continue
        claimed[row_keys[position][0]] = number
        cursor = max(cursor, position + 1)

    lost_rows = [
        f"строка {idx}: «{_cells(row)[0][:60]}»"
        for idx, row in lesson_rows if idx not in claimed
    ]

    if unmatched_topics:
        problems.append(
            f"темы черновика без своей строки в исходнике ({len(unmatched_topics)}): "
            + "; ".join(unmatched_topics[:6])
        )
    if lost_rows:
        problems.append(
            f"строки исходника, не попавшие в черновик ({len(lost_rows)}): "
            + "; ".join(lost_rows[:6])
        )
    if out_of_order:
        notes.append(f"тем, нарушающих порядок строк исходника: {out_of_order}")

    # --- 4. часы ---
    draft_hours = sum(float(topic.get("hours") or 0) for _, topic in topics)
    declared = _declared_hours(extraction.header_text)
    if declared is not None and abs(declared - draft_hours) > 0.01:
        problems.append(
            f"часы: в шапке документа заявлено {declared:g}, сумма тем черновика {draft_hours:g}"
        )
    stated = draft.get("hours_per_year")
    if isinstance(stated, (int, float)) and abs(float(stated) - draft_hours) > 0.01:
        notes.append(f"hours_per_year={float(stated):g} не сходится с суммой тем {draft_hours:g}")

    # --- 5. заголовки разделов исходника без пары ---
    orphan_headings = [
        _cells(row)[0]
        for _, row in heading_rows
        if not any(_norm(_cells(row)[0]) in _norm(name) or _norm(name) in _norm(_cells(row)[0])
                   for name in sections)
    ]
    if orphan_headings:
        notes.append(
            f"заголовки в исходнике без раздела в черновике ({len(orphan_headings)}): "
            + "; ".join(item[:50] for item in orphan_headings[:6])
        )

    return {
        "source_lesson_rows": len(lesson_rows),
        "source_headings": len(heading_rows),
        "declared_hours": declared,
        "draft_topics": len(topics),
        "draft_sections": len(sections),
        "draft_hours": draft_hours,
        "low_confidence": sum(1 for _, t in topics if t.get("confidence") == "low"),
        "model_warnings": len(draft.get("warnings") or []),
        "problems": problems,
        "notes": notes,
    }


def _topic_fragments(topic: dict[str, Any]) -> list[tuple[str, str]]:
    number = str(topic.get("ktp_number") or "").strip() or "?"
    fragments: list[tuple[str, str]] = []
    for field in ("name", "learning_objectives", "resources"):
        value = topic.get(field)
        if isinstance(value, str) and value.strip():
            fragments.append((f"тема №{number} ({field})", value))
    skills = topic.get("skills")
    if isinstance(skills, list):
        for item in skills:
            if isinstance(item, str) and item.strip():
                fragments.append((f"тема №{number} (skills)", item))
    return fragments


def main() -> int:
    if len(sys.argv) != 3:
        print('Использование: python -m ktp.verify "ктп.docx" "черновик.json"')
        return 2
    source_path, draft_path = Path(sys.argv[1]), Path(sys.argv[2])
    for path in (source_path, draft_path):
        if not path.is_file():
            print(f"Файл не найден: {path}")
            return 2

    report = verify(source_path, draft_path)

    declared = report["declared_hours"]
    print(f"Исходник:  строк-уроков {report['source_lesson_rows']}, "
          f"заголовков {report['source_headings']}, "
          f"часов в шапке {declared:g}" if declared is not None
          else f"Исходник:  строк-уроков {report['source_lesson_rows']}, "
               f"заголовков {report['source_headings']}, часов в шапке не указано")
    print(f"Черновик:  тем {report['draft_topics']}, "
          f"разделов {report['draft_sections']}, часов {report['draft_hours']:g}")
    print(f"           confidence=low: {report['low_confidence']}, "
          f"warnings от модели: {report['model_warnings']}")
    print()

    if report["problems"]:
        print("РАСХОЖДЕНИЯ (требуют правки):")
        for item in report["problems"]:
            print(f"  ✗ {item}")
    else:
        print("  ✓ все темы найдены в исходнике, дублей нет, текст дословный")

    if report["notes"]:
        print()
        print("К СВЕДЕНИЮ (проверьте глазами):")
        for item in report["notes"]:
            print(f"  · {item}")

    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
