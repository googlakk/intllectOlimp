-- Keep RLS helper functions outside the exposed public schema. They remain
-- executable from policies, but cannot be called as PostgREST RPC endpoints.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.current_profile_id()
returns bigint language sql stable security definer set search_path = public, pg_temp
as $$ select id from public.profiles where auth_user_id = auth.uid() and status = 'active' limit 1 $$;

create or replace function private.current_profile_role()
returns text language sql stable security definer set search_path = public, pg_temp
as $$ select role from public.profiles where auth_user_id = auth.uid() and status = 'active' limit 1 $$;

create or replace function private.current_student_id()
returns integer language sql stable security definer set search_path = public, pg_temp
as $$ select student_id from public.profiles where id = private.current_profile_id() $$;

create or replace function private.current_teacher_id()
returns integer language sql stable security definer set search_path = public, pg_temp
as $$ select teacher_id from public.profiles where id = private.current_profile_id() $$;

create or replace function private.current_student_grade()
returns integer language sql stable security definer set search_path = public, pg_temp
as $$ select grade from public.students where id = private.current_student_id() $$;

create or replace function private.can_access_classroom(target_classroom_id bigint)
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$
  select case private.current_profile_role()
    when 'admin' then true
    when 'teacher' then exists (
      select 1 from public.classroom_teachers ct
      join public.profiles p on p.teacher_id = ct.teacher_id
      where ct.classroom_id = target_classroom_id and p.id = private.current_profile_id()
    )
    when 'student' then exists (
      select 1 from public.classroom_students cs
      join public.profiles p on p.student_id = cs.student_id
      where cs.classroom_id = target_classroom_id and cs.left_at is null
        and p.id = private.current_profile_id()
    )
    else false
  end
$$;

create or replace function private.can_access_student(target_student_id integer)
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$
  select case private.current_profile_role()
    when 'admin' then true
    when 'student' then target_student_id = private.current_student_id()
    when 'teacher' then exists (
      select 1 from public.classroom_students cs
      join public.classroom_teachers ct on ct.classroom_id = cs.classroom_id
      where cs.student_id = target_student_id and cs.left_at is null
        and ct.teacher_id = private.current_teacher_id()
    )
    else false
  end
$$;

grant execute on function private.current_profile_id() to authenticated;
grant execute on function private.current_profile_role() to authenticated;
grant execute on function private.current_student_id() to authenticated;
grant execute on function private.current_teacher_id() to authenticated;
grant execute on function private.current_student_grade() to authenticated;
grant execute on function private.can_access_classroom(bigint) to authenticated;
grant execute on function private.can_access_student(integer) to authenticated;

alter policy "organization members can read organization" on public.organizations
using (id = (select organization_id from public.profiles where id = private.current_profile_id()));

alter policy "profiles are scoped to self admin or assigned teacher" on public.profiles
using (
  id = private.current_profile_id()
  or private.current_profile_role() = 'admin'
  or (
    private.current_profile_role() = 'teacher' and role = 'student' and exists (
      select 1 from public.classroom_students cs
      join public.classroom_teachers ct on ct.classroom_id = cs.classroom_id
      join public.profiles viewer on viewer.teacher_id = ct.teacher_id
      where cs.student_id = profiles.student_id and cs.left_at is null
        and viewer.id = private.current_profile_id()
    )
  )
);

alter policy "classrooms are visible to assigned members" on public.classrooms
using (private.can_access_classroom(id));
alter policy "classroom teachers are visible to classroom members" on public.classroom_teachers
using (private.can_access_classroom(classroom_id));
alter policy "classroom students are visible to classroom members" on public.classroom_students
using (private.can_access_classroom(classroom_id));

alter policy "subjects follow verified role and grade" on public.subjects
using (
  private.current_profile_role() in ('admin', 'teacher')
  or (private.current_profile_role() = 'student' and grade <= private.current_student_grade())
);
alter policy "published lessons are visible to students" on public.generated_lessons
using (
  private.current_profile_role() in ('admin', 'teacher')
  or (
    private.current_profile_role() = 'student' and status = 'published'
    and exists (
      select 1 from public.topics t
      join public.sections sec on sec.id = t.section_id
      join public.subjects sub on sub.id = sec.subject_id
      where t.id = generated_lessons.topic_id
    )
  )
);
alter policy "student rows are scoped by classroom" on public.students
using (private.can_access_student(id));
alter policy "teachers see self and admins see all" on public.teachers
using (private.current_profile_role() = 'admin' or id = private.current_teacher_id());
alter policy "progress is scoped by student" on public.progress
using (private.can_access_student(student_id));
alter policy "skill mastery is scoped by student" on public.student_skill_mastery
using (private.can_access_student(student_id));
alter policy "topic access is scoped by student" on public.student_topic_access
using (private.can_access_student(student_id));
alter policy "warp gates are scoped by student" on public.warp_gate_events
using (private.can_access_student(student_id));

drop function public.can_access_student(integer);
drop function public.current_student_grade();
drop function public.current_student_id();
drop function public.current_teacher_id();
drop function public.can_access_classroom(bigint);
drop function public.current_profile_role();
drop function public.current_profile_id();

create index if not exists account_events_actor_profile_idx
  on public.account_events (actor_profile_id);
create index if not exists classroom_students_enrolled_by_profile_idx
  on public.classroom_students (enrolled_by_profile_id);
create index if not exists classroom_teachers_assigned_by_profile_idx
  on public.classroom_teachers (assigned_by_profile_id);
create index if not exists classrooms_created_by_profile_idx
  on public.classrooms (created_by_profile_id);
create index if not exists profiles_created_by_profile_idx
  on public.profiles (created_by_profile_id);
