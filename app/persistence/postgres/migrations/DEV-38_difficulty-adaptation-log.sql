-- ============================================================================
-- Migration: DEV-38 — difficulty_adaptation_log table
-- Description: Creates audit table for difficulty adaptation decisions (FR-4.4)
-- Author: DEV-38
-- Date: 2026-03-01
--
-- Justification:
--   The question/selection module must log every difficulty adaptation
--   decision with full inputs and outputs for auditability (FR-4.4, NFR-11).
--   This table is INSERT-ONLY (immutable audit trail).
--
-- Invariants preserved:
--   - SRS FR-4.4: Log all adaptation decisions with inputs and outcomes
--   - No existing table modified
--   - No foreign key to interview_submissions yet (interview module not implemented)
--     — submission_id stored as BIGINT for forward compatibility
--   - INSERT-ONLY: No UPDATE/DELETE expected
--
-- Performance:
--   - Index on submission_id for per-interview queries
--   - Index on created_at for time-range queries
--   - Minimal write overhead (one INSERT per question selection)
--
-- Rollback: See DEV-38_difficulty-adaptation-log_rollback.sql
-- ============================================================================

-- UP

CREATE TABLE IF NOT EXISTS public.difficulty_adaptation_log (
    id              BIGSERIAL   PRIMARY KEY,
    submission_id   BIGINT      NOT NULL,
    exchange_sequence_order INTEGER NOT NULL,

    -- Previous state
    previous_difficulty VARCHAR(20),
    previous_score      NUMERIC(5, 2),
    previous_question_id BIGINT,

    -- Adaptation logic
    adaptation_rule     VARCHAR(50) NOT NULL,
    threshold_up        NUMERIC(5, 2),
    threshold_down      NUMERIC(5, 2),
    max_difficulty_jump INTEGER     NOT NULL DEFAULT 1,

    -- Output
    next_difficulty     VARCHAR(20) NOT NULL,
    adaptation_reason   TEXT        NOT NULL,
    difficulty_changed  BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Audit
    decided_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    rule_version        VARCHAR(20) NOT NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE public.difficulty_adaptation_log OWNER TO jithsungh;

COMMENT ON TABLE public.difficulty_adaptation_log IS
    'Immutable audit log for difficulty adaptation decisions (FR-4.4). INSERT-ONLY.';

CREATE INDEX IF NOT EXISTS idx_adaptation_log_submission
    ON public.difficulty_adaptation_log (submission_id);

CREATE INDEX IF NOT EXISTS idx_adaptation_log_created_at
    ON public.difficulty_adaptation_log (created_at);
