--
-- Migration 001 Rollback: Auth Module Schema Additions
-- 
-- Purpose: Rollback changes from 001_auth_schema_additions.sql
-- Date: 2026-02-26
-- Module: app/auth/domain
-- 
-- WARNING: This will DROP tables and columns. Ensure backups exist!
--

-- ============================================================================
-- ROLLBACK auth_audit_log TABLE
-- ============================================================================

DROP TABLE IF EXISTS public.auth_audit_log CASCADE;
DROP SEQUENCE IF EXISTS public.auth_audit_log_id_seq CASCADE;

RAISE NOTICE 'Dropped auth_audit_log table and sequence';


-- ============================================================================
-- ROLLBACK refresh_tokens TABLE
-- ============================================================================

DROP TABLE IF EXISTS public.refresh_tokens CASCADE;
DROP SEQUENCE IF EXISTS public.refresh_tokens_id_seq CASCADE;

RAISE NOTICE 'Dropped refresh_tokens table and sequence';


-- ==================================================================
-- ROLLBACK users TABLE CHANGES
-- ============================================================================

-- Drop indexes
DROP INDEX IF EXISTS public.idx_users_last_login;
DROP INDEX IF EXISTS public.idx_users_type;

-- Drop columns
ALTER TABLE public.users DROP COLUMN IF EXISTS token_version;
ALTER TABLE public.users DROP COLUMN IF EXISTS last_login_at;
ALTER TABLE public.users DROP COLUMN IF EXISTS user_type;

RAISE NOTICE 'Removed columns from users table: user_type, last_login_at, token_version';


-- ============================================================================
-- VALIDATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Migration 001 rollback complete';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Changes reverted:';
    RAISE NOTICE '  1. Dropped auth_audit_log table';
    RAISE NOTICE '  2. Dropped refresh_tokens table';
    RAISE NOTICE '  3. Removed user_type, last_login_at, token_version from users';
    RAISE NOTICE '';
    RAISE NOTICE 'Database restored to pre-migration state';
    RAISE NOTICE '=============================================================';
END $$;
