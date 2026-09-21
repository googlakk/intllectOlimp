# Agent Factory Contract

This project is connected to the local Pi Graph Factory checkout at:

```text
/Users/intellectmac/AI-Factory/pi-graph-factory
```

Pinned checkout:

```text
ab902f7c02a7f859e1c7cbcced2c0677d02c3d54
```

The factory is a control plane for guarded agent work. It plans changes, runs
implementation lanes in isolated Git worktrees, records evidence, performs
independent review, and stops at `merge_ready` by default.

## Safety Defaults

- Automatic merge is disabled: `merge.apply: false`.
- Automatic delivery is disabled: `delivery.enabled: false`.
- Planner and reviewer lanes are declared read-only with `approval_policy:
  on-request`; implementation lanes are declared `workspace-write` with
  approval prompts for escalated actions.
- Graphify enrichment is disabled for the first local setup, so no Baseten or
  Pi semantic-enrichment credential is required for the first trial.
- Evidence gates include backend tests, frontend typecheck, frontend build with
  required Vite environment variables, agent-system preflight, and
  `git diff --check`.
- Agents must preserve existing behavior unless a test or product contract
  proves a bug.

## First Production Refactor Lane

Use the first factory run for a bounded backend lane:

```text
Stabilize the KTP parsing backend pipeline for production.

Goals:
- Make validation, assembly, and API error reporting explicit and tested.
- Preserve the current public API unless tests prove a bug.
- Add or update backend tests for PDF/DOCX parsing and invalid input.
- Do not change frontend unless API contract handling requires it.
- Evidence must include backend pytest, frontend typecheck, and frontend build.
```

## Local Commands

Before a local factory run, verify the Codex/harness layer:

```bash
pnpm run check:agent-system
```

For UI/design lanes, make visual evidence explicit:

```bash
HARNESS_VISUAL_URL=http://127.0.0.1:3000 node scripts/src/capture-browser-evidence.mjs
```

Then use the Codex browser tooling to save:

```text
evidence/factory/desktop.png
evidence/factory/mobile.png
```

From the Pi Graph Factory checkout:

```bash
cd /Users/intellectmac/AI-Factory/pi-graph-factory

.venv/bin/python scripts/factory.py start \
  --repo /Users/intellectmac/Documents/Олимпиадники/intellect-platform \
  --config /Users/intellectmac/Documents/Олимпиадники/intellect-platform/factory.yaml \
  --request-file /path/to/request.md
```

Inspect a run:

```bash
.venv/bin/python scripts/factory.py status \
  --repo /Users/intellectmac/Documents/Олимпиадники/intellect-platform
```

Open the read-only dashboard:

```bash
.venv/bin/python scripts/dashboard.py \
  --root /Users/intellectmac/Documents/Олимпиадники/intellect-platform \
  --open
```

If macOS blocks opening the browser from a sandboxed terminal, run the same
command manually in Terminal or omit `--open` and visit the printed localhost
URL.

## Credentials

For unattended or long production-refactor runs, prefer API billing keys with
budget limits. CLI subscriptions can work for interactive local trials, but API
keys are easier to control in CI and server environments.

Recommended first setup:

- Codex / OpenAI API key for planner, product, prompt, QA, and review lanes.
- Claude Code login or Anthropic API key for the design lane.
- GitHub token later, when PR/issue automation is added.
