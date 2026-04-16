--
-- Rollback Migration DEV-54: Self-Introduction as First Interview Question
--
-- Reverts:
--   1) Removes seeded self-introduction preset questions.
--   2) Disables self_introduction section in templates where currently enabled.
--   3) Adjusts template_structure.total_questions (-question_count, floor at 0).
--

-- ============================================================================
-- PART 1: Remove seeded preset questions
plan for resume upload, analysis , proper results, feedback and ATS scoring plan all backend development - api, prompt template, based on target role and uploaded resume etc.., frontend development,  DB migrations if required

WHERE source_type = 'self_intro_preset';

-- ============================================================================
-- PART 2: Disable self_introduction in template_structure and adjust totals
-- ============================================================================

WITH targets AS (
    SELECT
        it.id,
        it.template_structure,
        COALESCE((it.template_structure->>'total_questions')::int, 0) AS total_before,
        COALESCE((it.template_structure #>> '{sections,self_introduction,question_count}')::int, 1) AS sub_count
    FROM public.interview_templates it
    WHERE jsonb_typeof(it.template_structure) = 'object'
      AND jsonb_typeof(it.template_structure->'sections') = 'object'
      AND jsonb_typeof(it.template_structure->'sections'->'self_introduction') = 'object'
      AND COALESCE((it.template_structure #>> '{sections,self_introduction,enabled}')::boolean, false) = true
),
patched AS (
    SELECT
        t.id,
        jsonb_set(
            jsonb_set(
                t.template_structure,
                '{sections,self_introduction,enabled}',
                'false'::jsonb,
                true
            ),
            '{total_questions}',
            to_jsonb(GREATEST(0, t.total_before - t.sub_count)),
            true
        ) AS patched_structure
    FROM targets t
)
UPDATE public.interview_templates it
SET
    template_structure = p.patched_structure,
    updated_at = now()
FROM patched p
WHERE it.id = p.id;
