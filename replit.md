# Intellect Learning Platform

Russian-language learning and lesson-management platform for grade 7 olympiad students and teachers.

## Run & Operate

Local (macOS/Linux):
- `docker compose up -d` — Postgres 16 + pgvector (db `intellect`, test db `intellect_test`)
- `cp .env.example backend/.env` and fill keys
- `cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt && .venv/bin/python migrate.py && .venv/bin/uvicorn main:app --port 5000`
- `cd artifacts/intellect-learning-platform && PORT=5173 BASE_PATH=/ pnpm exec vite`

Replit:

- `cd backend && pip install -r requirements.txt && python migrate.py && uvicorn main:app --host 0.0.0.0 --port 5000` — run the FastAPI server
- `pnpm --filter @workspace/intellect-learning-platform run dev` — run the React frontend
- `pnpm run typecheck` — full typecheck across all packages
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- Frontend: React 18, TypeScript, Tailwind CSS, Vite
- API: Python 3.11+, FastAPI, Pydantic
- DB: PostgreSQL + async SQLAlchemy

## Where things live

- `artifacts/intellect-learning-platform/` — React frontend
- `backend/` — FastAPI backend, SQLAlchemy models, seed script, routes, and component registry
- `artifacts/intellect-learning-platform/src/lib/api.ts` — typed frontend API client

## Architecture decisions

- The backend is Python-only; do not introduce Express, Drizzle, or another JavaScript backend.
- Schema is managed by Alembic (`backend/migrations`); run `python migrate.py` before the API. Never use `create_all`. New change: edit models.py, then `alembic revision --autogenerate -m "..."` and review the file.
- Curriculum data remains empty until KTP upload is implemented.

## Product

- Student and teacher role selection using seeded users
- Curriculum subject, section, and topic browsing
- Student progress and teacher dashboard foundations
- Lesson and KTP workflows intentionally stubbed for Stage 2

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
