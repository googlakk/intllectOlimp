# Feature Map

## Backend

- FastAPI application and route layer.
- KTP parsing, extraction, column mapping, validation, assembly, and verification.
- Lesson/objective generation.
- LLM routing across configured providers.
- Database models and seed data.

## Frontend

- React/Vite teacher and student application.
- Teacher dashboard, lesson editor, components, and lesson workflows.
- Student subject, lesson, learning, and progress views.
- Shared UI components and app shell.

## Evidence Gates

- Backend tests with `./run-tests.sh`.
- Frontend typecheck with `pnpm run typecheck`.
- Frontend build with `pnpm run build`.
- Diff hygiene with `git diff --check`.

## Current Production Focus

1. Stabilize KTP import/parsing.
2. Stabilize LLM generation and provider error behavior.
3. Harden API contracts and user-facing error states.
4. Add smoke coverage for critical teacher and student workflows.
5. Add deployment, monitoring, and rollback gates only after local evidence is stable.
