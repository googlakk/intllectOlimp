-- Keep every enrollment period while still allowing a student to return to a
-- previous classroom. The partial unique index created by the identity
-- migration remains the single source of truth for one active class.

alter table public.classroom_students
  drop constraint if exists classroom_students_classroom_id_student_id_key;

create index if not exists classroom_students_student_history_idx
  on public.classroom_students (student_id, enrolled_at desc);
