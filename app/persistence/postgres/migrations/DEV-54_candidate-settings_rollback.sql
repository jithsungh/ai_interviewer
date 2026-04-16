--
-- Rollback DEV-54: Candidate settings persistence
--

BEGIN;

DROP TABLE IF EXISTS public.candidate_settings;

COMMIT;
