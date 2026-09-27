# Start here — Intellect Platform

Read `docs/CLAUDE_HANDOFF.md` first (current state, owner rules, deploy, file map, open issues), then `AGENTS.md`,
`docs/ARCHITECTURE_GUIDE.md` and `docs/QUALITY_REQUIREMENTS.md`. The owner writes in Russian — answer in Russian.

Non-negotiable:
- Deploy to production only after the owner says «выкладывай» / «выложи». Railway is NOT connected to GitHub:
  deploy with `railway up --ci --service web` from this folder (see handoff §2). Pushing `main` alone changes nothing on prod.
- Local backend and production share ONE Supabase database. Your direct reads of it are blocked; use Railway logs, tests and code.
- Paid generation (HeyGen video, textbook OCR, bulk lesson generation) only with the owner's consent.
- Migrations: write SQL into `supabase/migrations/`, the owner applies it. New tables go into a separate model base
  so startup `create_all` does not create them.
- Never print `.env`, credentials, tokens or connection strings. Variable names are fine, values are not.
- Keep auth, permissions, publication versions, attempts and real course data intact. No `git reset --hard`,
  `git clean` or deleting untracked files without asking.
- Backend has no `--reload`: after backend changes, tell the owner to restart the local server.
- Work in steps (Discover → Plan → Implement → Review → Verify → Report), one commit per step.
  Gates: backend `pytest`, `pnpm run check:architecture`, `pnpm run check:quality`.

Use pnpm (Node 22, `.nvmrc`), Python ≥ 3.11, existing libraries and architecture boundaries.
Report real checks; say plainly what was not verified.
