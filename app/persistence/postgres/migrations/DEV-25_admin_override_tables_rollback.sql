--
-- Rollback for DEV-25: Admin Override Tables
--
-- Reverses all changes from DEV-25_admin_override_tables.sql
-- Date: 2026-02-27
-- Ticket: DEV-25
--

DROP TABLE IF EXISTS public.coding_problem_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.coding_problem_overrides_id_seq;

DROP TABLE IF EXISTS public.question_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.question_overrides_id_seq;

DROP TABLE IF EXISTS public.topic_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.topic_overrides_id_seq;

DROP TABLE IF EXISTS public.role_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.role_overrides_id_seq;

DROP TABLE IF EXISTS public.rubric_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.rubric_overrides_id_seq;

DROP TABLE IF EXISTS public.template_overrides CASCADE;
DROP SEQUENCE IF EXISTS public.template_overrides_id_seq;
