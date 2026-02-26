--
-- Migration 001: Auth Module Schema Additions
-- 
-- Purpose: Add required fields and tables for authentication module
-- Date: 2026-02-26
-- Module: app/auth/domain
-- 
-- Changes:
--   1. Add user_type, last_login_at, token_version to users table
--   2. Create refresh_tokens table
--   3. Create auth_audit_log table
--
-- Rollback: See 001_auth_schema_additions_rollback.sql
--

-- ============================================================================
-- PART 1: ALTER users TABLE
-- ============================================================================

-- Add user_type column (admin or candidate)
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) CHECK (user_type IN ('admin', 'candidate'));

-- Backfill user_type based on existing admins/candidates tables
-- Set to 'admin' if user exists in admins table
UPDATE public.users u
SET user_type = 'admin'
WHERE user_type IS NULL
  AND EXISTS (SELECT 1 FROM public.admins a WHERE a.user_id = u.id);

-- Set to 'candidate' if user exists in candidates table
UPDATE public.users u
SET user_type = 'candidate'
WHERE user_type IS NULL
  AND EXISTS (SELECT 1 FROM public.candidates c WHERE c.user_id = u.id);

-- Validate all users have type assigned
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.users WHERE user_type IS NULL) THEN
    RAISE EXCEPTION 'Migration failed: Some users have no user_type. Manual intervention required.';
  END IF;
END $$;

-- Make user_type NOT NULL after backfill
ALTER TABLE public.users 
ALTER COLUMN user_type SET NOT NULL;

-- Add last_login_at column for tracking login activity
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;

-- Add token_version for forced logout feature
-- Incrementing this field invalidates all active JWT tokens for the user
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 1 NOT NULL;

-- Add index for user_type queries
CREATE INDEX IF NOT EXISTS idx_users_type ON public.users(user_type);

-- Add index for last_login queries (analytics)
CREATE INDEX IF NOT EXISTS idx_users_last_login ON public.users(last_login_at) WHERE last_login_at IS NOT NULL;

COMMENT ON COLUMN public.users.user_type IS 'User type: admin or candidate. Determines which extended table (admins/candidates) contains additional data.';
COMMENT ON COLUMN public.users.last_login_at IS 'Timestamp of last successful login. Updated on each login event.';
COMMENT ON COLUMN public.users.token_version IS 'Token version for forced logout. Incrementing this invalidates all active JWT tokens.';


-- ============================================================================
-- PART 2: CREATE refresh_tokens TABLE
-- ============================================================================

-- Create sequence for refresh_tokens
CREATE SEQUENCE IF NOT EXISTS public.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create refresh_tokens table
CREATE TABLE IF NOT EXISTS public.refresh_tokens (
    id bigint NOT NULL DEFAULT nextval('public.refresh_tokens_id_seq'::regclass),
    user_id bigint NOT NULL,
    token_hash text NOT NULL,  -- SHA-256 hash of refresh token
    device_info text,  -- User agent or device fingerprint
    ip_address inet,  -- IP address from which token was issued
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,  -- NULL = active, NOT NULL = revoked
    revoked_reason varchar(100),  -- 'logout', 'password_change', 'admin_action', 'suspicious', 'rotation'
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT refresh_tokens_token_hash_unique UNIQUE (token_hash),
    CONSTRAINT refresh_tokens_user_fkey FOREIGN KEY (user_id) 
        REFERENCES public.users(id) ON DELETE CASCADE
);

-- Indexes for refresh_tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON public.refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON public.refresh_tokens(expires_at) 
    WHERE revoked_at IS NULL;  -- Only index active tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON public.refresh_tokens(revoked_at)
    WHERE revoked_at IS NOT NULL;  -- For audit queries

