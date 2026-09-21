#!/usr/bin/env bash
# Сверка черновика КТП с исходным файлом. Модель не участвует — только сравнение.
# Использование: ./check-ktp.sh "путь/к/ктп.docx" ["путь/к/черновика.json"]
# Если черновик не указан, берётся "<исходник>.draft.json" рядом с исходником.
set -euo pipefail
cd "$(dirname "$0")"
[ -n "${1:-}" ] || { echo 'Укажите файл КТП: ./check-ktp.sh "ктп.docx"'; exit 1; }
[ -x .venv/bin/python ] || { echo "Нет .venv — сначала ./start-local.sh"; exit 1; }

SRC="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
DRAFT="${2:-$SRC.draft.json}"
[ -f "$SRC" ]   || { echo "Не найден исходник: $SRC"; exit 1; }
[ -f "$DRAFT" ] || { echo "Не найден черновик: $DRAFT"; echo "Сначала ./parse-ktp.sh \"$1\""; exit 1; }

cd backend && exec ../.venv/bin/python -m ktp.verify "$SRC" "$DRAFT"
