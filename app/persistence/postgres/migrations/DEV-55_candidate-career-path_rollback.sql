--
-- Rollback DEV-55: Candidate Career Path persistence
--

BEGIN;

DROP TABLE IF EXISTS public.candidate_career_roadmaps;
DROP TABLE IF EXISTS public.candidate_career_insight_runs;

COMMIT;
