--
-- Rollback Migration DEV-16: Populate Interview Templates
--
-- Purpose: Reverse the seeding of interview_templates and
--          interview_template_roles tables.
-- Date: 2026-03-09
-- Module: app/interview
-- Ticket: DEV-16
--

-- Remove template-role mappings first (FK dependency)
DELETE FROM public.interview_template_roles
WHERE interview_template_id IN (1, 2, 3, 4, 5, 6);

-- Remove seeded templates
DELETE FROM public.interview_templates
WHERE id IN (1, 2, 3, 4, 5, 6);

-- Reset sequence
SELECT setval('public.interview_templates_id_seq', 1, false);
