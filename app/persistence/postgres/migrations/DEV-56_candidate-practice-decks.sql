--
-- Migration DEV-56: Candidate interview prep deck persistence
--
-- Purpose: Persist AI-generated interview prep flashcard decks so the
--          Interview Prep page is backend-driven, resumable, and auditable.
-- Date: 2026-04-16
-- Module: app/candidate
-- Ticket: DEV-56
--
-- Changes:
--   1. Create public.candidate_practice_deck_runs
--   2. Add indexes for candidate-scoped reads and active deck lookup
--
-- Rollback: See DEV-56_candidate-practice-decks_rollback.sql
--

BEGIN;

CREATE TABLE IF NOT EXISTS public.candidate_practice_deck_runs (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    industry TEXT NOT NULL,
    question_type VARCHAR(30),
    difficulty VARCHAR(20),
    source_question_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    flashcards JSONB NOT NULL DEFAULT '[]'::jsonb,
    bookmarked_indices JSONB NOT NULL DEFAULT '[]'::jsonb,
    mastered_indices JSONB NOT NULL DEFAULT '[]'::jsonb,
    current_card_index INTEGER NOT NULL DEFAULT 0,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    generation_source VARCHAR(20) NOT NULL DEFAULT 'db',
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT candidate_practice_deck_runs_current_card_index_check CHECK (current_card_index >= 0),
    CONSTRAINT candidate_practice_deck_runs_progress_check CHECK (progress_percent BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS idx_candidate_practice_deck_runs_candidate_created
    ON public.candidate_practice_deck_runs (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_practice_deck_runs_active
    ON public.candidate_practice_deck_runs (candidate_id, is_active, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_practice_deck_runs_lookup
    ON public.candidate_practice_deck_runs (candidate_id, role, industry, question_type, difficulty, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_practice_deck_runs_one_active
    ON public.candidate_practice_deck_runs (candidate_id)
    WHERE is_active = true;

COMMIT;
