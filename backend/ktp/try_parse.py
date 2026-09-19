"""Проверка разбора КТП из командной строки, без интерфейса.

Запуск из каталога backend:
    ../.venv/bin/python -m ktp.try_parse "путь/к/ктп.docx"

Печатает: что извлеклось детерминированно, что вернула модель,
и сохраняет черновик рядом с файлом как <имя>.draft.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .extract import extract
from .mapper import map_to_schema


async def main(path_str: str) -> int:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    path = Path(path_str)
    if not path.exists():
        print(f"Файл не найден: {path}")
        return 1

    extraction = extract(path.read_bytes(), path.name)
    print("=== ИЗВЛЕЧЕНО ИЗ ФАЙЛА (без ИИ) ===")
    print(f"  формат: {extraction.source_kind}")
    print(f"  таблиц: {len(extraction.tables)}, строк: {extraction.row_count}")
    print(f"  шапка первой таблицы: {extraction.tables[0][0] if extraction.tables else '—'}")

    print("\n=== СОПОСТАВЛЕНИЕ МОДЕЛЬЮ ===")
    draft = await map_to_schema(extraction)

    sections = draft.get("sections") or []
    topics = [t for s in sections for t in (s.get("topics") or [])]
    low = [t for t in topics if t.get("confidence") == "low"]
    print(f"  предмет: {draft.get('subject_name')}, класс: {draft.get('grade')}")
    print(f"  часов в год: {draft.get('hours_per_year')}, в неделю: {draft.get('hours_per_week')}")
    print(f"  разделов: {len(sections)}, тем: {len(topics)}")
    print(f"  тем с низкой уверенностью: {len(low)}")
    with_objectives = sum(1 for t in topics if (t.get("learning_objectives") or "").strip())
    print(f"  тем с заполненными целями: {with_objectives} из {len(topics)}")

    if draft.get("column_mapping"):
        print("\n  как разобраны колонки:")
        for source, target in draft["column_mapping"].items():
            print(f"    {source}  →  {target}")
    if draft.get("warnings"):
        print("\n  предупреждения:")
        for w in draft["warnings"]:
            print(f"    • {w}")
    if low:
        print("\n  строки, требующие внимания:")
        for t in low[:5]:
            print(f"    • {t.get('ktp_number')} {str(t.get('name'))[:60]} — {t.get('note')}")

    print("\n=== ПЕРВЫЕ ТРИ ТЕМЫ ===")
    for t in topics[:3]:
        print(json.dumps(t, ensure_ascii=False, indent=2)[:600])

    out = path.with_suffix(path.suffix + ".draft.json")
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЧерновик сохранён: {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Укажите файл: python -m ktp.try_parse "ктп.docx"')
        raise SystemExit(1)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
