-- =============================================================================
-- Migration DEV-56: Resume analysis schema additions
-- =============================================================================
--
-- Purpose:
--   Extend the existing public.resumes table so it can store full resume
--   upload metadata, LLM analysis results, ATS scoring, and embeddings.
--
--   Existing table columns (current production schema):
--     id, candidate_id, file_url, parsed_text, extracted_data,
--     uploaded_at, created_at
--
--   This migration adds:
--     - file_name
--     - structured_json
--     - llm_feedback
--     - ats_score
--     - ats_feedback
--     - embeddings
--     - parse_status
--     - llm_analysis_status
--     - embeddings_status
--     - parse_error
--     - llm_error
--     - embeddings_error
--     - analyzed_at
--     - updated_at
--
--   It also backfills existing rows from extracted_data where possible.
--
-- Idempotent: uses IF NOT EXISTS / safe UPDATE statements.
-- =============================================================================

BEGIN;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS file_name TEXT;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS structured_json JSONB;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS llm_feedback JSONB;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS ats_score INTEGER;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS ats_feedback TEXT;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS embeddings JSONB;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS parse_status VARCHAR(20) NOT NULL DEFAULT 'success';

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS llm_analysis_status VARCHAR(20) NOT NULL DEFAULT 'pending';

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS embeddings_status VARCHAR(20) NOT NULL DEFAULT 'pending';

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS parse_error TEXT;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS llm_error TEXT;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS embeddings_error TEXT;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ;

ALTER TABLE public.resumes
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Backfill existing rows from extracted_data when it already contains analysis payloads.
UPDATE public.resumes
SET
    file_name = COALESCE(file_name, (extracted_data ->> 'file_name')),
    structured_json = COALESCE(structured_json, (extracted_data -> 'structured_json')),
    llm_feedback = COALESCE(llm_feedback, (extracted_data -> 'llm_feedback')),
    ats_score = COALESCE(ats_score, NULLIF(extracted_data ->> 'ats_score', '')::INTEGER),
    ats_feedback = COALESCE(ats_feedback, extracted_data ->> 'ats_feedback'),
    embeddings = COALESCE(embeddings, (extracted_data -> 'embeddings')),
    parse_status = COALESCE(parse_status, extracted_data ->> 'parse_status', 'success'),
    llm_analysis_status = COALESCE(llm_analysis_status, extracted_data ->> 'llm_analysis_status', 'pending'),
    embeddings_status = COALESCE(embeddings_status, extracted_data ->> 'embeddings_status', 'pending'),
    parse_error = COALESCE(parse_error, extracted_data ->> 'parse_error'),
    llm_error = COALESCE(llm_error, extracted_data ->> 'llm_error'),
    embeddings_error = COALESCE(embeddings_error, extracted_data ->> 'embeddings_error'),
    analyzed_at = COALESCE(analyzed_at, NULLIF(extracted_data ->> 'analyzed_at', '')::TIMESTAMPTZ),
    updated_at = COALESCE(updated_at, now())
WHERE extracted_data IS NOT NULL;

-- Default values for future inserts/updates.
ALTER TABLE public.resumes
    ALTER COLUMN parse_status SET DEFAULT 'success';

ALTER TABLE public.resumes
    ALTER COLUMN llm_analysis_status SET DEFAULT 'pending';

ALTER TABLE public.resumes
    ALTER COLUMN embeddings_status SET DEFAULT 'pending';

ALTER TABLE public.resumes
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_resumes_candidate_created_at
    ON public.resumes (candidate_id, created_at DESC);

COMMIT;
