--
-- Rollback DEV-56: Candidate interview prep deck persistence
--

BEGIN;

DROP TABLE IF EXISTS public.candidate_practice_deck_runs CASCADE;

COMMIT;
