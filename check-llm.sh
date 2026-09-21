#!/usr/bin/env bash
# Проверка шлюза к моделям: маршруты, ключ, доступность моделей, цены.
# Использование: ./check-llm.sh           — без обращения к моделям
#                ./check-llm.sh --call    — плюс один пробный вызов (доли цента)
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Нет .venv — сначала ./start-local.sh"; exit 1; }
cd backend && exec ../.venv/bin/python -m llm.probe "$@"
