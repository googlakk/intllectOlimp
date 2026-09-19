#!/usr/bin/env bash
# Локальный запуск платформы: бэкенд на :5000, фронтенд на :5173
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ОШИБКА: нет файла .env"
  echo "Выполните:  cp .env.example .env   — и впишите DATABASE_URL"
  exit 1
fi
set -a; source .env; set +a

if [ -z "${DATABASE_URL:-}" ] || [[ "$DATABASE_URL" == *"ВАШ-ПРОЕКТ"* ]]; then
  echo "ОШИБКА: в .env не заполнен DATABASE_URL"; exit 1
fi

command -v python3 >/dev/null || { echo "ОШИБКА: не установлен python3"; exit 1; }
command -v node    >/dev/null || { echo "ОШИБКА: не установлен node"; exit 1; }

echo "[1/5] Python-окружение..."
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r backend/requirements.txt

echo "[2/5] Зависимости фронтенда..."
if ! command -v pnpm >/dev/null; then
  echo
  echo "ОШИБКА: не установлен pnpm."
  echo "Установите один раз:  npm install -g pnpm@10"
  echo "(раньше скрипт подставлял npx — из-за этого ломались платформенные"
  echo " модули вроде @rollup/rollup-darwin-arm64)"
  exit 1
fi
pnpm install --silent
# Платформенный бинарник rollup иногда не доезжает — известная проблема
# с необязательными зависимостями. Проверяем и лечим переустановкой.
if ! ls node_modules/.pnpm 2>/dev/null | grep -q '@rollup+rollup-darwin'; then
  echo
  echo "ОШИБКА: не установлен платформенный бинарник rollup для macOS."
  echo "Ничего не удаляю — решайте сами. Обычно помогает:"
  echo "  rm -rf node_modules artifacts/*/node_modules pnpm-lock.yaml && pnpm install"
  exit 1
fi

echo "[3/4] Проверяю доступность базы..."
DB_CHECK=$(./.venv/bin/python - <<'PYCHK'
import os, socket, sys
from urllib.parse import urlsplit
url = os.environ["DATABASE_URL"].strip()
if "[" in url or "]" in url:
    print("BRACKET|"); sys.exit(0)
try:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or 5432
except ValueError as exc:
    print(f"BADURL|{exc}"); sys.exit(0)
if not host:
    print("BADURL|в строке не удалось найти адрес сервера"); sys.exit(0)
try:
    socket.getaddrinfo(host, port)
except socket.gaierror:
    print(f"DNS|{host}"); sys.exit(0)
try:
    s = socket.create_connection((host, port), timeout=8); s.close()
except Exception as exc:
    print(f"TCP|{host}:{port}|{exc}"); sys.exit(0)
print(f"OK|{host}:{port}")
PYCHK
)
case "$DB_CHECK" in
  OK*)
    echo "      база отвечает: ${DB_CHECK#OK|}"
    case "$DB_CHECK" in
      *:6543) echo
              echo "ВНИМАНИЕ: порт 6543 — это Transaction pooler."
              echo "Он не поддерживает подготовленные запросы, на которых построен"
              echo "наш драйвер asyncpg. Возьмите вкладку Session pooler (порт 5432)."
              echo ;;
    esac ;;
  DNS*)
    echo
    echo "ОШИБКА: имя сервера базы не разрешается в адрес — ${DB_CHECK#DNS|}"
    echo
    echo "Почти всегда это значит, что взята строка Direct connection."
    echo "Возьмите в Supabase: Project Settings -> Database ->"
    echo "Connection string -> вкладка Session pooler"
    echo "Она выглядит так:"
    echo "  postgresql://postgres.ССЫЛКА:ПАРОЛЬ@aws-0-РЕГИОН.pooler.supabase.com:5432/postgres"
    exit 1 ;;
  BRACKET*)
    echo
    echo "ОШИБКА: в DATABASE_URL остались квадратные скобки [ ]"
    echo
    echo "Supabase показывает строку с заглушкой [YOUR-PASSWORD]."
    echo "Её надо заменить на настоящий пароль базы — вместе со скобками."
    echo
    echo "  было:  ...postgres:[YOUR-PASSWORD]@..."
    echo "  стало: ...postgres:вашпарольбезскобок@..."
    echo
    echo "Если в пароле есть @ : / ? # или пробел — смените пароль на"
    echo "буквенно-цифровой в Database -> Reset database password,"
    echo "иначе эти знаки ломают строку подключения."
    exit 1 ;;
  BADURL*)
    echo
    echo "ОШИБКА: строку DATABASE_URL не удалось разобрать"
    echo "  ${DB_CHECK#BADURL|}"
    echo "Проверьте, что она начинается с postgresql:// и скопирована целиком."
    exit 1 ;;
  TCP*)
    echo
    echo "ОШИБКА: имя разрешилось, но подключиться не удалось"
    echo "  ${DB_CHECK#TCP|}"
    echo "Проверьте пароль в строке и что проект Supabase не на паузе."
    exit 1 ;;
esac

if lsof -nP -iTCP:5000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo
  echo "ОШИБКА: порт 5000 уже занят — скорее всего висит бэкенд от прошлого запуска."
  echo "Освободите его:"
  echo "  lsof -ti:5000 | xargs kill"
  echo
  echo "Если процесс не ваш, это может быть AirPlay Receiver macOS:"
  echo "  Системные настройки -> Основные -> AirDrop и Handoff -> AirPlay-приёмник (выключить)"
  exit 1
fi

echo "[4/4] Бэкенд на http://localhost:5000 ..."
(cd backend && ../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 5000) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT INT TERM

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:5000/api/healthz >/dev/null 2>&1; then echo "      бэкенд отвечает"; break; fi
  if [ "$i" = 30 ]; then echo "ОШИБКА: бэкенд не поднялся за 30 секунд"; exit 1; fi
  sleep 1
done

echo "[5/5] Фронтенд..."
echo
echo "=================================================="
echo "  Откройте в браузере:  http://localhost:5173"
echo "  Остановить: Ctrl+C"
echo "=================================================="
echo
cd artifacts/intellect-learning-platform && pnpm exec vite --port 5173 --host 127.0.0.1
