# Один контейнер: FastAPI отдаёт и /api, и собранный сайт.
# Секреты сюда не попадают — задаются переменными окружения на хостинге.

# --- 1. Сборка frontend ---------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10 --activate
COPY . .
RUN pnpm install --frozen-lockfile --filter ./artifacts/intellect-learning-platform... \
 && pnpm --filter ./artifacts/intellect-learning-platform run build

# --- 2. Backend ------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend /app/artifacts/intellect-learning-platform/dist/public /app/frontend
ENV FRONTEND_DIST=/app/frontend
EXPOSE 8000
# Хостинги передают порт в $PORT.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
