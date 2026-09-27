# Продолжение в Claude Code и запуск среды

> Актуальное состояние, правила владельца и выкладка на прод — в `docs/CLAUDE_HANDOFF.md`. Быстрый локальный запуск: `./start-local.sh` (бэкенд :5000, фронтенд :5173). Локальный бэкенд смотрит в ту же базу Supabase, что и прод.

## Тот же Mac — рекомендуемый вариант

Claude Code уже найден: `/opt/homebrew/bin/claude`. Менять проект или переносить файлы не требуется.

```bash
cd "/Users/intellectmac/Documents/Олимпиадники/intellect-platform"
claude
```

Стартовый запрос:

> Прочитай CLAUDE.md и docs/CLAUDE_HANDOFF.md. Проверь, что рабочая ветка dev/lesson-experience совпадает с main,
> и какие серверы уже запущены. Не печатай секреты и не меняй базу автоматически: она общая с продом.
> Дальше — моя задача: …

Проверить уже работающие процессы, прежде чем запускать новые:

```bash
lsof -nP -iTCP:5000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
curl --fail --silent --show-error http://127.0.0.1:5000/api/healthz
```

`lsof` без результата означает, что слушателя не найдено, а не что надо завершать другие процессы.

Если frontend5173 отсутствует, открыть отдельный терминал:

```bash
cd "/Users/intellectmac/Documents/Олимпиадники/intellect-platform"
pnpm --filter ./artifacts/intellect-learning-platform exec vite --host 127.0.0.1 --port 5173
```

Если backend5000 отсутствует, и подтверждено, что .env относится к нужной базе:

```bash
cd "/Users/intellectmac/Documents/Олимпиадники/intellect-platform/backend"
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 5000
```

Держать оба терминала работающими. `--reload` не обязателен; перед сдачей спокойнее явный перезапуск после изменений backend. Frontend обновляется через Vite. Не запускать второй экземпляр на занятом порту.

Открыть `http://127.0.0.1:5173`. Использовать существующую учётную запись; пароли в документах не записаны. После старта проверить также `http://127.0.0.1:5173/api/healthz`: это путь через Vite proxy к5000. Не смешивать без необходимости localhost и127.0.0.1 — это разные browser origins для локального состояния.

## Другая машина / чистая среда

1. Передать всю актуальную рабочую копию, включая untracked исходники, `supabase/migrations`, документы и `public/images/lessons`. Git clone текущего HEAD недостаточен. Сравнить `git status --short` и наличие новых файлов на обеих сторонах.
2. Если перенос через Git — сначала просмотреть diff, выбрать и закоммитить только нужные файлы, проверить отсутствие секретов. Никакого автоматического `git add .` на этой большой рабочей копии.
3. Для прямого переноса в новый пустой каталог можно использовать rsync. Сначала dry run, не применять `--delete`:

```bash
rsync -an --exclude=node_modules --exclude=.venv --exclude=.env \
  --exclude=dist --exclude=__pycache__ --exclude=.pytest_cache \
  --exclude=.playwright-cli --exclude=output --exclude=outputs --exclude=evidence \
  --exclude=.codex --exclude=.agents --exclude=api-parse-result.json --exclude=import-result.json \
  "/путь/к/intellect-platform/" "/новый/пустой/каталог/intellect-platform/"
```

После проверки повторить с `-a` вместо `-an`. Это пример локального копирования; для удалённой машины выбрать безопасный канал и её путь. Команда копирует также .git, исходники, миграции и готовые изображения; не копирует локальные секреты и диагностические материалы. Не публиковать архив рабочей копии в открытом доступе. База и Supabase Storage НЕ находятся внутри каталога проекта: их данные переносятся отдельно либо подключается существующий сервис с пониманием последствий.

4. Установить Node22 (`.nvmrc`), pnpm10, Python>=3.11. Claude Code установить официальным способом в нужной среде, если его ещё нет. Не переносить старую .venv между каталогами или ОС.
5. Из корня проекта установить зависимости:

```bash
pnpm install --frozen-lockfile
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

На Windows для Python использовать `.venv\Scripts\python.exe`; проще запускать проект в WSL и заново создать окружение там. `uv sync` по одному pyproject не заменяет requirements: в requirements есть дополнительные библиотеки импорта и тестирования.

6. Только если `.env` отсутствует, создать его из `.env.example`. Заполнить локально, не вставлять секреты в чат. Существующий .env не перезаписывать.

Для полноценной платформы нужны DATABASE_URL и параметры текущего Supabase Auth/Storage: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY. Для генерации уроков — подходящий ключ Anthropic/OpenRouter и согласованные LLM_PROVIDER/LLM_MODEL настройки. Медиа и HeyGen опциональны; их ключи не нужны для показа уже созданных образцов. Service role — только backend, никогда VITE_*.

При смене БД: сначала резервная копия/тестовый проект и сверка миграций. Startup выполняет create_all/schema_compat; не проверять запуск на случайной production-базе. Миграции auth и учебного цикла изучить в supabase/migrations и docs/BETA_AUTH_RUNBOOK.md. Не выполнять bootstrap/repair автоматически. Для DATABASE_URL корректно URL-кодировать специальные символы пароля, не менять пароль ради парсинга URL.

7. Запустить backend и frontend в двух терминалах, как выше, заменив абсолютный путь на свой. Проверить прямой health, proxy health, вход и один обычный урок. Наличие только статических образцов не подтверждает работу backend.

## Почему не советуем начинать с start-local.sh в новой ОС

Скрипт существует, но рассчитан на macOS: проверяет rollup-darwin, делает source .env, устанавливает зависимости, использует pip с абсолютным shebang и при выходе останавливает свой backend. Он может ошибочно отвергнуть Linux и в тексте ошибки советует удалять lockfile. Не следовать этому совету автоматически. Для предсказуемого переноса использовать явные команды выше и сохранять lockfile.

## Проверки

Из корня:

```bash
pnpm run typecheck
pnpm run check:architecture
pnpm run test:run
pnpm --filter ./artifacts/intellect-learning-platform run build
```

Полный gate:

```bash
pnpm run check:quality
```

`run-tests.sh` внутри gate устанавливает Python-зависимости и может требовать сеть. Если зависимости уже установлены, узкие backend-тесты можно запускать из backend напрямую. Пример не подключает настоящий production URL:

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://test:test@localhost/test ../.venv/bin/python -m pytest -q
```

Специальные PostgreSQL integration tests требуют отдельной локальной `learning_test` базы и явного LEARNING_CYCLE_TEST_DATABASE_URL; не подставлять рабочую БД. Не объявлять такие тесты выполненными, если они пропущены.

Корневой `pnpm run build` включает дополнительный mockup-sandbox; для сдаваемого приложения достаточно фильтрованной сборки выше. После UI-правок проверить браузер на desktop/375px, клавиатуру, ошибки сохранения и цепочку учитель→ученик. Исторические скриншоты не заменяют свежую проверку.
