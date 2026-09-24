alter table public.account_events
  drop constraint if exists account_events_event_type_check;

alter table public.account_events
  add constraint account_events_event_type_check check (event_type in (
    'account_created', 'password_reset_issued', 'password_changed',
    'account_blocked', 'account_restored', 'classroom_assigned',
    'classroom_unassigned', 'classroom_transferred'
  ));
