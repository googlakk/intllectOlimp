create or replace function private.current_organization_id()
returns bigint language sql stable security definer set search_path = public, pg_temp
as $$ select organization_id from public.profiles where id = private.current_profile_id() $$;

create or replace function private.current_teacher_max_grade()
returns integer language sql stable security definer set search_path = public, pg_temp
as $$
  select max(c.grade)::integer
  from public.classrooms c
  join public.classroom_teachers ct on ct.classroom_id = c.id
  where ct.teacher_id = private.current_teacher_id() and c.status = 'active'
$$;

grant execute on function private.current_organization_id() to authenticated;
grant execute on function private.current_teacher_max_grade() to authenticated;

create or replace function private.can_access_classroom(target_classroom_id bigint)
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$
  select case private.current_profile_role()
    when 'admin' then exists (
      select 1 from public.classrooms c
      where c.id = target_classroom_id
        and c.organization_id = private.current_organization_id()
    )
    when 'teacher' then exists (
      select 1 from public.classroom_teachers ct
      join public.profiles p on p.teacher_id = ct.teacher_id
      join public.classrooms c on c.id = ct.classroom_id
      where ct.classroom_id = target_classroom_id and p.id = private.current_profile_id()
        and c.organization_id = private.current_organization_id()
    )
    when 'student' then exists (
      select 1 from public.classroom_students cs
      join public.profiles p on p.student_id = cs.student_id
      join public.classrooms c on c.id = cs.classroom_id
      where cs.classroom_id = target_classroom_id and cs.left_at is null
        and p.id = private.current_profile_id()
        and c.organization_id = private.current_organization_id()
    )
    else false
  end
$$;

create or replace function private.can_access_student(target_student_id integer)
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$
  select case private.current_profile_role()
    when 'admin' then exists (
      select 1 from public.profiles p
      where p.student_id = target_student_id
        and p.organization_id = private.current_organization_id()
    )
    when 'student' then target_student_id = private.current_student_id()
    when 'teacher' then exists (
      select 1 from public.classroom_students cs
      join public.classroom_teachers ct on ct.classroom_id = cs.classroom_id
      join public.classrooms c on c.id = cs.classroom_id
      where cs.student_id = target_student_id and cs.left_at is null
        and ct.teacher_id = private.current_teacher_id()
        and c.organization_id = private.current_organization_id()
    )
    else false
  end
$$;

alter policy "organization members can read organization" on public.organizations
using (id = private.current_organization_id());

alter policy "profiles are scoped to self admin or assigned teacher" on public.profiles
using (
  id = private.current_profile_id()
  or (
    private.current_profile_role() = 'admin'
    and organization_id = private.current_organization_id()
  )
  or (
    private.current_profile_role() = 'teacher'
    and organization_id = private.current_organization_id()
    and role = 'student'
    and exists (
      select 1 from public.classroom_students cs
      join public.classroom_teachers ct on ct.classroom_id = cs.classroom_id
      join public.profiles viewer on viewer.teacher_id = ct.teacher_id
      where cs.student_id = profiles.student_id and cs.left_at is null
        and viewer.id = private.current_profile_id()
    )
  )
);

alter policy "subjects follow verified role and grade" on public.subjects
using (
  private.current_profile_role() = 'admin'
  or (
    private.current_profile_role() = 'teacher'
    and grade <= private.current_teacher_max_grade()
  )
  or (
    private.current_profile_role() = 'student'
    and grade <= private.current_student_grade()
  )
);

alter policy "published lessons are visible to students" on public.generated_lessons
using (
  private.current_profile_role() = 'admin'
  or (
    private.current_profile_role() = 'teacher'
    and exists (
      select 1 from public.topics t
      join public.sections sec on sec.id = t.section_id
      join public.subjects sub on sub.id = sec.subject_id
      where t.id = generated_lessons.topic_id
    )
  )
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

alter policy "teachers see self and admins see all" on public.teachers
using (
  id = private.current_teacher_id()
  or (
    private.current_profile_role() = 'admin'
    and exists (
      select 1 from public.profiles p
      where p.teacher_id = teachers.id
        and p.organization_id = private.current_organization_id()
    )
  )
);
