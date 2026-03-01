-- DEV-36: Add 'expired' and 'cancelled' to submission_status enum
-- This migration is idempotent; it checks before adding each value.

DO $$
BEGIN
    -- Add 'expired' if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'expired'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'submission_status')
    ) THEN
        ALTER TYPE public.submission_status ADD VALUE 'expired' AFTER 'completed';
    END IF;

    -- Add 'cancelled' if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'cancelled'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'submission_status')
    ) THEN
        ALTER TYPE public.submission_status ADD VALUE 'cancelled' AFTER 'expired';
    END IF;
END
$$;
