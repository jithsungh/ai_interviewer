--
-- Migration DEV-51: Create Practice Window
--
-- Purpose: Seed a special "__practice__" interview_submission_window that
--          never expires (end_time = year 9999) and allows unlimited
--          resubmissions. Map all 6 standard templates × all 7 roles
--          to this window via window_role_templates.
-- Date: 2026-03-09
-- Module: app/candidate
-- Ticket: DEV-51
--
-- Changes:
--   1. Insert a "__practice__" window into interview_submission_windows
--      with scope='global', end_time far in the future, allow_resubmission=true,
--      no max_allowed_submissions limit.
--   2. Insert 42 rows into window_role_templates (6 templates × 7 roles).
--
-- Invariants preserved:
--   - Dynamically looks up admin_id from organization_id=1
--   - Template IDs 1–6, role IDs 1–7 from prior DEV-16 migrations
--   - check constraint end_time > start_time satisfied
--   - Idempotent via ON CONFLICT DO NOTHING
--
-- Rollback: See DEV-51_create-practice-window_rollback.sql
--

-- ============================================================================
-- PART 1: Insert the practice window
-- ============================================================================

INSERT INTO public.interview_submission_windows
    (organization_id, admin_id, name, scope, start_time, end_time,
     timezone, max_allowed_submissions, allow_after_end_time, allow_resubmission)
SELECT
     1,                                                          -- Super Organization
     (SELECT id FROM admins WHERE organization_id = 1 LIMIT 1), -- first org-1 admin
     '__practice__',                                             -- sentinel name
     'global',                                                   -- accessible to everyone
     '2000-01-01 00:00:00+00',                                   -- started long ago
     '9999-12-31 23:59:59+00',                                   -- effectively never expires
     'UTC',                                                      -- UTC timezone
     NULL,                                                       -- no submission limit
     true,                                                       -- allow after end time
     true                                                        -- allow repeated submissions
WHERE NOT EXISTS (
    SELECT 1 FROM public.interview_submission_windows WHERE name = '__practice__'
);

-- ============================================================================
-- PART 2: Map all 6 templates to all 7 roles for the practice window
-- ============================================================================
-- Template 1 = DSA Fundamentals
-- Template 2 = System Design
-- Template 3 = Backend Engineering
-- Template 4 = Frontend Development
-- Template 5 = Behavioral Interview
-- Template 6 = DevOps & Cloud
-- Roles 1–7 = Backend, Frontend, Full Stack, DevOps, Data, Mobile, ML

INSERT INTO public.window_role_templates (window_id, role_id, template_id)
SELECT pw.id, r.role_id, r.template_id
FROM (SELECT id FROM interview_submission_windows WHERE name = '__practice__') pw
CROSS JOIN (VALUES
    -- DSA Fundamentals (template=1) × all roles
    (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1),
    -- System Design (template=2) × all roles
    (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2),
    -- Backend Engineering (template=3) × all roles
    (1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3),
    -- Frontend Development (template=4) × all roles
    (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4),
    -- Behavioral Interview (template=5) × all roles
    (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5), (7, 5),
    -- DevOps & Cloud (template=6) × all roles
    (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (7, 6)
) AS r(role_id, template_id)
ON CONFLICT (window_id, role_id, template_id) DO NOTHING;

-- ============================================================================
-- PART 3: Update sequence so future windows get id > 1
-- ============================================================================

SELECT setval('public.interview_submission_windows_id_seq',
              GREATEST(1, (SELECT MAX(id) FROM public.interview_submission_windows)),
              true);
