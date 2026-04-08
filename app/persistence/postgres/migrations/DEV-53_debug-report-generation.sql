-- DEV-53 Debug Queries: report-generation issues
-- Purpose:
--   1) Why "No section_weights in scoring_configuration" appears
--   2) Why duplicate scoring_version fallback is triggered
--   3) Why final score becomes 0.0
--
-- Usage (psql):
--   \set submission_id 677
--   \set template_id 1

-- ============================================================================
-- A) Template and section_weights diagnostics
-- ============================================================================

-- 1. Check template_structure and scoring configuration shape
SELECT
    it.id,
    it.name,
    it.version,
    jsonb_typeof(it.template_structure) AS template_structure_type,
    jsonb_typeof(it.template_structure->'scoring_configuration') AS scoring_configuration_type,
    jsonb_typeof(it.template_structure->'scoring_configuration'->'section_weights') AS section_weights_type,
    it.template_structure->'scoring_configuration'->'section_weights' AS section_weights
FROM public.interview_templates it
WHERE it.id = :template_id;

-- 2. List all templates missing section_weights
SELECT
    it.id,
    it.name,
    it.version,
    it.organization_id,
    CASE
        WHEN it.template_structure->'scoring_configuration'->'section_weights' IS NULL THEN 'missing'
        ELSE 'present'
    END AS section_weights_status
FROM public.interview_templates it
WHERE it.template_structure->'scoring_configuration'->'section_weights' IS NULL
ORDER BY it.id;

-- 3. Compare sections present vs section_weights keys for one template
WITH section_names AS (
    SELECT DISTINCT
        COALESCE(
            NULLIF(TRIM(sec->>'section_name'), ''),
            NULLIF(TRIM(sec->>'name'), ''),
            CONCAT('section_', ord::text)
        ) AS section_name
    FROM public.interview_templates it
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(it.template_structure->'sections') = 'array'
                THEN it.template_structure->'sections'
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS t(sec, ord)
    WHERE it.id = :template_id
),
weight_keys AS (
    SELECT key AS section_name
    FROM public.interview_templates it
    CROSS JOIN LATERAL jsonb_each_text(
        COALESCE(it.template_structure->'scoring_configuration'->'section_weights', '{}'::jsonb)
    )
    WHERE it.id = :template_id
)
SELECT
    s.section_name,
    CASE WHEN w.section_name IS NULL THEN 'missing_in_weights' ELSE 'ok' END AS status
FROM section_names s
LEFT JOIN weight_keys w ON w.section_name = s.section_name
ORDER BY s.section_name;

-- ============================================================================
-- B) scoring_version duplication diagnostics
-- ============================================================================

-- 4. Show interview results for one submission with same scoring_version repeats
SELECT
    ir.id,
    ir.interview_submission_id,
    ir.scoring_version,
    ir.is_current,
    ir.result_status,
    ir.final_score,
    ir.normalized_score,
    ir.created_at,
    ir.computed_at
FROM public.interview_results ir
WHERE ir.interview_submission_id = :submission_id
ORDER BY ir.created_at DESC, ir.id DESC;

-- 5. Find duplicate scoring_version tuples globally
SELECT
    interview_submission_id,
    scoring_version,
    COUNT(*) AS cnt,
    ARRAY_AGG(id ORDER BY created_at DESC, id DESC) AS result_ids
FROM public.interview_results
GROUP BY interview_submission_id, scoring_version
HAVING COUNT(*) > 1
ORDER BY cnt DESC, interview_submission_id;

-- ============================================================================
-- C) Scoring quality diagnostics (zeros/defaulted dimensions)
-- ============================================================================

-- 6. Exchange-level answer lengths for one submission
SELECT
    ie.id AS exchange_id,
    ie.sequence_order,
    LENGTH(COALESCE(NULLIF(ie.response_text, ''), NULLIF(ie.response_code, ''), '')) AS answer_length,
    LENGTH(COALESCE(aa.transcript, '')) AS transcript_length
FROM public.interview_exchanges ie
LEFT JOIN public.audio_analytics aa ON aa.interview_exchange_id = ie.id
WHERE ie.interview_submission_id = :submission_id
ORDER BY ie.sequence_order;

-- 7. Latest final evaluation per exchange + total score
SELECT DISTINCT ON (ie.id)
    ie.id AS exchange_id,
    ie.sequence_order,
    e.id AS evaluation_id,
    e.total_score,
    e.evaluator_type,
    e.scoring_version,
    e.created_at
FROM public.interview_exchanges ie
LEFT JOIN public.evaluations e
    ON e.interview_exchange_id = ie.id
   AND e.is_final = true
WHERE ie.interview_submission_id = :submission_id
ORDER BY ie.id, e.created_at DESC, e.id DESC;

-- 8. Dimension rows with fallback-default markers
SELECT
    e.id AS evaluation_id,
    e.interview_exchange_id,
    rd.dimension_name,
    eds.score,
    eds.max_score,
    eds.justification
FROM public.evaluations e
JOIN public.evaluation_dimension_scores eds ON eds.evaluation_id = e.id
JOIN public.rubric_dimensions rd ON rd.id = eds.rubric_dimension_id
JOIN public.interview_exchanges ie ON ie.id = e.interview_exchange_id
WHERE ie.interview_submission_id = :submission_id
  AND e.is_final = true
ORDER BY e.id DESC, rd.sequence_order;

-- 9. Count suspicious all-zero evaluations (with synthetic fallback justification)
SELECT
    e.id AS evaluation_id,
    e.interview_exchange_id,
    COUNT(*) AS dim_count,
    SUM(CASE WHEN eds.score > 0 THEN 1 ELSE 0 END) AS non_zero_dims,
    SUM(CASE WHEN eds.justification ILIKE '%defaulting to 0%' THEN 1 ELSE 0 END) AS defaulted_dims
FROM public.evaluations e
JOIN public.evaluation_dimension_scores eds ON eds.evaluation_id = e.id
JOIN public.interview_exchanges ie ON ie.id = e.interview_exchange_id
WHERE ie.interview_submission_id = :submission_id
  AND e.is_final = true
GROUP BY e.id, e.interview_exchange_id
ORDER BY e.id DESC;
