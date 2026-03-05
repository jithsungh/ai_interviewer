-- =============================================================================
-- Rollback: DEV-49 — Audio Persistence Schema Additions
-- =============================================================================
--
-- Reverses the forward migration by dropping added columns and constraints.
-- Safe to run multiple times (idempotent).
-- =============================================================================

-- Drop index
DROP INDEX IF EXISTS idx_audio_analytics_finalized;

-- Drop CHECK constraints
ALTER TABLE public.audio_analytics DROP CONSTRAINT IF EXISTS audio_analytics_sentiment_range;
ALTER TABLE public.audio_analytics DROP CONSTRAINT IF EXISTS audio_analytics_confidence_range;
ALTER TABLE public.audio_analytics DROP CONSTRAINT IF EXISTS audio_analytics_speech_state_check;

-- Drop added columns (reverse order of addition)
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS finalized_at;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS updated_at;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS background_noise_detected;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS audio_quality_score;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS frustration_detected;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS hesitation_detected;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS filler_rate;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS long_pause_count;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS pause_duration_ms;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS speech_state;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS language_detected;
ALTER TABLE public.audio_analytics DROP COLUMN IF EXISTS transcript_finalized;
