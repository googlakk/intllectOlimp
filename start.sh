#!/usr/bin/env bash
# Единый запуск платформы: бэкенд :5000 + фронтенд :5173.
#
#   ./start.sh            поднять всё и показывать логи (Ctrl+C — остановить то, что запустил скрипт)
#   ./start.sh -d         поднять всё в фоне и выйти
#   ./start.sh status     что сейчас запущено
#   ./start.sh stop       остановить процессы, запущенные этим скриптом
#   ./start.sh --install  принудительно переустановить зависимости перед запуском
#
# Уже работающие сервера переиспользуются, чужие процессы скрипт никогда не завершает.
# Секреты из .env не выводятся: бэкенд читает .env сам.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT/artifacts/intellect-learning-platform"
RUN_DIR="$ROOT/.run"
BACKEND_PORT=5000
FRONTEND_PORT=5173
BACKEND_HEALTH="http://127.0.0.1:$BACKEND_PORT/api/healthz"
PROXY_HEALTH="http://127.0.0.1:$FRONTEND_PORT/api/healthz"

say()  { printf '%s\n' "$*"; }
fail() { printf 'ОШИБКА: %s\n' "$*" >&2; exit 1; }

is_listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
is_healthy()   { curl --fail --silent --max-time 3 "$1" >/dev/null 2>&1; }

