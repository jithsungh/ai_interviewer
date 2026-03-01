-- ============================================================================
-- Rollback: DEV-38 — difficulty_adaptation_log table
-- ============================================================================

-- DOWN

DROP INDEX IF EXISTS public.idx_adaptation_log_created_at;
DROP INDEX IF EXISTS public.idx_adaptation_log_submission;
DROP TABLE IF EXISTS public.difficulty_adaptation_log;
