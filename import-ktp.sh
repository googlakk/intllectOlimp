#!/usr/bin/env bash
# Импорт разобранного черновика в базу. Бэкенд должен быть запущен.
# Использование: ./import-ktp.sh [файл-черновика.json]
set -euo pipefail
cd "$(dirname "$0")"
DRAFT="${1:-api-parse-result.json}"
[ -f "$DRAFT" ] || { echo "Черновик не найден: $DRAFT"; echo "Сначала ./test-parse-api.sh"; exit 1; }

if ! curl -sf http://127.0.0.1:5000/api/healthz >/dev/null; then
  echo "Бэкенд не отвечает на :5000 — сначала ./start-local.sh"; exit 1
fi

python3 - "$DRAFT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
secs = d.get('sections') or []
tops = [t for s in secs for t in (s.get('topics') or [])]
print(f"Будет импортировано: {d.get('subject_name')}, {d.get('grade')} класс")
print(f"  разделов {len(secs)}, тем {len(tops)}, часов {d.get('hours_per_year')}")
PY
read -r -p "Импортировать в базу? [y/N] " answer
[ "$answer" = "y" ] || { echo "Отменено."; exit 0; }

CODE=$(curl -sS -o import-result.json -w '%{http_code}' --max-time 120 \
       -X POST http://127.0.0.1:5000/api/ktp/upload \
       -H 'Content-Type: application/json' --data-binary "@$DRAFT")
echo "HTTP $CODE"
python3 -c "
import json
d = json.load(open('import-result.json', encoding='utf-8'))
if 'detail' in d: print('ОШИБКА:', json.dumps(d['detail'], ensure_ascii=False)[:600])
else: print(f\"Создан предмет id={d.get('id')}: {d.get('name')}, разделов {d.get('section_count')}, тем {d.get('topic_count')}\")
"
