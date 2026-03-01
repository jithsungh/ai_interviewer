-- DEV-36 ROLLBACK: Remove 'expired' and 'cancelled' from submission_status enum
--
-- PostgreSQL does not support DROP VALUE from an enum directly.
-- The standard workaround is to recreate the type and update dependent columns.
-- Run this only if you need a full rollback.

BEGIN;

-- 1. Fail-safe: move any rows using the new values back to a safe state
UPDATE public.interview_submissions
   SET status = 'completed'
 WHERE status IN ('expired', 'cancelled');

-- 2. Rename old type
ALTER TYPE public.submission_status RENAME TO submission_status_old;

-- 3. Create new type without expired/cancelled
CREATE TYPE public.submission_status AS ENUM ('pending', 'in_progress', 'completed', 'reviewed');

-- 4. Alter column to use new type
ALTER TABLE public.interview_submissions
    ALTER COLUMN status TYPE public.submission_status
    USING status::text::public.submission_status;

-- 5. Drop old type
DROP TYPE public.submission_status_old;

COMMIT;
