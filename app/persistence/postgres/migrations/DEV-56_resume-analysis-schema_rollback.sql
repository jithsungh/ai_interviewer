-- =============================================================================
-- Rollback DEV-56: Resume analysis schema additions
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS public.idx_resumes_candidate_created_at;

ALTER TABLE public.resumes
    DROP COLUMN IF EXISTS updated_at,
    DROP COLUMN IF EXISTS analyzed_at,
    DROP COLUMN IF EXISTS embeddings_error,
    DROP COLUMN IF EXISTS llm_error,
    DROP COLUMN IF EXISTS parse_error,
    DROP COLUMN IF EXISTS embeddings_status,
    DROP COLUMN IF EXISTS llm_analysis_status,
    DROP COLUMN IF EXISTS parse_status,
    DROP COLUMN IF EXISTS embeddings,
    DROP COLUMN IF EXISTS ats_feedback,
    DROP COLUMN IF EXISTS ats_score,
    DROP COLUMN IF EXISTS llm_feedback,
    DROP COLUMN IF EXISTS structured_json,
    DROP COLUMN IF EXISTS file_name;

COMMIT;
