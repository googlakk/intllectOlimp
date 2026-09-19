#!/usr/bin/env bash
# Разбор файла КТП. Запуск из любого места: ./parse-ktp.sh "путь/к/ктп.pdf"
set -euo pipefail
cd "$(dirname "$0")"
[ -n "${1:-}" ] || { echo 'Укажите файл: ./parse-ktp.sh "ктп.pdf"'; exit 1; }
[ -x .venv/bin/python ] || { echo "Нет .venv — сначала ./start-local.sh"; exit 1; }
FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd backend && exec ../.venv/bin/python -m ktp.try_parse "$FILE"
