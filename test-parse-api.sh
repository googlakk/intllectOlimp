#!/usr/bin/env bash
# Проверка эндпоинта /api/ktp/parse. Бэкенд должен быть запущен (./start-local.sh).
set -euo pipefail
cd "$(dirname "$0")"
FILE="${1:-$HOME/Documents/Олимпиадники/Образцы ктп/ктп 7 класс.pdf}"
[ -f "$FILE" ] || { echo "Файл не найден: $FILE"; exit 1; }

if ! curl -sf http://127.0.0.1:5000/api/healthz >/dev/null; then
  echo "Бэкенд не отвечает на :5000 — сначала ./start-local.sh"; exit 1
fi

OUT="api-parse-result.json"
echo "Отправляю файл, разбор занимает около минуты..."
CODE=$(curl -sS -o "$OUT" -w '%{http_code}' --max-time 300 \
       -X POST http://127.0.0.1:5000/api/ktp/parse \
       -F "file=@$FILE")
echo "HTTP $CODE, ответ сохранён в $OUT"
python3 - "$OUT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
if 'detail' in d and 'sections' not in d:
    print("ОШИБКА ОТ СЕРВЕРА:", d['detail']); raise SystemExit(1)
s = d.get('stats', {}); src = d.get('source', {})
print(f"  файл: {src.get('filename')} ({src.get('kind')}), строк {src.get('row_count')}")
print(f"  разделов: {s.get('section_count')} | тем: {s.get('topic_count')}")
print(f"  с целями: {s.get('with_objectives')} | низкая уверенность: {s.get('low_confidence_count')}")
print(f"  предмет: {d.get('subject_name')}, класс {d.get('grade')}, часов {d.get('hours_per_year')}")
PY
