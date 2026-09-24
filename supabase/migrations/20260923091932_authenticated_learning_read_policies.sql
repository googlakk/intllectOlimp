create or replace function public.current_student_id()
returns integer language sql stable security definer set search_path = public
as $$ select student_id from public.profiles where id = public.current_profile_id() $$;

create or replace function public.current_teacher_id()
returns integer language sql stable security definer set search_path = public
as $$ select teacher_id from public.profiles where id = public.current_profile_id() $$;

create or replace function public.can_access_student(target_student_id integer)
returns boolean language sql stable security definer set search_path = public
as $$
  select case public.current_profile_role()
    when 'admin' then true
    when 'student' then target_student_id = public.current_student_id()
    when 'teacher' then exists (
      select 1 from public.classroom_students cs
      join public.classroom_teachers ct on ct.classroom_id = cs.classroom_id
      where cs.student_id = target_student_id and cs.left_at is null
        and ct.teacher_id = public.current_teacher_id()
    )
    else false
  end
$$;

create or replace function public.current_student_grade()
returns integer language sql stable security definer set search_path = public
as $$ select grade from public.students where id = public.current_student_id() $$;

grant select on public.subjects, public.sections, public.topics,
  public.generated_lessons, public.lesson_versions, public.students,
  public.teachers, public.progress, public.student_skill_mastery,
  public.student_topic_access, public.warp_gate_events to authenticated;

create policy "subjects follow verified role and grade"
on public.subjects for select to authenticated
using (
  public.current_profile_role() in ('admin', 'teacher')
  or (public.current_profile_role() = 'student' and grade <= public.current_student_grade())
);

create policy "sections follow visible subjects"
on public.sections for select to authenticated
using (exists (select 1 from public.subjects s where s.id = sections.subject_id));

create policy "topics follow visible sections"
on public.topics for select to authenticated
using (exists (select 1 from public.sections s where s.id = topics.section_id));

create policy "published lessons are visible to students"
on public.generated_lessons for select to authenticated
using (
  public.current_profile_role() in ('admin', 'teacher')
  or (
    public.current_profile_role() = 'student' and status = 'published'
    and exists (
      select 1 from public.topics t
      join public.sections sec on sec.id = t.section_id
      join public.subjects sub on sub.id = sec.subject_id
      where t.id = generated_lessons.topic_id
    )
  )
);

create policy "lesson versions follow visible lessons"
on public.lesson_versions for select to authenticated
using (exists (select 1 from public.generated_lessons gl where gl.id = lesson_versions.lesson_id));

create policy "student rows are scoped by classroom"
on public.students for select to authenticated
using (public.can_access_student(id));

create policy "teachers see self and admins see all"
on public.teachers for select to authenticated
using (public.current_profile_role() = 'admin' or id = public.current_teacher_id());

create policy "progress is scoped by student"
on public.progress for select to authenticated
using (public.can_access_student(student_id));

create policy "skill mastery is scoped by student"
on public.student_skill_mastery for select to authenticated
using (public.can_access_student(student_id));

create policy "topic access is scoped by student"
on public.student_topic_access for select to authenticated
using (public.can_access_student(student_id));

create policy "warp gates are scoped by student"
on public.warp_gate_events for select to authenticated
using (public.can_access_student(student_id));

-- Writes remain backend-only: authenticated receives SELECT but no mutation grants.
