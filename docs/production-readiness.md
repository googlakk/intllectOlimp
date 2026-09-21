# Production Readiness Checklist

## Required Before Merge-Ready

- Backend tests pass.
- Frontend typecheck passes.
- Frontend build passes.
- `git diff --check` passes.
- Changed behavior has targeted tests or explicit evidence.
- LLM changes include schema, failure, and abstention handling.
- UI changes include browser evidence when they affect visible workflows.

## Required Before Staging

- Environment variables documented.
- Database setup and migration path documented.
- API health endpoint available.
- Critical workflows have smoke tests.
- Logs are useful without exposing secrets.

## Required Before Production

- Deployment target selected.
- Rollback command documented and tested.
- Monitoring configured.
- Error tracking configured.
- Secrets stored outside the repository.
- Human approval required for production delivery.
