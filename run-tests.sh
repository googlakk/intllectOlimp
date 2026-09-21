#!/usr/bin/env bash
# Прогон тестов бэкенда. Сначала доставляет зависимости, потом запускает.
# Использование: ./run-tests.sh
#
# Почему ставит зависимости: тесты у разработчика проходили, а на этой машине
# падали на отсутствующем модуле — среды разошлись. Зелёные тесты в чужой
# среде ничего не доказывают, поэтому прогон начинается с выравнивания.
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Нет .venv — сначала ./start-local.sh"; exit 1; }

echo "Сверяю зависимости…"
# Через `python -m pip`, а не `.venv/bin/pip`: у скрипта pip в shebang зашит
# абсолютный путь, и он перестаёт работать, если каталог проекта перенесли.
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r backend/requirements.txt

# Тестам база не нужна, но импорт модулей требует переменную.
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://test:test@localhost/test}"

cd backend
if ! ../.venv/bin/python -m pytest -q; then
  echo
  echo "ТЕСТЫ НЕ ПРОШЛИ — разбор запускать нельзя."
  exit 1
fi
echo
echo "Тесты прошли. Можно запускать ./parse-ktp.sh"
