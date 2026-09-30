-- Apply manually: creation/assignment of subject teachers records this audit event.
-- Preserve every previously allowed event. No account, lesson or student rows change.
BEGIN;

ALTER TABLE public.account_events
  DROP CONSTRAINT IF EXISTS account_events_event_type_check;

ALTER TABLE public.account_events
  ADD CONSTRAINT account_events_event_type_check CHECK (event_type IN (
    'account_created', 'password_reset_issued', 'password_changed',
    'account_blocked', 'account_restored', 'classroom_assigned',
    'classroom_unassigned', 'classroom_transferred',
    'teacher_subjects_assigned'
  ));

COMMIT;
