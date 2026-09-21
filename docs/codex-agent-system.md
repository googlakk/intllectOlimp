# Codex Agent System

This workspace uses a lightweight, harness-like Codex setup for developing Intellect Platform without restarting a broad refactoring phase.

## What Is Installed

- `AGENTS.md`: persistent project instructions loaded by Codex at task start.
- `.codex/config.toml`: project-level Codex agent settings.
- `.codex/agents/intellect-*.toml`: focused subagent profiles for planning, implementation, UI, prompts, QA, and review.
- `.codex/config.toml`: project MCP wiring for OpenAI Developer Docs, Context7, Linear, and Figma.
- `factory.yaml`: optional Pi Graph Factory control-plane configuration for heavier guarded runs.
- `docs/agent-factory.md`: operational notes for the external factory.

## Tooling Surface

Active local layer:

- OpenAI Developer Docs MCP: required source-of-truth docs for OpenAI API, Agents, Codex, and MCP work.
- Context7 MCP: required current library/framework docs during implementation.
- Linear MCP: optional issue context and delivery planning when a Linear workflow is used.
- Figma MCP: optional design context for UI work when a Figma source is available.
- Browser / node_repl runtime tools: browser smoke checks and UI inspection.

Recommended plugin layer:

- GitHub: PR, issue, CI, and publish flow integration.
- Codex Security: security scans and security investigation lanes.
- OpenAI Developers: deeper OpenAI API, Agents API, and ChatGPT Apps development support.

Supabase, Stitch, and Pencil/Antigravity MCP servers may exist globally on this machine, but they are explicitly disabled in this project because Intellect Platform does not currently depend on them.

## Default Flow

For ordinary development, stay inside Codex and follow:

1. Ask `intellect_planner` or use parent-agent planning for unclear work.
2. Use `intellect_product`, `intellect_design`, or `intellect_prompt` for focused implementation.
3. Use `intellect_qa` for evidence and noisy test triage.
4. Use `intellect_reviewer` before considering the work complete.

For small changes, the parent agent can do all steps directly, but it still follows the same gates.

## Suggested Prompts

```text
Разработай следующую продуктовую фичу. Сначала пусть intellect_planner ограничит скоуп, потом intellect_product реализует, intellect_qa проверит, intellect_reviewer даст независимый review.
```

```text
Проверь этот UI flow. Пусть intellect_design посмотрит фронтенд и браузерное поведение, intellect_qa соберет evidence, а intellect_reviewer проверит риски.
```

```text
Нужно изменить LLM-поведение. Пусть intellect_prompt предложит схему и eval cases, потом реализуем минимально и прогоним targeted checks.
```

## External Factory

Use Pi Graph Factory when the work is large enough to justify isolated worktrees and independent lanes:

```bash
cd /Users/intellectmac/AI-Factory/pi-graph-factory
.venv/bin/python scripts/factory.py start \
  --repo /Users/intellectmac/Documents/Олимпиадники/intellect-platform \
  --config /Users/intellectmac/Documents/Олимпиадники/intellect-platform/factory.yaml \
  --request-file /path/to/request.md
```

Factory runs must stop at `merge_ready` unless the user explicitly asks for merge or delivery.

## Quality Rule

The system is successful only when each task ends with:

- changed files summary;
- evidence commands and results;
- known risks or explicit "no known residual risk";
- no unrelated refactoring.

Run the local harness preflight after changing agent configuration:

```bash
pnpm run check:agent-system
```
