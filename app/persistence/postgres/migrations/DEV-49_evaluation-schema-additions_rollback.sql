-- Rollback: DEV-49 — Evaluation schema additions
-- Branch: feature/DEV-49-complete-all-pending-modules
-- Date: 2026-03-04

-- ============================================================
-- DOWN MIGRATION
-- ============================================================

-- 7. Drop scoring_version index
DROP INDEX IF EXISTS idx_evaluations_scoring_version;

-- 6. Drop evaluated_by index
DROP INDEX IF EXISTS idx_evaluations_evaluated_by;

-- 5. Drop partial unique on interview_results
DROP INDEX IF EXISTS uq_interview_results_submission_current;

-- 4. Restore simple UNIQUE constraint on evaluations
DROP INDEX IF EXISTS uq_evaluations_exchange_final;

-- Re-add simple UNIQUE (WARNING: will fail if multiple rows per exchange exist)
-- Only run if data has been cleaned: DELETE FROM evaluations WHERE is_final = false;
ALTER TABLE public.evaluations
    ADD CONSTRAINT evaluations_interview_exchange_id_key
    UNIQUE (interview_exchange_id);

-- 3. Drop max_score column from evaluation_dimension_scores
ALTER TABLE public.evaluation_dimension_scores
    DROP COLUMN IF EXISTS max_score;

-- 2. Drop scoring_version column from evaluations
ALTER TABLE public.evaluations
    DROP COLUMN IF EXISTS scoring_version;

-- 1. Drop evaluated_by column and FK from evaluations
ALTER TABLE public.evaluations
    DROP CONSTRAINT IF EXISTS evaluations_evaluated_by_fkey;

ALTER TABLE public.evaluations
    DROP COLUMN IF EXISTS evaluated_by;
