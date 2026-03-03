-- Rollback: DEV-46 — Remove proctoring risk columns from interview_submissions
-- Branch: feature/DEV-46-implement-interview-realtime

-- ============================================================
-- DOWN MIGRATION
-- ============================================================

-- 1. Drop indexes
DROP INDEX IF EXISTS idx_submissions_proctoring_flagged;
DROP INDEX IF EXISTS idx_proctoring_events_submission_occurred;
DROP INDEX IF EXISTS idx_proctoring_events_occurred;

-- 2. Drop columns from interview_submissions
ALTER TABLE public.interview_submissions
    DROP COLUMN IF EXISTS proctoring_reviewed;

ALTER TABLE public.interview_submissions
    DROP COLUMN IF EXISTS proctoring_flagged;

ALTER TABLE public.interview_submissions
    DROP COLUMN IF EXISTS proctoring_risk_classification;

ALTER TABLE public.interview_submissions
    DROP COLUMN IF EXISTS proctoring_risk_score;
