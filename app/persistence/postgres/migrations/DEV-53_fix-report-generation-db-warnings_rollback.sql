-- Rollback: DEV-53_fix-report-generation-db-warnings
--
-- Reverts:
--   1) Re-add unique constraint on (interview_submission_id, scoring_version)
--   2) Drop helper non-unique index added by DEV-53
--
-- Note:
--   If duplicates exist for (interview_submission_id, scoring_version), we first
--   rewrite older duplicates with a deterministic rollback suffix so the unique
--   constraint can be restored safely.

BEGIN;

-- Remove helper index introduced by DEV-53
DROP INDEX IF EXISTS public.idx_interview_results_submission_scoring_version;

-- Normalize duplicates before restoring unique constraint
WITH ranked AS (
    SELECT
        id,
        interview_submission_id,
        scoring_version,
        ROW_NUMBER() OVER (
            PARTITION BY interview_submission_id, scoring_version
            ORDER BY created_at DESC, id DESC
        ) AS rn
    FROM public.interview_results
),
renamed AS (
    UPDATE public.interview_results ir
    SET scoring_version = ir.scoring_version || '-rb-' || ir.id::text
    FROM ranked r
    WHERE ir.id = r.id
      AND r.rn > 1
    RETURNING ir.id
)
SELECT COUNT(*) AS renamed_rows FROM renamed;

ALTER TABLE public.interview_results
    ADD CONSTRAINT interview_results_interview_submission_id_scoring_version_key
    UNIQUE (interview_submission_id, scoring_version);

COMMIT;
