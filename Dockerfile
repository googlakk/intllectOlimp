# amd64 pinned: pnpm-workspace overrides drop linux-arm64 native binaries; output is static files.
FROM --platform=linux/amd64 node:22-slim AS frontend
WORKDIR /src
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate
COPY . .
RUN pnpm install --frozen-lockfile --filter @workspace/intellect-learning-platform...
ENV NODE_ENV=production BASE_PATH=/ PORT=5173
RUN pnpm --filter @workspace/intellect-learning-platform run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend /src/artifacts/intellect-learning-platform/dist/public /app/static
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 5000
CMD ["sh", "-c", "python migrate.py && exec uvicorn main:app --host 0.0.0.0 --port 5000 --proxy-headers --forwarded-allow-ips '*'"]
