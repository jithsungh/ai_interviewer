-- Migration: DEV-49 — Evaluation schema additions for persistence layer
-- Branch: feature/DEV-49-complete-all-pending-modules
-- Date: 2026-03-04
--
-- Purpose:
--   Add missing columns to evaluations and evaluation_dimension_scores tables
--   required by the scoring service and evaluation API. Replace the simple
--   UNIQUE constraint on evaluations.interview_exchange_id with a partial unique
--   index to support the re-evaluation (versioning) flow. Add partial unique
--   index on interview_results for is_current enforcement.
--
-- Justification:
--   - Scoring service writes evaluated_by (human evaluator tracking) and
--     scoring_version (algorithm version audit trail) — both are required by
--     REQUIREMENTS.md and the existing scoring/service.py implementation.
--   - evaluation_dimension_scores.max_score is written by scoring service
--     for each dimension to preserve the rubric's max score at evaluation time.
--   - The simple UNIQUE(interview_exchange_id) prevents the re-evaluation flow
--     (force_rescore) which marks old evaluation is_final=false and creates a new
--     one. A partial unique WHERE is_final = true preserves the "one final
--     evaluation per exchange" invariant while allowing historical versions.
--   - interview_results partial unique on (interview_submission_id) WHERE
--     is_current = true enforces the "one current result per submission" invariant
--     at database level.
--
-- Proof of safety:
--   - No SRS invariant broken: "one exchange = one evaluation" still enforced
--     via partial unique on is_final = true
--   - No ERD invariant violated: additive columns, constraint relaxation is
--     strictly controlled (partial unique is more correct)
--   - No existing module breaks: all new columns are nullable, existing data
--     remains valid
--   - No data corruption risk: ALTER TABLE ADD COLUMN is safe, index changes
--     are idempotent
--   - No performance regression: partial indexes are smaller than full indexes

-- ============================================================
-- UP MIGRATION
-- ============================================================

-- 1. Add evaluated_by column to evaluations (human evaluator FK)
ALTER TABLE public.evaluations
    ADD COLUMN IF NOT EXISTS evaluated_by bigint;

-- Add FK constraint for evaluated_by → users(id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'evaluations_evaluated_by_fkey'
    ) THEN
        ALTER TABLE public.evaluations
            ADD CONSTRAINT evaluations_evaluated_by_fkey
            FOREIGN KEY (evaluated_by) REFERENCES public.users(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 2. Add scoring_version column to evaluations (algorithm version tracking)
ALTER TABLE public.evaluations
    ADD COLUMN IF NOT EXISTS scoring_version text;

-- 3. Add max_score column to evaluation_dimension_scores
ALTER TABLE public.evaluation_dimension_scores
    ADD COLUMN IF NOT EXISTS max_score numeric;

-- 4. Replace simple UNIQUE with partial unique to support re-evaluation
--    The existing simple UNIQUE prevents having multiple rows per exchange
--    (including non-final historical versions). The partial unique preserves
--    the "one final evaluation per exchange" invariant.
ALTER TABLE public.evaluations
    DROP CONSTRAINT IF EXISTS evaluations_interview_exchange_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_evaluations_exchange_final
    ON public.evaluations (interview_exchange_id)
    WHERE is_final = true;

-- 5. Add partial unique on interview_results for is_current enforcement
CREATE UNIQUE INDEX IF NOT EXISTS uq_interview_results_submission_current
    ON public.interview_results (interview_submission_id)
    WHERE is_current = true;

-- 6. Add index on evaluated_by for evaluator lookup
CREATE INDEX IF NOT EXISTS idx_evaluations_evaluated_by
    ON public.evaluations (evaluated_by)
    WHERE evaluated_by IS NOT NULL;

-- 7. Add index on scoring_version for version-based queries
CREATE INDEX IF NOT EXISTS idx_evaluations_scoring_version
    ON public.evaluations (scoring_version)
    WHERE scoring_version IS NOT NULL;
