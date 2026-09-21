# Intellect Platform Architecture Guide

This guide turns the quality requirements into day-to-day development rules.
Keep it short, practical, and updated when the architecture changes.

## Backend Shape

- `backend/routes`: FastAPI adapters only. Routes own request models,
  dependency injection, file upload objects, query parameters, and translating
  service errors into `HTTPException`.
- `backend/services`: application use cases. Services may use SQLAlchemy,
  domain modules, and provider adapters, but must not import FastAPI.
- `backend/ktp`, `backend/objectives`, `backend/llm`, `backend/ai`: domain
  logic and external-provider boundaries. Prefer deterministic functions and
  injectable adapters for tests.
- `backend/schema_compat.py`: temporary runtime compatibility for existing
  local databases. New schema changes should move toward migrations instead of
  growing startup logic.

### Backend Error Rule

Services raise application errors such as `LessonServiceError`,
`ProgressServiceError`, `AuthServiceError`, `ComponentRegistryError`,
`KtpParseError`, or `KtpPersistenceError`. Each error exposes stable
`status_code` and `detail` fields by inheriting from `backend/errors.py`
`ApplicationError`. Routes translate those errors to HTTP with
`routes.http_errors.raise_http_error`.

This keeps services testable without FastAPI and makes CLI/background use cases
possible later.

### Adding A Backend Feature

1. Add or extend a service use case first.
2. Keep deterministic calculations in domain modules.
3. Add a route that only parses HTTP input and maps service errors.
4. Add focused service/domain tests.
5. Run `./run-tests.sh` and `pnpm run check:architecture`. For broad changes,
   run `pnpm run check:quality`.

## Frontend Shape

- `src/lib/api`: low-level HTTP client, endpoint functions, and DTO types.
- `src/features/<domain>`: feature model functions, hooks, and reusable views
  for a workflow.
- `src/pages`: route composition only. A page can own navigation and top-level
  state, but large rendering/model logic should move into `features`.
  Keep model/data/helper `.ts` files out of `src/pages`; move them to
  `src/features/<domain>`. Route pages should stay under 220 lines.
- `src/components/blocks`: lesson block renderers. Dynamic block content should
  flow through typed boundary contracts instead of spreading `any`.
- `src/components/ui`: generic UI primitives only.

### Lesson Block Classification

Keep lesson block category rules in `src/lib/lessonBlocks.ts`. UI renderers,
lesson progress, and lesson quality checks should call named classifiers such as
`isAssessmentBlock` or `isObjectiveAssessmentBlock` instead of carrying local
component-name arrays. This prevents progress, publishing checks, and rendering
from drifting apart.

### Frontend Typing Rule

Avoid TypeScript `any` in pages, features, lesson blocks, and layout. If data is
dynamic, use `unknown`, DTO types, or a small boundary type, then narrow it near
the use site. HTML values such as `step="any"` are fine.

### Frontend Cache Rule

Pages should not hard-code React Query keys in `setQueryData` or
`invalidateQueries`. Put cache key shapes and invalidation policy in
`src/features/<domain>` workflow/model helpers, then call those helpers from the
page or feature hook. This keeps route components thin and makes cache behavior
testable.

### Adding A Frontend Feature

1. Put API contracts in `src/lib/api/types.ts` or the relevant endpoint module.
2. Put data shaping and workflow calculations in `src/features/<domain>`.
3. Keep page components as composition shells.
4. Add targeted Vitest coverage for model/data-shaping code.
5. Run `pnpm run typecheck`, `pnpm run test:run`,
   `pnpm --filter ./artifacts/intellect-learning-platform run build`, and
   `pnpm run check:architecture`. For broad changes, run
   `pnpm run check:quality`.

## Automated Guardrails

Run:

```bash
pnpm run check:architecture
```

The guardrail currently enforces:

- no FastAPI imports or `HTTPException` inside `backend/services`;
- no application/service error classes inheriting directly from `Exception` in
  `backend/services` or `backend/ktp`; use `ApplicationError`;
- no manual `HTTPException(status_code=exc.status_code, detail=exc.detail)`
  mapping in routes; use `routes.http_errors.raise_http_error`;
- no explicit TypeScript `any` in frontend pages, features, lesson blocks, or
  layout, except literal HTML values such as `step="any"`.
- no `.ts` files inside `src/pages`; page-adjacent model/data/helper code
  belongs in `src/features/<domain>`.
- no local lesson assessment component lists outside `src/lib/lessonBlocks.ts`;
  use named classifiers from that module.
- no literal React Query cache keys inside route pages; use feature
  workflow/model helpers for cache policy.
- no route page over 220 lines.

When a new architectural rule becomes stable and easy to check, add it to
`scripts/src/check-architecture.mjs`.

## Full Quality Gate

Run:

```bash
pnpm run check:quality
```

This wraps backend tests, architecture guardrails, frontend tests, TypeScript
typecheck, and production frontend build.
