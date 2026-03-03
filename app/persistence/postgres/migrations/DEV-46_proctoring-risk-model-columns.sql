-- Migration: DEV-46 — Add proctoring risk columns to interview_submissions
-- Branch: feature/DEV-46-implement-interview-realtime
-- Date: 2026-03-03
--
-- Purpose:
--   Add columns to interview_submissions for persisting proctoring risk data
--   (risk score, classification, flagged, reviewed) as required by risk_model module.
--   Add missing indexes on proctoring_events for efficient risk computation.
--
-- Justification:
--   - REQUIREMENTS.md specifies risk score stored on submission for audit trail
--   - ProctoringAdjuster in evaluation reads from submission record
--   - Admin review queue queries flagged submissions
--   - No SRS invariant broken (advisory-only columns, no auto-fail logic)
--   - No ERD invariant violated (additive columns, no FK changes)
--   - No existing module breaks (all columns nullable/defaulted)
--   - No data corruption risk (ALTER TABLE ADD COLUMN is safe)
--   - No performance regression (indexed where needed)

-- ============================================================
-- UP MIGRATION
-- ============================================================

-- 1. Add proctoring risk columns to interview_submissions
ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS proctoring_risk_score NUMERIC(6, 2) DEFAULT 0.0;

ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS proctoring_risk_classification VARCHAR(20);

ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS proctoring_flagged BOOLEAN DEFAULT FALSE;

ALTER TABLE public.interview_submissions
    ADD COLUMN IF NOT EXISTS proctoring_reviewed BOOLEAN DEFAULT FALSE;

-- 2. Add missing index on proctoring_events.occurred_at (for time-range queries)
CREATE INDEX IF NOT EXISTS idx_proctoring_events_occurred
    ON public.proctoring_events (occurred_at);

-- 3. Add composite index for efficient risk computation queries
CREATE INDEX IF NOT EXISTS idx_proctoring_events_submission_occurred
    ON public.proctoring_events (interview_submission_id, occurred_at);

-- 4. Add index on flagged submissions for admin review queue
CREATE INDEX IF NOT EXISTS idx_submissions_proctoring_flagged
    ON public.interview_submissions (proctoring_flagged)
    WHERE proctoring_flagged = TRUE;