# PID-файлы хранят только процессы, которые запустил этот скрипт.
pid_alive() {
  local file="$RUN_DIR/$1.pid"
  [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null
}

stop_one() {
  local name="$1" file="$RUN_DIR/$1.pid"
  if pid_alive "$name"; then
    local pid; pid="$(cat "$file")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    say "  $name остановлен (PID $pid)"
  fi
  rm -f "$file"
}

cmd_status() {
  for spec in "backend:$BACKEND_PORT:$BACKEND_HEALTH" "frontend:$FRONTEND_PORT:$PROXY_HEALTH"; do
    IFS=: read -r name port _ <<<"$spec"
    local url="${spec#*:*:}" owner="чужой процесс"
    if pid_alive "$name"; then owner="запущен start.sh, PID $(cat "$RUN_DIR/$name.pid")"; fi
    if ! is_listening "$port"; then
      say "  $name :$port — не запущен"
    elif is_healthy "$url"; then
      say "  $name :$port — работает ($owner)"
    else
      say "  $name :$port — порт занят, но /api/healthz не отвечает ($owner)"
    fi
  done
}

cmd_stop() {
  say "Останавливаю процессы, запущенные start.sh..."
  stop_one frontend
  stop_one backend
  cmd_status
}

wait_for() {
  local url="$1" seconds="$2" name="$3" log="$4"
  for _ in $(seq 1 "$seconds"); do
    is_healthy "$url" && return 0
    if ! pid_alive "$name"; then
      say "--- последние строки $log ---" >&2; tail -n 30 "$log" >&2 || true
      fail "$name завершился при старте"
    fi
    sleep 1
  done
  say "--- последние строки $log ---" >&2; tail -n 30 "$log" >&2 || true
  fail "$name не ответил за $seconds с"
}

ensure_deps() {
  local force="$1"
  command -v node >/dev/null || fail "не установлен node (нужна версия из .nvmrc: $(cat "$ROOT/.nvmrc"))"
  command -v pnpm >/dev/null || fail "не установлен pnpm. Установите: npm install -g pnpm@10"
  local want; want="$(cat "$ROOT/.nvmrc" 2>/dev/null || echo '')"
  local have; have="$(node -v | sed 's/^v//; s/\..*//')"
  if [ -n "$want" ] && [ "$have" != "$want" ]; then
    say "  внимание: node $(node -v), проект рассчитан на $want (.nvmrc)"
  fi

  if [ "$force" = 1 ] || [ ! -x "$ROOT/.venv/bin/python" ]; then
    command -v python3 >/dev/null || fail "не установлен python3 (нужен >= 3.11)"
    say "  Python-окружение..."
    [ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/python" -m pip install --quiet -r "$ROOT/backend/requirements.txt"
  fi
  if [ "$force" = 1 ] || [ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]; then
    say "  Node-зависимости (lockfile не меняется)..."
    (cd "$ROOT" && pnpm install --frozen-lockfile)
  fi
}

start_backend() {
  if is_healthy "$BACKEND_HEALTH"; then
    say "  backend уже работает на :$BACKEND_PORT — переиспользую"
    return
  fi
  if is_listening "$BACKEND_PORT"; then
    fail "порт $BACKEND_PORT занят процессом, который не отвечает на /api/healthz.
  Посмотрите, кто это:  lsof -nP -iTCP:$BACKEND_PORT -sTCP:LISTEN
  (на macOS это бывает AirPlay-приёмник). Скрипт чужие процессы не завершает."
  fi
  [ -f "$ROOT/.env" ] || fail "нет файла .env. Создайте из .env.example и заполните локально."
  say "  внимание: при старте бэкенд применяет совместимые изменения схемы к базе из .env"
  say "  запускаю backend на :$BACKEND_PORT (лог: .run/backend.log)..."
  (cd "$ROOT/backend" && exec "$ROOT/.venv/bin/python" -m uvicorn main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT") >"$RUN_DIR/backend.log" 2>&1 &
  echo $! >"$RUN_DIR/backend.pid"
  wait_for "$BACKEND_HEALTH" 60 backend "$RUN_DIR/backend.log"
  say "  backend отвечает"
}

start_frontend() {
  if is_listening "$FRONTEND_PORT"; then
    say "  frontend уже слушает :$FRONTEND_PORT — переиспользую"
    return
  fi
  say "  запускаю frontend на :$FRONTEND_PORT (лог: .run/frontend.log)..."
  (cd "$FRONTEND_DIR" && exec ./node_modules/.bin/vite --config vite.config.ts \
      --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort) >"$RUN_DIR/frontend.log" 2>&1 &
  echo $! >"$RUN_DIR/frontend.pid"
  wait_for "$PROXY_HEALTH" 60 frontend "$RUN_DIR/frontend.log"
  say "  frontend отвечает, прокси /api → :$BACKEND_PORT работает"
}

cmd_up() {
  local detach="$1" force="$2"
  mkdir -p "$RUN_DIR"
  say "[1/3] Зависимости"
  ensure_deps "$force"
  say "[2/3] Backend"
  start_backend
  say "[3/3] Frontend"
  start_frontend

  say ""
  say "=================================================="
  say "  Откройте:  http://127.0.0.1:$FRONTEND_PORT"
  if [ "$detach" = 1 ]; then
    say "  Работает в фоне. Остановить: ./start.sh stop"
    say "=================================================="
    return
  fi
  say "  Ctrl+C — остановить процессы, запущенные этим скриптом"
  say "=================================================="
  trap 'say ""; cmd_stop; exit 0' INT TERM
  local logs=()
  for name in backend frontend; do
    if pid_alive "$name"; then logs+=("$RUN_DIR/$name.log"); fi
  done
  if [ ${#logs[@]} -eq 0 ]; then
    say "Все сервера уже были запущены ранее — скрипту нечего держать. Выход."
    return
  fi
  tail -n 0 -F "${logs[@]}" &
  local tail_pid=$!
  # Следим, чтобы наши процессы не упали молча.
  while true; do
    for name in backend frontend; do
      if [ -f "$RUN_DIR/$name.pid" ] && ! pid_alive "$name"; then
        kill "$tail_pid" 2>/dev/null || true
        say "" ; say "ОШИБКА: $name неожиданно завершился, см. .run/$name.log" >&2
        cmd_stop; exit 1
      fi
    done
    sleep 2
  done
}

DETACH=0; FORCE=0; ACTION=up
for arg in "$@"; do
  case "$arg" in
    -d|--detach) DETACH=1 ;;
    --install)   FORCE=1 ;;
    status|stop|up) ACTION="$arg" ;;
    -h|--help)   sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "неизвестный аргумент: $arg (см. ./start.sh --help)" ;;
  esac
done

case "$ACTION" in
  status) cmd_status ;;
  stop)   cmd_stop ;;
  up)     cmd_up "$DETACH" "$FORCE" ;;
esac
