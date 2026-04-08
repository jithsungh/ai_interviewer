-- DEV-53: Fix report-generation DB warnings
--
-- Fixes:
--   1) Backfill missing template_structure.scoring_configuration.section_weights
--      to avoid "No section_weights in scoring_configuration" warnings.
--   2) Remove strict uniqueness on (interview_submission_id, scoring_version)
--      to avoid duplicate-scoring-version fallback retries for re-generations.
--
-- Notes:
--   - Invariant "one current result per submission" remains enforced by
--     unique partial index uq_interview_results_submission_current.
--   - Re-running this script is safe (idempotent operations where possible).

BEGIN;

-- ============================================================================
-- PART 1: Backfill section_weights in interview_templates
-- ============================================================================

WITH derived AS (
    SELECT
        it.id,
        COALESCE(
            (
                SELECT jsonb_object_agg(section_name, 1)
                FROM (
                    SELECT DISTINCT
                        COALESCE(
                            NULLIF(TRIM(sec->>'section_name'), ''),
                            NULLIF(TRIM(sec->>'name'), ''),
                            CONCAT('section_', ord::text)
                        ) AS section_name
                    FROM jsonb_array_elements(
                        CASE
                            WHEN jsonb_typeof(it.template_structure->'sections') = 'array'
                                THEN it.template_structure->'sections'
                            ELSE '[]'::jsonb
                        END
                    ) WITH ORDINALITY AS s(sec, ord)
                ) q
            ),
            (
                SELECT jsonb_object_agg(section_name, 1)
                FROM (
                    SELECT DISTINCT
                        NULLIF(TRIM(ie.content_metadata->>'section_name'), '') AS section_name
                    FROM public.interview_submissions isub
                    JOIN public.interview_exchanges ie
                      ON ie.interview_submission_id = isub.id
                    WHERE isub.template_id = it.id
                      AND NULLIF(TRIM(ie.content_metadata->>'section_name'), '') IS NOT NULL
                ) q2
            )
        ) AS section_weights
    FROM public.interview_templates it
),
patches AS (
    SELECT
        it.id,
        jsonb_set(
            it.template_structure,
            '{scoring_configuration,section_weights}',
            d.section_weights,
            true
        ) AS patched_structure
    FROM public.interview_templates it
    JOIN derived d ON d.id = it.id
    WHERE it.template_structure->'scoring_configuration'->'section_weights' IS NULL
      AND d.section_weights IS NOT NULL
)
UPDATE public.interview_templates it
SET template_structure = p.patched_structure,
    updated_at = NOW()
FROM patches p
WHERE it.id = p.id;

-- ============================================================================
-- PART 2: Relax unique constraint causing noisy fallback retries
-- ============================================================================

ALTER TABLE public.interview_results
    DROP CONSTRAINT IF EXISTS interview_results_interview_submission_id_scoring_version_key;

-- Keep lookup performance for reporting/history queries.
CREATE INDEX IF NOT EXISTS idx_interview_results_submission_scoring_version
    ON public.interview_results (interview_submission_id, scoring_version);

COMMIT;
