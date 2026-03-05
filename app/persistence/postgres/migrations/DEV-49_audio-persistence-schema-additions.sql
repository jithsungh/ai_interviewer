-- =============================================================================
-- Migration: DEV-49 — Audio Persistence Schema Additions
-- =============================================================================
--
-- Purpose:
--   Add missing columns to the `audio_analytics` table as required by
--   app/audio/persistence/REQUIREMENTS.md.
--
--   The existing table has: id, interview_exchange_id, transcript,
--   confidence_score, speech_rate_wpm, filler_word_count, sentiment_score,
--   analysis_metadata, created_at.
--
--   This migration adds:
--   - transcript_finalized (boolean) — immutability flag
--   - language_detected (varchar) — detected language code
--   - speech_state (varchar) — complete/incomplete/continuing
--   - pause_duration_ms (integer) — pause duration
--   - long_pause_count (integer) — count of long pauses
--   - filler_rate (numeric) — fillers per minute
--   - hesitation_detected (boolean) — behavioral signal
--   - frustration_detected (boolean) — behavioral signal
--   - audio_quality_score (numeric) — quality metric
--   - background_noise_detected (boolean) — noise flag
--   - updated_at (timestamptz) — last modification
--   - finalized_at (timestamptz) — when finalized
--
-- Justification:
--   REQUIREMENTS.md §2 specifies these columns for full audio analytics
--   persistence. No existing module depends on the absence of these columns.
--   All new columns are nullable or have defaults, so existing rows are safe.
--
-- SRS Invariant Check:
--   ✓ No exchange immutability violated (audio_analytics is a separate table)
--   ✓ No evaluation invariants violated (read-only after finalization)
--   ✓ No template immutability violated (unrelated table)
--   ✓ One exchange = one evaluation preserved (UNIQUE constraint untouched)
--
-- ERD Invariant Check:
--   ✓ FK to interview_exchanges unchanged
--   ✓ UNIQUE on interview_exchange_id unchanged
--   ✓ No new FK introduced
--
-- Idempotent: Uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS where supported.
-- =============================================================================

-- Add transcript finalization flag
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS transcript_finalized BOOLEAN NOT NULL DEFAULT FALSE;

-- Add language detection
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS language_detected VARCHAR(10);

-- Add speech state (complete/incomplete/continuing)
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS speech_state VARCHAR(20) NOT NULL DEFAULT 'complete';

-- Add pause metrics
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS pause_duration_ms INTEGER;

ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS long_pause_count INTEGER NOT NULL DEFAULT 0;

-- Add filler rate
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS filler_rate NUMERIC NOT NULL DEFAULT 0.0;

-- Add behavioral signals
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS hesitation_detected BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS frustration_detected BOOLEAN NOT NULL DEFAULT FALSE;

-- Add audio quality metrics
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS audio_quality_score NUMERIC;

ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS background_noise_detected BOOLEAN NOT NULL DEFAULT FALSE;

-- Add modification timestamps
ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();

ALTER TABLE public.audio_analytics
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP WITH TIME ZONE;

-- Add CHECK constraints (idempotent via DO block)
DO $$
BEGIN
    -- Speech state constraint
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'audio_analytics_speech_state_check'
    ) THEN
        ALTER TABLE public.audio_analytics
            ADD CONSTRAINT audio_analytics_speech_state_check
            CHECK (speech_state IN ('complete', 'incomplete', 'continuing'));
    END IF;

    -- Confidence score range constraint
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'audio_analytics_confidence_range'
    ) THEN
        ALTER TABLE public.audio_analytics
            ADD CONSTRAINT audio_analytics_confidence_range
            CHECK (confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0));
    END IF;

    -- Sentiment score range constraint
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'audio_analytics_sentiment_range'
    ) THEN
        ALTER TABLE public.audio_analytics
            ADD CONSTRAINT audio_analytics_sentiment_range
            CHECK (sentiment_score IS NULL OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0));
    END IF;
END
$$;

-- Add index on finalized status for efficient filtering
CREATE INDEX IF NOT EXISTS idx_audio_analytics_finalized
    ON public.audio_analytics(transcript_finalized);
