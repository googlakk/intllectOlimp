# Lesson generation without a long HTTP request

The editor starts a job with `POST /api/lessons/generate/start` and polls
`GET /api/lessons/generate/status/{job_id}?topic_id=N`. Both routes require
administrator or assigned teacher access to the topic. Successful status includes
the current draft and its authoritative version document.

Each explicit start carries a UUID request ID. A topic row lock prevents
overlapping jobs; the current job marker lives in the existing lesson metadata.
No schema change is required. Existing materials and published versions remain
available while the provider runs. Completion checks the job identity, deadline,
draft and published version identities, and topic archival before saving.

The worker owns an independent database session and releases its transaction
before calling the provider. Jobs have a 15-minute execution limit. Status reads
can be retried without starting another provider request. The old synchronous
generation endpoint retains its lesson response and shares overlap protection.

Background workers belong to the server process. A server restart interrupts
work; the durable marker becomes failed after its deadline, or earlier when
cancellation can be recorded. Jobs are never restarted automatically. A new
manual start is required after failure. An expired or replaced worker cannot
overwrite a newer draft.

Verification uses fake providers and sessions. Live database access and paid
generation are unnecessary for these checks. Production deployment still
requires the owner's authorization under `AGENTS.md`.
