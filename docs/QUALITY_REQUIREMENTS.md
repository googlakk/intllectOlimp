# Intellect Platform Quality Requirements

This document defines the engineering standard for refactoring Intellect Platform.
Every refactor should preserve behavior, improve one explicit quality attribute,
and leave the system easier to verify than before.

For day-to-day placement rules and automated guardrails, see
[`ARCHITECTURE_GUIDE.md`](./ARCHITECTURE_GUIDE.md).

## Current Architecture Context

- Backend: FastAPI, async SQLAlchemy, Pydantic, pytest.
- Frontend: Vite, React, TypeScript, TanStack Query, Radix UI components.
- Domain: learning platform with subjects, KTP import, generated lessons,
  lesson quality checks, student progress, and teacher workflows.
- Repository shape: workspace root with Python backend and generated/artifact
  frontend app under `artifacts/intellect-learning-platform`.

## Quality Principles

1. Behavior first.
   Refactoring must not change user-visible behavior unless the change is
   intentional, documented, and covered by tests.

2. Small reversible steps.
   Prefer narrow changes that can be reviewed, tested, and reverted
   independently. Avoid broad rewrites while tests are still thin.

3. Explicit boundaries.
   API routes should orchestrate HTTP concerns. Business rules should live in
   services or domain modules. Persistence details should remain behind
   repositories or clearly named data-access helpers.

4. Typed contracts.
   Backend request/response shapes and frontend API types should be explicit,
   shared in naming, and validated at system boundaries.

5. Deterministic core, isolated side effects.
   Lesson quality checks, KTP parsing, objective mapping, and mastery logic
   should be testable as pure functions where possible. Database, network, file,
   and LLM calls should be isolated behind small interfaces.

6. Clear error semantics.
   Domain failures, validation failures, missing resources, provider failures,
   and unexpected errors should produce distinct errors and HTTP responses.
   Services should raise domain/application errors with stable `status_code`
   and `detail` fields. FastAPI `HTTPException` belongs in routes, where
   service errors are translated into HTTP responses.

7. Observable and debuggable.
   Critical flows should expose useful logs or structured diagnostics without
   leaking secrets or noisy implementation details.

8. Secure by default.
   Secrets must come from environment variables, CORS/auth behavior must be
   explicit, and generated content must be validated before publication.

9. Accessible and ergonomic UI.
   UI changes should preserve keyboard access, loading states, empty states,
   error states, and responsive layouts.

10. Consistent style over cleverness.
    Follow existing project patterns unless they conflict with these
    requirements. Introduce abstractions only when they remove real duplication
    or clarify ownership.

## Backend Requirements

### Layers

- `routes/`: FastAPI routers, request parsing, response selection, dependency
  injection, and HTTP status mapping only.
- `services/`: application use cases such as generating lessons, publishing
  lessons, importing KTP, updating progress, and building dashboards.
- `repositories/` or data-access helpers: database queries and persistence.
- Domain modules such as `objectives`, `ktp`, and `llm`: deterministic rules,
  adapters, and provider contracts.
- Upload/parse workflows should expose one application boundary per user
  action. For KTP import, routes own `UploadFile` and HTTP error mapping,
  while `ktp.parsing` owns file validation, extraction, mapping, and parse
  diagnostics.

### Rules

- Route handlers should stay short enough to read as orchestration.
- Repeated query patterns should move out of routers.
- Pydantic models should define API input and output contracts.
- SQLAlchemy models should not become the public API contract by accident.
- Startup code must not accumulate complex schema migration logic. If schema
  changes continue, add a real migration path before expanding runtime ALTER
  statements.
- External providers must be called through interfaces that are easy to fake in
  tests.
- Domain validation should return structured results or domain exceptions, not
  loosely shaped dictionaries when consumers need stable fields.
- New service modules should not import FastAPI unless the module itself is an
  HTTP adapter. Existing services that still do should be migrated one domain at
  a time with route-level error mapping and focused tests.

## Frontend Requirements

### Layers

- `lib/api`: low-level HTTP client and endpoint functions.
- `features/<domain>`: domain hooks, typed view models, and feature components
  when a page grows beyond simple composition.
- `pages`: route-level composition and navigation.
- `components/ui`: generic design-system components only.
- `components/blocks`: lesson block renderers and block-specific interactions.

### Rules

- Large pages should be split by workflow, not by arbitrary visual fragments.
- API hooks should be close to feature ownership instead of one ever-growing
  global file.
- Types should distinguish server DTOs from UI state where they diverge.
- Mutations should invalidate or update the relevant TanStack Query cache.
- UI must cover loading, error, empty, permission/role, and success states.
- Components should avoid hidden global assumptions about role, current user,
  or selected subject.

## Testing Requirements

Each refactor should choose the smallest useful verification set:

- Pure domain logic: focused unit tests.
- Route/service behavior: pytest tests with mocked providers or test database
  fixtures.
- Frontend data shaping: TypeScript checks and targeted component/hook tests if
  the project adds a test runner.
- Full user workflow risk: browser smoke test or manual verification note.

Preferred full gate before handing off a cross-cutting refactor:

```bash
pnpm run check:quality
```

Minimum gate before completing a backend refactor:

```bash
./run-tests.sh
pnpm run check:architecture
```

Minimum gate before completing a frontend refactor:

```bash
pnpm run typecheck
pnpm --filter ./artifacts/intellect-learning-platform run build
```

If a gate cannot be run, the final note must say why and what risk remains.

## Definition of Done

A refactor is complete when:

- The intended behavior is preserved or the behavior change is explicitly
  documented.
- New or changed boundaries have clear names and ownership.
- The touched code has focused tests or a clear verification path.
- Errors remain user-meaningful and developer-debuggable.
- No unrelated user changes are reverted.
- Dead code and duplicate paths introduced by the refactor are removed.
- The final response states what changed and which verification commands ran.
  For broad refactors, prefer reporting `pnpm run check:quality`.

## Refactoring Order

1. Establish safety net.
   Run existing tests and type checks, record current failures, and avoid
   changing behavior until the baseline is understood.

2. Backend lesson flow.
   Extract lesson generation, quality normalization, publish/unpublish, and
   serialization out of `routes/lessons.py` into a service boundary.

3. Backend startup and schema hygiene.
   Reduce schema mutation logic inside `main.py`; introduce a migration path or
   a contained compatibility module.

4. KTP import pipeline.
   Make extraction, column mapping, validation, assembly, and persistence a
   clear pipeline with typed intermediate results. Keep route handlers out of
   parsing details; parse/upload services should be testable with fake
   extractors, mappers, and sessions.

5. LLM provider boundary.
   Keep provider selection, HTTP retries/timeouts, and model metadata behind
   stable interfaces and fakes for tests.

6. Frontend API boundary.
   Split `src/lib/api.ts` into an HTTP client, domain endpoint modules, and
   feature hooks while preserving existing imports through temporary barrels if
   needed.

7. Frontend page decomposition.
   Refactor large teacher/student pages into feature modules with explicit
   loading, error, empty, and role states.

8. Final cleanup.
   Remove compatibility shims, document the architecture, and ensure all gates
   are green.

## Review Checklist

Use this checklist before accepting each change:

- Does this change reduce coupling or only move code around?
- Is there one obvious place to change this behavior next time?
- Are inputs and outputs typed at the boundary?
- Are side effects isolated from deterministic rules?
- Would a failing provider, missing database row, or malformed lesson block
  produce a clear error?
- Did tests cover the behavior that could have been broken?
- Did the UI keep loading, empty, error, and mobile states intact?