-- Comments
COMMENT ON TABLE public.refresh_tokens IS 'Refresh tokens for JWT authentication. Tokens are hashed before storage.';
COMMENT ON COLUMN public.refresh_tokens.token_hash IS 'SHA-256 hash of the refresh token. Original token never stored.';
COMMENT ON COLUMN public.refresh_tokens.revoked_at IS 'Timestamp when token was revoked. NULL means token is still active.';
COMMENT ON COLUMN public.refresh_tokens.revoked_reason IS 'Reason for revocation: logout, password_change, admin_action, suspicious, rotation';

-- Grant permissions (adjust users as needed)
ALTER TABLE public.refresh_tokens OWNER TO jithsungh;


-- ============================================================================
-- PART 3: CREATE auth_audit_log TABLE
-- ============================================================================

-- Create sequence for auth_audit_log
CREATE SEQUENCE IF NOT EXISTS public.auth_audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create auth_audit_log table
-- This table is INSERT-ONLY (immutable audit trail)
CREATE TABLE IF NOT EXISTS public.auth_audit_log (
    id bigint NOT NULL DEFAULT nextval('public.auth_audit_log_id_seq'::regclass),
    user_id bigint,  -- NULL for failed login attempts before user identified
    event_type varchar(50) NOT NULL,  -- 'login_success', 'login_failure', 'logout', 'token_refresh', 'password_change', etc.
    ip_address inet,  -- Source IP address
    user_agent text,  -- Browser/client user agent
    event_metadata jsonb,  -- Additional context (error codes, device info, etc.)
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    CONSTRAINT auth_audit_log_pkey PRIMARY KEY (id),
    CONSTRAINT auth_audit_log_user_fkey FOREIGN KEY (user_id) 
        REFERENCES public.users(id) ON DELETE SET NULL  -- Preserve audit log even if user deleted
);

-- Indexes for auth_audit_log
CREATE INDEX IF NOT EXISTS idx_auth_audit_user ON public.auth_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event ON public.auth_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_auth_audit_created ON public.auth_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_auth_audit_ip ON public.auth_audit_log(ip_address);

-- Comments
COMMENT ON TABLE public.auth_audit_log IS 'Immutable audit log for all authentication events. INSERT-ONLY table.';
COMMENT ON COLUMN public.auth_audit_log.event_type IS 'Event type: login_success, login_failure, logout, token_refresh, password_change, admin_role_changed, user_status_changed, suspicious_activity';
COMMENT ON COLUMN public.auth_audit_log.event_metadata IS 'Additional context as JSON: {error_code, email, organization_id, admin_role, etc.}';

-- Grant permissions (adjust users as needed)
ALTER TABLE public.auth_audit_log OWNER TO jithsungh;


-- ============================================================================
-- VALIDATION QUERIES
-- ============================================================================

-- Verify all users have user_type
DO $$
DECLARE
    missing_count integer;
BEGIN
    SELECT COUNT(*) INTO missing_count FROM public.users WHERE user_type IS NULL;
    
    IF missing_count > 0 THEN
        RAISE WARNING 'WARNING: % users have NULL user_type', missing_count;
    ELSE
        RAISE NOTICE 'SUCCESS: All users have user_type assigned';
    END IF;
END $$;

-- Verify table creation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'refresh_tokens') THEN
        RAISE NOTICE 'SUCCESS: refresh_tokens table created';
    ELSE
        RAISE EXCEPTION 'FAILURE: refresh_tokens table not created';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'auth_audit_log') THEN
        RAISE NOTICE 'SUCCESS: auth_audit_log table created';
    ELSE
        RAISE EXCEPTION 'FAILURE: auth_audit_log table not created';
    END IF;
END $$;


-- ============================================================================
-- SUMMARY
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Migration 024 complete';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Changes applied:';
    RAISE NOTICE '  1. users table: Added user_type, last_login_at, token_version';
    RAISE NOTICE '  2. Created refresh_tokens table with indexes';
    RAISE NOTICE '  3. Created auth_audit_log table with indexes';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Verify data integrity';
    RAISE NOTICE '  2. Test auth module implementation';
    RAISE NOTICE '  3. Rollback available in 001_auth_schema_additions_rollback.sql';
    RAISE NOTICE '=============================================================';
END $$;
