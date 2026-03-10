--
-- Migration: Disable Coding Problems in Interview Templates
--
-- Purpose: Disable the coding_round section in all interview templates
--          to skip code execution and evaluation temporarily
-- Date: 2026-03-09
--
-- Changes:
--   1. Set coding_round.enabled = false for all templates
--   2. Set coding_round.weight = 0 for all templates
--   3. Adjust section_weights to compensate (redistribute to topics_assessment)
--
-- Note: This preserves the coding_round configuration for future re-enabling
--

-- ============================================================================
-- Option 1: Disable coding_round but keep configuration (RECOMMENDED)
-- ============================================================================

-- Update all templates to disable coding_round and set weight to 0
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{sections,coding_round,enabled}',
        'false'::jsonb
    ),
    '{sections,coding_round,weight}',
    '0'::jsonb
)
WHERE template_structure->'sections'->'coding_round' IS NOT NULL
  AND (template_structure->'sections'->'coding_round'->>'enabled')::boolean = true;

-- Adjust scoring weights to redistribute coding weight to topics_assessment
-- Template 1: DSA Fundamentals (coding was 50, now give to topics_assessment)
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{scoring,section_weights,coding_round}',
        '0'::jsonb
    ),
    '{scoring,section_weights,topics_assessment}',
    '80'::jsonb  -- Was 30, now 30 + 50 = 80
)
WHERE id = 1;

-- Template 2: System Design (coding was 25, redistribute)
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{scoring,section_weights,coding_round}',
        '0'::jsonb
    ),
    '{scoring,section_weights,topics_assessment}',
    '75'::jsonb  -- Was 50, now 50 + 25 = 75
)
WHERE id = 2;

-- Template 3: Backend Engineering (coding was 35, redistribute)
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{scoring,section_weights,coding_round}',
        '0'::jsonb
    ),
    '{scoring,section_weights,topics_assessment}',
    '60'::jsonb  -- Was 25, now 25 + 35 = 60
)
WHERE id = 3;

-- Template 4: Frontend Development (coding was 30, redistribute)
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{scoring,section_weights,coding_round}',
        '0'::jsonb
    ),
    '{scoring,section_weights,topics_assessment}',
    '55'::jsonb  -- Was 25, now 25 + 30 = 55
)
WHERE id = 4;

-- Template 5: Behavioral Interview (coding already disabled/0 weight)
-- No change needed

-- Template 6: DevOps & Cloud (coding was 25, redistribute)
UPDATE public.interview_templates
SET template_structure = jsonb_set(
    jsonb_set(
        template_structure,
        '{scoring,section_weights,coding_round}',
        '0'::jsonb
    ),
    '{scoring,section_weights,topics_assessment}',
    '55'::jsonb  -- Was 30, now 30 + 25 = 55
)
WHERE id = 6;

-- ============================================================================
-- Verification Query
-- ============================================================================

-- Run this to verify coding_round is disabled in all templates
-- SELECT 
--     id,
--     name,
--     template_structure->'sections'->'coding_round'->>'enabled' as coding_enabled,
--     template_structure->'sections'->'coding_round'->>'weight' as coding_weight,
--     template_structure->'scoring'->'section_weights'->>'coding_round' as scoring_weight,
--     template_structure->'scoring'->'section_weights'->>'topics_assessment' as topics_weight
-- FROM public.interview_templates
-- WHERE is_active = true
-- ORDER BY id;

-- ============================================================================
-- Rollback Script (To Re-enable Coding)
-- ============================================================================

-- Uncomment and run this to re-enable coding problems:
--
-- -- Re-enable coding_round for templates
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     template_structure,
--     '{sections,coding_round,enabled}',
--     'true'::jsonb
-- )
-- WHERE id IN (1, 2, 3, 4, 6);
--
-- -- Restore original weights
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     jsonb_set(
--         jsonb_set(
--             template_structure,
--             '{sections,coding_round,weight}',
--             '50'::jsonb
--         ),
--         '{scoring,section_weights,coding_round}',
--         '50'::jsonb
--     ),
--     '{scoring,section_weights,topics_assessment}',
--     '30'::jsonb
-- )
-- WHERE id = 1;
--
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     jsonb_set(
--         jsonb_set(
--             template_structure,
--             '{sections,coding_round,weight}',
--             '25'::jsonb
--         ),
--         '{scoring,section_weights,coding_round}',
--         '25'::jsonb
--     ),
--     '{scoring,section_weights,topics_assessment}',
--     '50'::jsonb
-- )
-- WHERE id = 2;
--
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     jsonb_set(
--         jsonb_set(
--             template_structure,
--             '{sections,coding_round,weight}',
--             '35'::jsonb
--         ),
--         '{scoring,section_weights,coding_round}',
--         '35'::jsonb
--     ),
--     '{scoring,section_weights,topics_assessment}',
--     '25'::jsonb
-- )
-- WHERE id = 3;
--
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     jsonb_set(
--         jsonb_set(
--             template_structure,
--             '{sections,coding_round,weight}',
--             '30'::jsonb
--         ),
--         '{scoring,section_weights,coding_round}',
--         '30'::jsonb
--     ),
--     '{scoring,section_weights,topics_assessment}',
--     '25'::jsonb
-- )
-- WHERE id = 4;
--
-- UPDATE public.interview_templates
-- SET template_structure = jsonb_set(
--     jsonb_set(
--         jsonb_set(
--             template_structure,
--             '{sections,coding_round,weight}',
--             '25'::jsonb
--         ),
--         '{scoring,section_weights,coding_round}',
--         '25'::jsonb
--     ),
--     '{scoring,section_weights,topics_assessment}',
--     '30'::jsonb
-- )
-- WHERE id = 6;
