-- Migration: main-coding-execution-schema
-- Date: 2026-02-28
-- Description: Schema additions required by coding/execution module
--
-- Changes:
--   1. Add 'memory_exceeded' to code_execution_status enum
--      Reason: Execution REQUIREMENTS §4 defines ExecutionStatus with memory_exceeded
--      as a terminal state for OOM-killed submissions. DB enum is missing this value.
--
--   2. Add executed_at column to code_submissions
--      Reason: Tracks when execution completed (distinct from submitted_at).
--      Required by execution REQUIREMENTS §5 (Atomic Status Update).
--
--   3. Add UNIQUE constraint on code_submissions.interview_exchange_id
--      Reason: SRS invariant — one submission per exchange. persistence/REQUIREMENTS §6
--      ("One Submission Per Exchange"). Non-unique INDEX already exists; replaced by UNIQUE.
--
--   4. Add exit_code column to code_execution_results
--      Reason: Required to store process exit codes for failure classification
--      (124=timeout, 137=OOM, non-zero=runtime error). execution/REQUIREMENTS §5.
--
--   5. Add UNIQUE constraint on code_execution_results(code_submission_id, test_case_id)
--      Reason: Prevents duplicate test results per submission. Enables idempotent
--      re-execution. persistence/REQUIREMENTS §6 ("One Result Per Test Case").
--
--   6. Add index on code_submissions(execution_status)
--      Reason: Optimizes pending queue queries (LIST PENDING). persistence/REQUIREMENTS §11.
--
-- Safety:
--   - All changes are additive (ADD COLUMN, ADD VALUE, ADD CONSTRAINT, CREATE INDEX)
--   - New columns are nullable — no impact on existing rows
--   - No existing data modified or deleted
--   - No existing constraints removed
--   - Tables are currently empty (module not yet live)
--
-- Proof of no breakage:
--   - No SRS invariant broken (adding constraints strengthens invariants)
--   - No ERD invariant violated (all FK relationships preserved)
--   - No existing module breaks (auth, admin do not reference these tables)
--   - No data corruption risk (additive changes on empty tables)
--   - No performance regression (indexes improve query performance)

-- ============================================================================
-- UP
-- ============================================================================

-- 1. Add 'memory_exceeded' to code_execution_status enum
-- Note: ADD VALUE cannot run inside a transaction block in PostgreSQL < 12.
-- In PostgreSQL 12+, IF NOT EXISTS makes this idempotent.
ALTER TYPE public.code_execution_status ADD VALUE IF NOT EXISTS 'memory_exceeded';

-- 2. Add executed_at column to code_submissions
ALTER TABLE public.code_submissions
    ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE;

-- 3. Add UNIQUE constraint on code_submissions.interview_exchange_id
-- Drop the existing non-unique index first (superseded by unique constraint)
DROP INDEX IF EXISTS public.idx_code_submissions_exchange;

ALTER TABLE ONLY public.code_submissions
    ADD CONSTRAINT code_submissions_interview_exchange_id_key
    UNIQUE (interview_exchange_id);

-- 4. Add exit_code column to code_execution_results
ALTER TABLE public.code_execution_results
    ADD COLUMN IF NOT EXISTS exit_code INTEGER;

-- 5. Add UNIQUE constraint on (code_submission_id, test_case_id)
ALTER TABLE ONLY public.code_execution_results
    ADD CONSTRAINT uq_submission_test_case
    UNIQUE (code_submission_id, test_case_id);

-- 6. Add index on execution_status for pending queue queries
CREATE INDEX IF NOT EXISTS idx_code_submissions_status
    ON public.code_submissions USING btree (execution_status);

-- ============================================================================
-- DOWN (manual rollback if needed)
-- ============================================================================
-- WARNING: ALTER TYPE ... DROP VALUE is not supported in PostgreSQL.
-- To remove 'memory_exceeded', a full type recreation is required.
-- This is intentionally omitted to avoid data loss risk.
--
-- ALTER TABLE public.code_submissions DROP COLUMN IF EXISTS executed_at;
-- ALTER TABLE public.code_execution_results DROP COLUMN IF EXISTS exit_code;
-- ALTER TABLE ONLY public.code_submissions DROP CONSTRAINT IF EXISTS code_submissions_interview_exchange_id_key;
-- ALTER TABLE ONLY public.code_execution_results DROP CONSTRAINT IF EXISTS uq_submission_test_case;
-- DROP INDEX IF EXISTS public.idx_code_submissions_status;
-- CREATE INDEX idx_code_submissions_exchange ON public.code_submissions USING btree (interview_exchange_id);
