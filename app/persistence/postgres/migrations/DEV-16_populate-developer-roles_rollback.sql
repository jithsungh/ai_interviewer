--
-- Rollback for DEV-16: Populate Developer Roles
--
-- Reverts changes made in DEV-16_populate-developer-roles.sql
-- Ticket: DEV-16
--

-- Remove the 7 seeded developer roles for super organization
DELETE FROM public.roles WHERE id IN (1, 2, 3, 4, 5, 6, 7) AND organization_id = 1;

-- Reset the sequence to 1
SELECT setval('public.roles_id_seq', 1, false);

