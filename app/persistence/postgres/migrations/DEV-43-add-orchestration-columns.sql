-- ============================================================================
-- Migration: DEV-43 — Add orchestration columns to interview_submissions
-- ============================================================================
--
-- Adds two columns required by the orchestration module:
--
-- 1. current_exchange_sequence (INTEGER, DEFAULT 0, NOT NULL)
--    Tracks the most recently completed exchange sequence for a submission.
--    Updated by the orchestration layer after each exchange is persisted.
--    Used for:
--      - Resolving the next question from the template snapshot
--      - Progress percentage calculation
--      - Race condition validation (expected sequence check)
--
-- 2. template_structure_snapshot (JSONB, NULLABLE)
--    Frozen template structure captured at interview creation time.
--    Orchestration reads from this snapshot ONLY — never from live template.
--    Ensures template changes after interview start do NOT affect in-progress
--    interviews (Architecture Invariant: Template Immutability).
--    NULL until populated by the admin/session module at submission creation.
--
-- Proof of safety:
--   - No SRS invariant broken: immutability enforced at application layer
--   - No ERD invariant violated: no FK changes, no constraint removals
--   - No existing module breaks: both columns have safe defaults (0 / NULL)
--   - No data corruption risk: additive-only change, no data mutation
--   - No performance regression: no new indexes required (progress is looked
--     up by PK, snapshot is read per-submission)
--
-- Forward-only. Idempotent (IF NOT EXISTS / safe ADD COLUMN pattern).
-- ============================================================================

-- UP

-- Add current_exchange_sequence column
-- Tracks progress: 0 = no exchanges yet, N = last completed sequence_order
ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS current_exchange_sequence INTEGER NOT NULL DEFAULT 0;

-- Add template_structure_snapshot column
-- JSONB snapshot of template structure frozen at creation time
-- Expected shape:
-- {
--   "template_id": <int>,
--   "template_name": <str>,
--   "sections": [
--     {
--       "section_name": <str>,
--       "question_count": <int>,
--       "question_ids": [<int>, ...]
--     }, ...
--   ],
--   "total_questions": <int>
-- }
ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS template_structure_snapshot JSONB;

-- Add CHECK constraint: current_exchange_sequence must be non-negative
-- Using DO block for idempotency (skip if constraint already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_submissions_exchange_sequence_non_negative'
    ) THEN
        ALTER TABLE public.interview_submissions
            ADD CONSTRAINT ck_submissions_exchange_sequence_non_negative
            CHECK (current_exchange_sequence >= 0);
    END IF;
END $$;

-- ============================================================================
-- DOWN (manual rollback if needed)
-- ============================================================================
-- ALTER TABLE public.interview_submissions DROP COLUMN IF EXISTS current_exchange_sequence;
-- ALTER TABLE public.interview_submissions DROP COLUMN IF EXISTS template_structure_snapshot;
-- ALTER TABLE public.interview_submissions DROP CONSTRAINT IF EXISTS ck_submissions_exchange_sequence_non_negative;
