# Beta authentication runbook

## Access model

- There is no public registration screen or public account-creation API.
- The beta administrator creates teachers and assigns them to classes.
- Administrators and assigned teachers create students. Every student must have one active class.
- New teacher and student accounts receive a temporary password and must replace it on first login.
- The Supabase service-role key is used only by FastAPI. Never expose it through a `VITE_*` variable or the frontend bundle.

## One-time Supabase setup

1. In Supabase Dashboard open **Authentication -> Providers -> Email**.
2. Disable **Allow new users to sign up** while leaving email/password sign-in enabled. This hosted setting is required before production use.
3. Copy the project service-role/secret key into the backend `.env` as `SUPABASE_SERVICE_ROLE_KEY`.
4. Set a unique `BETA_ADMIN_PASSWORD` with at least 12 characters. Keep this value out of git.

The database trigger rejects external signup identities. Internal `@users.intellect.local` identities are not sufficient for application access: every authenticated user must also have an active, backend-created row in `profiles`. This preserves the authorization boundary even before the hosted signup switch is disabled.

## Create the beta administrator

From the project root:

```bash
cd backend
../.venv/bin/python bootstrap_beta_admin.py
```

The command is idempotent: rerunning it does not create a second administrator.

## Acceptance check

1. Sign in as the beta administrator.
2. Create a class and a teacher, then assign the teacher to that class.
3. Sign in as the teacher, replace the temporary password, and create a student in the assigned class.
4. Sign in as the student, replace the temporary password, and confirm that only subjects and lessons available to that grade are visible.
5. Block the student and confirm that the next authenticated request is denied; restore the account and confirm access returns.

Account creation, class assignment, transfer, blocking, restoration, and password reset are recorded in `account_events`.
