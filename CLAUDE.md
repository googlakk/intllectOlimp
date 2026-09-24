# Start here — Intellect Platform

Read `AGENTS.md`, then `docs/CLAUDE_HANDOFF.md` and `docs/RUN_IN_ANOTHER_ENVIRONMENT.md` before editing.
These files describe existing work, open risks and the user's current priority. The working tree contains extensive valuable uncommitted and untracked work; preserve it. Do not reset/clean/stash/checkout over it or assume a Git clone contains the current implementation.

Current goal: improve the EXISTING material constructor, generator, lesson experience and component library to produce visual, exploratory lessons. The user does not want more disconnected sample pages or a fixed seven-scene template. Deadline was described as tomorrow on 2026-09-24; confirm relevance from the current conversation, do not assume unlimited redesign time.

Keep auth, permissions, publication versions, attempts and real course data intact. No automatic live migrations, curriculum repairs, bulk generation, publication, deployment or destructive cleanup. Backend startup itself runs compatibility schema changes; know which database is configured before starting in a different environment. Never print `.env`, credentials, access tokens or database connection strings.

Use pnpm (Node 22 in `.nvmrc`), Python >=3.11, existing libraries and architecture boundaries. Establish a fresh baseline before changing code. Report real checks and distinguish visual samples from the production learning flow. Consult handoff for precise paths, verification history and next steps.
