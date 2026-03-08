--
-- Rollback Migration DEV-16: Candidate Module — Practice Window & Schema Additions
--
-- Reverts: DEV-16_candidate-module-schema.sql
-- Date: 2026-03-08
-- Module: app/candidate
-- Ticket: DEV-16
--

BEGIN;

-- ============================================================================
-- PART 1: Drop the partial unique index
-- ============================================================================

DROP INDEX IF EXISTS public.uq_candidate_window_role_non_practice;

-- ============================================================================
-- PART 2: Restore original unique constraint
-- ============================================================================

-- Restore the original unique constraint (may fail if duplicate data exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'interview_submissions_candidate_id_window_id_role_id_key'
    ) THEN
        ALTER TABLE public.interview_submissions
            ADD CONSTRAINT interview_submissions_candidate_id_window_id_role_id_key
            UNIQUE (candidate_id, window_id, role_id);
    END IF;
END $$;

-- ============================================================================
-- PART 3: Remove practice window-role-template mappings
-- ============================================================================

DELETE FROM public.window_role_templates
WHERE window_id IN (
    SELECT id FROM public.interview_submission_windows
    WHERE name = '__practice__'
);

-- ============================================================================
-- PART 4: Remove the practice window
-- ============================================================================

DELETE FROM public.interview_submission_windows
WHERE name = '__practice__';

COMMIT;
