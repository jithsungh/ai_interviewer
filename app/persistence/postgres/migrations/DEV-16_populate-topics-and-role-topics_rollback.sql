--
-- Rollback for DEV-16: Populate Topics and Role-Topics Mapping
--
-- Reverts changes made in DEV-16_populate-topics-and-role-topics.sql
-- Ticket: DEV-16
--

-- Remove all role-topic mappings for the 7 roles
DELETE FROM public.role_topics WHERE role_id IN (1, 2, 3, 4, 5, 6, 7);

-- Remove all topics created for super organization
DELETE FROM public.topics WHERE id >= 1 AND id <= 120 AND organization_id = 1;

-- Reset the sequence to 1
SELECT setval('public.topics_id_seq', 1, false);

