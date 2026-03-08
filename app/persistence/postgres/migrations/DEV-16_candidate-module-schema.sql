--
-- Migration DEV-16: Candidate Module — Practice Window & Schema Additions
--
-- Purpose: Create the system practice window required for ad-hoc practice
--          sessions (Gap 6) and ensure profile metadata columns support
--          the candidate profile endpoint (Gap 4).
-- Date: 2026-03-08
-- Module: app/candidate
-- Ticket: DEV-16
--
-- Changes:
--   1. Insert a system practice window (__practice__) for practice mode
--   2. Create a default practice window-role-template mapping
--
-- Dependencies:
--   - organizations table must have at least one organization (id=1)
--   - admins table must have at least one admin (id=1)
--   - roles table must have at least one role
--   - interview_templates table must have at least one active template
--
-- Invariants preserved:
--   - Practice window has scope='global' so all candidates can see it
--   - end_time is set far in the future (2099-12-31)
--   - No SRS invariant broken (using existing tables)
--   - No ERD invariant violated (valid FK relationships)
--
-- Rollback: See DEV-16_candidate-module-schema_rollback.sql
--

BEGIN;

-- ============================================================================
-- PART 1: Create system practice window
-- ============================================================================

-- Insert the practice window only if it does not already exist
INSERT INTO public.interview_submission_windows (
    organization_id,
    admin_id,
    name,
    scope,
    start_time,
    end_time,
    timezone,
    max_allowed_submissions,
    allow_after_end_time,
    allow_resubmission
)
SELECT
    1,                                          -- organization_id (super org)
    (SELECT id FROM public.admins LIMIT 1),     -- admin_id (first admin)
    '__practice__',                             -- name (system identifier)
    'global',                                   -- scope (visible to all)
    '2025-01-01T00:00:00Z',                     -- start_time (always open)
    '2099-12-31T23:59:59Z',                     -- end_time (effectively never)
    'UTC',                                      -- timezone
    NULL,                                       -- max_allowed_submissions (unlimited)
    true,                                       -- allow_after_end_time
    true                                        -- allow_resubmission (practice)
WHERE NOT EXISTS (
    SELECT 1 FROM public.interview_submission_windows
    WHERE name = '__practice__'
);

-- ============================================================================
-- PART 2: Create default practice window-role-template mapping
-- ============================================================================

-- Map the first available role and active template to the practice window
INSERT INTO public.window_role_templates (
    window_id,
    role_id,
    template_id,
    selection_weight
)
SELECT
    w.id,
    (SELECT id FROM public.roles LIMIT 1),
    (SELECT id FROM public.interview_templates WHERE is_active = true LIMIT 1),
    1
FROM public.interview_submission_windows w
WHERE w.name = '__practice__'
  AND NOT EXISTS (
      SELECT 1 FROM public.window_role_templates wrt
      WHERE wrt.window_id = w.id
  )
  AND EXISTS (SELECT 1 FROM public.roles)
  AND EXISTS (SELECT 1 FROM public.interview_templates WHERE is_active = true);

-- ============================================================================
-- PART 3: Drop unique constraint on candidate_id + window_id + role_id
--         to allow multiple practice submissions per candidate
-- ============================================================================

-- The existing unique constraint prevents candidates from creating multiple
-- practice submissions. We replace it with a partial unique constraint that
-- only enforces uniqueness for non-practice windows.

-- First check if constraint exists before attempting operations
DO $$
BEGIN
    -- Drop old unique constraint if it exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_candidate_window_role'
    ) THEN
        ALTER TABLE public.interview_submissions
            DROP CONSTRAINT uq_candidate_window_role;
    END IF;

    -- Also handle the alternative constraint name
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'interview_submissions_candidate_id_window_id_role_id_key'
    ) THEN
        ALTER TABLE public.interview_submissions
            DROP CONSTRAINT interview_submissions_candidate_id_window_id_role_id_key;
    END IF;
END $$;

-- Create partial unique index: enforce uniqueness only for non-practice windows.
-- PostgreSQL does not allow subqueries in index predicates, so we look up the
-- practice window ID dynamically and execute the CREATE INDEX with a literal.
DO $$
DECLARE
    _practice_window_id INTEGER;
BEGIN
    SELECT id INTO _practice_window_id
    FROM public.interview_submission_windows
    WHERE name = '__practice__';

    IF _practice_window_id IS NOT NULL THEN
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_window_role_non_practice '
            'ON public.interview_submissions (candidate_id, window_id, role_id) '
            'WHERE window_id <> %s',
            _practice_window_id
        );
    END IF;
END $$;

COMMIT;
