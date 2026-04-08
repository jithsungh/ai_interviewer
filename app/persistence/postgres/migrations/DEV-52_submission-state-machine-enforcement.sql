-- DEV-52: Production-grade interview submission state machine enforcement
--
-- Adds:
--   1) DB-level allowed transition table
--   2) BEFORE UPDATE trigger to validate status transitions
--   3) AFTER UPDATE trigger to audit every status change
--   4) Optimistic concurrency version column on interview_submissions
--   5) Supporting indexes for expiry scans + audit queries

-- ============================================================================
-- PART 1: version column for optimistic concurrency
-- ============================================================================

ALTER TABLE public.interview_submissions
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- ============================================================================
-- PART 2: allowed transitions table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.interview_submission_allowed_transitions (
    from_status public.submission_status NOT NULL,
    to_status public.submission_status NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT interview_submission_allowed_transitions_pkey PRIMARY KEY (from_status, to_status),
    CONSTRAINT ck_interview_submission_allowed_transitions_no_self_loop CHECK (from_status <> to_status)
);

INSERT INTO public.interview_submission_allowed_transitions (from_status, to_status)
VALUES
    ('pending', 'in_progress'),
    ('pending', 'cancelled'),
    ('in_progress', 'completed'),
    ('in_progress', 'expired'),
    ('in_progress', 'cancelled'),
    ('completed', 'reviewed'),
    ('expired', 'reviewed'),
    ('cancelled', 'reviewed')
ON CONFLICT (from_status, to_status) DO NOTHING;

-- ============================================================================
-- PART 3: status transition audit table
-- ============================================================================

CREATE SEQUENCE IF NOT EXISTS public.interview_submission_status_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE IF NOT EXISTS public.interview_submission_status_audit (
    id BIGINT NOT NULL DEFAULT nextval('public.interview_submission_status_audit_id_seq'::regclass),
    submission_id BIGINT NOT NULL,
    from_status public.submission_status NOT NULL,
    to_status public.submission_status NOT NULL,
    actor TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    CONSTRAINT interview_submission_status_audit_pkey PRIMARY KEY (id),
    CONSTRAINT interview_submission_status_audit_submission_fkey
        FOREIGN KEY (submission_id) REFERENCES public.interview_submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interview_submission_status_audit_submission
    ON public.interview_submission_status_audit(submission_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_interview_submission_status_audit_occurred
    ON public.interview_submission_status_audit(occurred_at DESC);

-- ============================================================================
-- PART 4: trigger function for transition validation
-- ============================================================================

CREATE OR REPLACE FUNCTION public.fn_validate_interview_submission_status_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- only validate actual status changes
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.interview_submission_allowed_transitions t
        WHERE t.from_status = OLD.status::public.submission_status
          AND t.to_status = NEW.status::public.submission_status
    ) THEN
        RAISE EXCEPTION
            'Invalid interview_submissions.status transition: % -> % (submission_id=%)',
            OLD.status,
            NEW.status,
            OLD.id
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_interview_submission_status_transition ON public.interview_submissions;

CREATE TRIGGER trg_validate_interview_submission_status_transition
BEFORE UPDATE OF status ON public.interview_submissions
FOR EACH ROW
EXECUTE FUNCTION public.fn_validate_interview_submission_status_transition();

-- ============================================================================
-- PART 5: trigger function for transition audit logging
-- ============================================================================

CREATE OR REPLACE FUNCTION public.fn_audit_interview_submission_status_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actor_value TEXT;
BEGIN
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    actor_value := NULLIF(current_setting('app.actor', true), '');

    INSERT INTO public.interview_submission_status_audit (
        submission_id,
        from_status,
        to_status,
        actor,
        occurred_at
    )
    VALUES (
        NEW.id,
        OLD.status::public.submission_status,
        NEW.status::public.submission_status,
        actor_value,
        now()
    );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_interview_submission_status_transition ON public.interview_submissions;

CREATE TRIGGER trg_audit_interview_submission_status_transition
AFTER UPDATE OF status ON public.interview_submissions
FOR EACH ROW
EXECUTE FUNCTION public.fn_audit_interview_submission_status_transition();

-- ============================================================================
-- PART 6: supporting index for expiry worker queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_interview_submissions_expiry_scan
    ON public.interview_submissions(scheduled_end)
    WHERE status = 'in_progress';
