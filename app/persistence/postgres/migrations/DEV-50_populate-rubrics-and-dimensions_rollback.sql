--
-- Rollback Migration DEV-50: Populate Rubrics and Rubric Dimensions
--
-- Purpose: Reverse the seeding of rubrics, rubric_dimensions, and
--          interview_template_rubrics tables.
-- Date: 2026-03-09
-- Module: app/evaluation
-- Ticket: DEV-50
--

-- Remove template-rubric mappings first (FK dependency)
DELETE FROM public.interview_template_rubrics
WHERE id IN (1, 2, 3, 4, 5, 6);

-- Remove rubric dimensions (FK dependency on rubrics)
DELETE FROM public.rubric_dimensions
WHERE id IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17);

-- Remove rubrics
DELETE FROM public.rubrics
WHERE id IN (1, 2);

-- Reset sequences
SELECT setval('public.interview_template_rubrics_id_seq', 1, false);
SELECT setval('public.rubric_dimensions_id_seq', 1, false);
SELECT setval('public.rubrics_id_seq', 1, false);
