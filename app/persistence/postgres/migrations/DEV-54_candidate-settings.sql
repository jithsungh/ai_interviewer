--
-- Migration DEV-54: Candidate settings persistence
--
-- Purpose: Persist candidate notification/privacy/UI preferences so the
--          Settings page can be fully backend-driven.
-- Date: 2026-04-10
-- Module: app/candidate
-- Ticket: DEV-54
--
-- Changes:
--   1. Create public.candidate_settings
--   2. Backfill default settings rows for existing candidates
--
-- Rollback: See DEV-54_candidate-settings_rollback.sql
--

BEGIN;

CREATE TABLE IF NOT EXISTS public.candidate_settings (
    candidate_id BIGINT PRIMARY KEY REFERENCES public.candidates(id) ON DELETE CASCADE,
    notification_preferences JSONB NOT NULL DEFAULT '{"email": true, "interview": true, "reports": true, "marketing": false}'::jsonb,
    privacy_preferences JSONB NOT NULL DEFAULT '{"profileVisible": true, "shareResults": false, "allowAnalytics": true}'::jsonb,
    ui_preferences JSONB NOT NULL DEFAULT '{"theme": "system"}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.candidate_settings (candidate_id)
SELECT c.id
FROM public.candidates c
WHERE NOT EXISTS (
    SELECT 1
    FROM public.candidate_settings s
    WHERE s.candidate_id = c.id
);

COMMIT;
