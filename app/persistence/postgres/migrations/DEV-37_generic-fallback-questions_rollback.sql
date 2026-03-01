--
-- Rollback for DEV-37: Generic Fallback Questions Table
--
-- Reverts changes made in DEV-37_generic-fallback-questions.sql
-- Ticket: DEV-37
--

DROP TABLE IF EXISTS public.generic_fallback_questions CASCADE;
DROP SEQUENCE IF EXISTS public.generic_fallback_questions_id_seq;
