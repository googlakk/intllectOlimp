# Agentic Development Cycle Audit

Date: 2026-09-21

## Verified Tool Surface

Required and enabled for this project:

- OpenAI Developer Docs MCP: official OpenAI, Codex, Agents, and MCP documentation.
- Context7 MCP: current framework and library documentation.

Optional and enabled for this project:

- Linear MCP: planning and issue context.
- Figma MCP: design context for UI work.
- Browser/node runtime tooling: browser smoke and UI inspection through Codex runtime tools.

Explicitly disabled for this project:

- Supabase MCP servers.
- Stitch MCP.
- Pencil/Antigravity MCP.

Reason: Intellect Platform currently does not depend on these services, so keeping them enabled would expose unnecessary account/data surfaces to agents.

## Harness Safety

- Root project instructions live in `AGENTS.md`.
- Project Codex config lives in `.codex/config.toml`.
- Focused subagents live in `.codex/agents`.
- `factory.yaml` now declares sandbox and approval policy intent for each lane.
- External Pi Graph Factory checkout is pinned in documentation to:

```text
ab902f7c02a7f859e1c7cbcced2c0677d02c3d54
```

## Agent Cycle Exercised

1. Parent agent inspected official Codex documentation and current local configuration.
2. Parent agent configured project MCP, subagent profiles, and harness gates.
3. Independent reviewer subagent audited the harness layer and produced findings.
4. Parent agent implemented the required fixes.
5. QA gates were run locally.

## Evidence

Passed:

```bash
pnpm run check:agent-system
git diff --check
pnpm run check:architecture
pnpm run test:run
pnpm run typecheck
./run-tests.sh
pnpm --filter ./artifacts/intellect-learning-platform run build
pnpm run check:quality
```

Observed:

- `codex mcp list` shows OpenAI Developer Docs, Context7, Linear, and Figma enabled.
- `codex mcp list` shows Supabase and Stitch disabled inside this trusted project.
- `scripts/src/capture-browser-evidence.mjs` writes `evidence/factory/browser-receipt.json`.

## Plugin Layer

Installed and verified:

- GitHub (`plugin_connector_1p_1a69035c238881919c4190932b2df699`): PR, issue, CI, and publishing workflows. Current state: `installed: true`.
- Codex Security (`Plugin_1e648473be9c8191a91ac3947151af55`): security scans and investigation lanes. Current state: `installed: true`.
- OpenAI Developers (`plugin_connector_1p_32dba5a7095c8191adca04ee30276304`): deeper OpenAI API, Agents API, and ChatGPT Apps workflows. Current state: `installed: true`.

Current callable surface notes:

- Codex Security MCP tools are available and were used for a real diff scan.
- OpenAI Developers skills are available for OpenAI API, Agents API, and Apps SDK work.
- GitHub is installed; in this session, PR/diff workflows are exposed through the Linear diff connector surface rather than a separate `github` tool namespace.

## Codex Security Scan

Completed scan:

```text
8892d816-bcec-49fb-a378-987ab9cec3f7
```

Readable report:

```text
/private/var/folders/y2/yhsg1p1d5y5dsg7qhylxyc900000gn/T/codex-security-scans-LFQbwz/intellect-platform/ba4a356cbf18ca227805ff4cc137e8d2935f2e60_20260921T173501Z_pvs9etwn/report.md
```

Result:

- Findings: 0.
- Reviewed: harness/tooling layer.
- Coverage: partial, because unrelated backend/frontend product-refactor files were intentionally deferred to a separate security pass.

## Remaining Manual Trigger

For UI/design lanes, start the app and run:

```bash
HARNESS_VISUAL_URL=http://127.0.0.1:3000 node scripts/src/capture-browser-evidence.mjs
```

Then capture desktop and mobile screenshots through Codex browser tooling into:

```text
evidence/factory/desktop.png
evidence/factory/mobile.png
```
