-- DEV-52 ROLLBACK: submission state machine enforcement

-- Drop expiry index
DROP INDEX IF EXISTS public.idx_interview_submissions_expiry_scan;

-- Drop audit trigger + function
DROP TRIGGER IF EXISTS trg_audit_interview_submission_status_transition ON public.interview_submissions;
DROP FUNCTION IF EXISTS public.fn_audit_interview_submission_status_transition();

-- Drop validation trigger + function
DROP TRIGGER IF EXISTS trg_validate_interview_submission_status_transition ON public.interview_submissions;
DROP FUNCTION IF EXISTS public.fn_validate_interview_submission_status_transition();

-- Drop audit indexes/table/sequence
DROP INDEX IF EXISTS public.idx_interview_submission_status_audit_occurred;
DROP INDEX IF EXISTS public.idx_interview_submission_status_audit_submission;
DROP TABLE IF EXISTS public.interview_submission_status_audit CASCADE;
DROP SEQUENCE IF EXISTS public.interview_submission_status_audit_id_seq CASCADE;

-- Drop allowed transitions table
DROP TABLE IF EXISTS public.interview_submission_allowed_transitions CASCADE;

-- Drop optimistic lock version column
ALTER TABLE public.interview_submissions
DROP COLUMN IF EXISTS version;
