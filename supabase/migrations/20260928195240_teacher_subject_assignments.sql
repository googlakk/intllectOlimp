-- Apply manually before deploying subject-teacher access.
-- Existing classroom memberships are NOT converted into broad subject permissions.
-- After applying, assign subjects explicitly to each teacher in /admin/accounts.
BEGIN;

CREATE TABLE IF NOT EXISTS public.teacher_subject_assignments (
    teacher_id integer NOT NULL REFERENCES public.teachers(id) ON DELETE CASCADE,
    subject_id integer NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    organization_id bigint NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    assigned_by_profile_id bigint REFERENCES public.profiles(id) ON DELETE SET NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (teacher_id, subject_id)
);

CREATE INDEX IF NOT EXISTS teacher_subject_assignments_org_idx
    ON public.teacher_subject_assignments (organization_id, teacher_id);
CREATE INDEX IF NOT EXISTS teacher_subject_assignments_subject_idx
    ON public.teacher_subject_assignments (subject_id);

ALTER TABLE public.teacher_subject_assignments ENABLE ROW LEVEL SECURITY;
-- FastAPI validates administrator and organization scope. No browser Data API access.
REVOKE ALL ON public.teacher_subject_assignments FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.teacher_subject_assignments TO service_role;

COMMIT;
