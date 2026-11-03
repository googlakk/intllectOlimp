-- Apply before deploying code that reads Progress.response_details.
-- Existing attempt snapshots remain valid: missing keys mean answers were not captured.
BEGIN;
ALTER TABLE public.progress
    ADD COLUMN IF NOT EXISTS response_details jsonb NOT NULL DEFAULT '{}'::jsonb;
COMMENT ON COLUMN public.progress.response_details IS
    'Latest submitted answer per original lesson block/question; grading remains in answers/responses.';
COMMIT;
