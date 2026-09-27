# Intellect Platform Codex Operating Guide

## Mission

Build Intellect Platform through small, evidence-backed product increments. The refactoring foundation is considered sufficient; do not start a new broad refactoring phase unless the user explicitly asks for one.

## Development Contract

- Treat `docs/QUALITY_REQUIREMENTS.md` and `docs/ARCHITECTURE_GUIDE.md` as the quality baseline.
- Keep changes scoped to the current product request.
- Preserve public API behavior unless a test, product requirement, or documented contract proves it should change.
- Prefer existing architecture boundaries: FastAPI routes delegate to services; application errors inherit from `ApplicationError`; route HTTP mapping goes through `backend/routes/http_errors.py`.
- Keep React route pages thin. Move feature logic into `src/features`, shared API clients into `src/lib/api`, and lesson block logic through `src/lib/lessonBlocks.ts`.
- Avoid explicit TypeScript `any` in app code unless an existing tool or browser API forces it and the reason is local and obvious.
- Do not add production dependencies without a concrete need.

## Agentic Workflow

Use a harness-like flow for non-trivial work:

1. Discover: map the affected files, contracts, tests, and user-facing behavior.
2. Plan: define the smallest product increment and acceptance checks.
3. Implement: make focused edits with tests or targeted verification.
4. Review: inspect for correctness, regressions, security, architecture drift, and missing tests.
5. Verify: run the narrowest reliable checks first, then `pnpm run check:quality` when the blast radius justifies it.
6. Report: summarize changed files, evidence, and remaining risks.

Use subagents when the task benefits from parallel exploration, independent review, UI verification, or noisy test triage. Keep the parent agent responsible for final decisions.

## Tooling Surface

Required project-local MCP/tools:

- `openaiDeveloperDocs`: official OpenAI/Codex/API documentation.
- `context7`: current library and framework documentation.
- `linear`: issue context and planning when Linear is part of the workflow.
- `figma`: design context for UI work when a Figma source is available.

Available global runtime tools:

- browser and `node_repl` for UI smoke checks.
- The product uses Supabase (Postgres, Auth, Storage). Production and local development share one database — see `docs/CLAUDE_HANDOFF.md` §1–2 before touching data, migrations or deploys.

Recommended plugin layer, when installed by the user:

- GitHub for PR, issue, CI, and publish flows.
- Codex Security for security scans and investigations.
- OpenAI Developers for deeper OpenAI API, Agents API, and ChatGPT Apps work.

## Quality Gates

Default evidence ladder:

- Agent harness/config change: `pnpm run check:agent-system`.
- Backend-only change: relevant `pytest` target, then `pnpm run check:architecture`.
- Frontend-only change: targeted frontend tests or typecheck, then browser smoke when UI behavior changes.
- Cross-stack change: backend tests, frontend typecheck, architecture check, and build.
- Release-like change: `pnpm run check:quality`.

If a check cannot run, state the reason and what evidence replaced it.

## Harness / Factory

`factory.yaml` and `docs/agent-factory.md` describe the external Pi Graph Factory lane. It is optional for day-to-day Codex work, but use its roles and gates as the local operating model:

- planner defines bounded work.
- product implements backend and domain behavior.
- design owns UI, interaction, accessibility, and browser evidence.
- prompt owns LLM prompts, schemas, abstention behavior, and evals.
- qa owns repeatable verification and evidence capture.
- reviewer performs independent risk review.

Do not auto-merge or auto-deliver. Commit each finished step; deploy only after the owner says «выкладывай» (Railway via `railway up`, see `docs/CLAUDE_HANDOFF.md` §2).
