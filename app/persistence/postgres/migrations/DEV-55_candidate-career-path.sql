--
-- Migration DEV-55: Candidate Career Path persistence
--
-- Purpose: Persist generated career market insights and personalized roadmaps
--          so the Career Path page is fully backend-driven and resumable.
-- Date: 2026-04-16
-- Module: app/candidate
-- Ticket: DEV-55
--
-- Changes:
--   1. Create public.candidate_career_insight_runs
--   2. Create public.candidate_career_roadmaps
--   3. Add indexes for candidate-scoped reads and active roadmap lookup
--
-- Rollback: See DEV-55_candidate-career-path_rollback.sql
--

BEGIN;

CREATE TABLE IF NOT EXISTS public.candidate_career_insight_runs (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
    industry TEXT NOT NULL,
    seniority VARCHAR(30) NOT NULL,
    insights JSONB NOT NULL DEFAULT '[]'::jsonb,
    generation_source VARCHAR(20) NOT NULL DEFAULT 'fallback',
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_career_insight_runs_candidate_created
    ON public.candidate_career_insight_runs (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_career_insight_runs_lookup
    ON public.candidate_career_insight_runs (candidate_id, industry, seniority, created_at DESC);

CREATE TABLE IF NOT EXISTS public.candidate_career_roadmaps (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
    insight_run_id BIGINT REFERENCES public.candidate_career_insight_runs(id) ON DELETE SET NULL,
    industry TEXT NOT NULL,
    target_role TEXT NOT NULL,
    selected_insight JSONB,
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    completed_levels JSONB NOT NULL DEFAULT '[]'::jsonb,
    current_level INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    generation_source VARCHAR(20) NOT NULL DEFAULT 'fallback',
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT candidate_career_roadmaps_current_level_check CHECK (current_level BETWEEN 1 AND 4)
);

CREATE INDEX IF NOT EXISTS idx_career_roadmaps_candidate_created
    ON public.candidate_career_roadmaps (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_career_roadmaps_active
    ON public.candidate_career_roadmaps (candidate_id, is_active, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_career_roadmaps_one_active
    ON public.candidate_career_roadmaps (candidate_id)
    WHERE is_active = true;

COMMIT;
