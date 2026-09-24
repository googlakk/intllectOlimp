-- Hot-path indexes for course lists, student lesson manifests, and media hydration.
-- Existing migrations already cover sections(subject_id, sort_order),
-- topics(section_id, sort_order), progress(student_id, topic_id), and
-- student_topic_access(student_id, topic_id).

create index if not exists subjects_grade_name_idx
  on public.subjects (grade, name, id);

create index if not exists generated_lessons_published_topic_idx
  on public.generated_lessons (topic_id)
  where status = 'published';

create index if not exists generated_lessons_active_version_idx
  on public.generated_lessons (active_version_id)
  where active_version_id is not null;

create index if not exists lesson_versions_ready_lesson_idx
  on public.lesson_versions (lesson_id, version_number desc)
  where status in ('ready', 'published');

create index if not exists lesson_assets_ready_version_scene_idx
  on public.lesson_assets (lesson_version_id, scene_id, created_at desc)
  where status = 'ready';
