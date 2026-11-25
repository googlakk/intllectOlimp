# Выкат на сервер (Hetzner, рядом с BilimOs)

Один контейнер `app` отдаёт и API (`/api/*`), и собранный фронтенд на порту 5000.
Порты наружу не публикуются: Caddy BilimOs ходит на `http://olimp-app:5000`
по docker-сети BilimOs (`BILIMOS_NETWORK`, по умолчанию `bilimos_default`).
База `db` видна только во внутренней сети проекта.

Все команды ниже — из `/opt/olimp`. `--env-file .env.prod` нужен, чтобы compose
подставил `BILIMOS_NETWORK`; сами контейнеры читают `.env.prod` через `env_file`.

```sh
alias dc='docker compose -f docker-compose.prod.yml --env-file .env.prod'
```

## Первая установка

```sh
git clone <repo> /opt/olimp && cd /opt/olimp
cp .env.prod.example .env.prod && chmod 600 .env.prod   # заполнить все CHANGE_ME
docker network ls | grep bilimos                         # проверить имя сети BilimOs
dc up -d --build
dc exec app python manage.py create-admin <логин> "<ФИО>"  # печатает временный пароль
```

В Caddyfile BilimOs добавить сайт, например:

```
olimp.example.kg {
    reverse_proxy olimp-app:5000
}
```

## Обновление

```sh
cd /opt/olimp && git pull --ff-only
docker tag olimp-app:latest olimp-app:prev   # точка отката
dc up -d --build                             # миграции применяются при старте (migrate.py)
```

## Откат

```sh
docker tag olimp-app:prev olimp-app:latest
dc up -d --no-build app
```

Внимание: если новая версия применила миграцию, старый код может не совпасть со схемой —
перед обновлением с миграциями делайте бэкап (ниже) и при откате восстанавливайте его.

## Бэкап базы

```sh
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup-$(date +%F).dump
# восстановление:
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup-YYYY-MM-DD.dump
```

## Проверка

```sh
dc ps                                                   # оба сервиса Up, db (healthy)
dc logs --tail 50 app
dc exec app python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:5000/api/healthz').read())"
curl -s https://olimp.example.kg/api/healthz            # {"status":"ok"} снаружи через Caddy
```
