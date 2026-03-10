--
-- Rollback for DEV-51: Create Practice Window
--
-- Reverts changes made in DEV-51_create-practice-window.sql
--

-- Remove template-role mappings for practice window
DELETE FROM public.window_role_templates
WHERE window_id = 1;

-- Remove the practice window itself
DELETE FROM public.interview_submission_windows
WHERE id = 1 AND name = '__practice__';
