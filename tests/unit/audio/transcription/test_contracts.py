"""
Unit tests for transcription domain contracts.

Validates frozen dataclass invariants, validation rules, and edge cases
for TranscriptionRequest, TranscriptionResult, TranscriptSegment, and
TranscriptionConfig.
"""

import pytest

from app.audio.transcription.contracts import (
    TranscriptionConfig,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptSegment,
)


# ═══════════════════════════════════════════════════════════════════════════
# TranscriptionRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestTranscriptionRequest:
    """Tests for TranscriptionRequest contract."""

    def test_valid_minimal_request(self):
        req = TranscriptionRequest(audio_data=b"\x00\x01\x02")
        assert req.audio_data == b"\x00\x01\x02"
        assert req.sample_rate == 16000
        assert req.language is None
        assert req.context is None
        assert req.streaming is False

    def test_valid_full_request(self):
        req = TranscriptionRequest(
            audio_data=b"audio",
            sample_rate=48000,
            language="en",
            context="coding interview",
            streaming=True,
        )
        assert req.sample_rate == 48000
        assert req.language == "en"
        assert req.streaming is True

    def test_empty_audio_data_raises(self):
        with pytest.raises(ValueError, match="audio_data must not be empty"):
            TranscriptionRequest(audio_data=b"")

    def test_zero_sample_rate_raises(self):
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            TranscriptionRequest(audio_data=b"audio", sample_rate=0)

    def test_negative_sample_rate_raises(self):
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            TranscriptionRequest(audio_data=b"audio", sample_rate=-1)

    def test_frozen_immutability(self):
        req = TranscriptionRequest(audio_data=b"audio")
        with pytest.raises(AttributeError):
            req.sample_rate = 44100  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# TranscriptSegment
# ═══════════════════════════════════════════════════════════════════════════


class TestTranscriptSegment:
    """Tests for TranscriptSegment contract."""

    def test_valid_segment(self):
        seg = TranscriptSegment(text="hello", start_ms=0, end_ms=500, confidence=0.95)
        assert seg.text == "hello"
        assert seg.start_ms == 0
        assert seg.end_ms == 500
        assert seg.confidence == 0.95

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="end_ms must be >= start_ms"):
            TranscriptSegment(text="x", start_ms=500, end_ms=100, confidence=0.5)

    def test_zero_duration_allowed(self):
        seg = TranscriptSegment(text="punct", start_ms=100, end_ms=100, confidence=0.9)
        assert seg.start_ms == seg.end_ms

    def test_frozen_immutability(self):
        seg = TranscriptSegment(text="word", start_ms=0, end_ms=100, confidence=0.8)
        with pytest.raises(AttributeError):
            seg.text = "other"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# TranscriptionResult
# ═══════════════════════════════════════════════════════════════════════════


class TestTranscriptionResult:
    """Tests for TranscriptionResult contract."""

    def test_valid_result(self):
        result = TranscriptionResult(
            transcript="hello world",
            confidence_score=0.92,
        )
        assert result.transcript == "hello world"
        assert result.confidence_score == 0.92
        assert result.language_detected is None
        assert result.segments == ()
        assert result.partial is False
        assert result.provider_metadata == {}

    def test_confidence_clamped_above_one(self):
        result = TranscriptionResult(transcript="x", confidence_score=1.5)
        assert result.confidence_score == 1.0

    def test_confidence_clamped_below_zero(self):
        result = TranscriptionResult(transcript="x", confidence_score=-0.5)
        assert result.confidence_score == 0.0

    def test_normal_confidence_unchanged(self):
        result = TranscriptionResult(transcript="x", confidence_score=0.85)
        assert result.confidence_score == 0.85

    def test_result_with_segments(self):
        segs = (
            TranscriptSegment(text="hello", start_ms=0, end_ms=300, confidence=0.9),
            TranscriptSegment(text="world", start_ms=300, end_ms=600, confidence=0.85),
        )
        result = TranscriptionResult(
            transcript="hello world",
            confidence_score=0.875,
            segments=segs,
        )
        assert len(result.segments) == 2

    def test_frozen_immutability(self):
        result = TranscriptionResult(transcript="test", confidence_score=0.9)
        with pytest.raises(AttributeError):
            result.transcript = "modified"  # type: ignore[misc]

    def test_partial_result(self):
        result = TranscriptionResult(
            transcript="partial text", confidence_score=0.7, partial=True
        )
        assert result.partial is True

    def test_empty_transcript(self):
        result = TranscriptionResult(transcript="", confidence_score=1.0)
        assert result.transcript == ""
        assert result.confidence_score == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# TranscriptionConfig
# ═══════════════════════════════════════════════════════════════════════════


class TestTranscriptionConfig:
    """Tests for TranscriptionConfig contract."""

    def test_defaults(self):
        config = TranscriptionConfig()
        assert config.provider == "whisper"
        assert config.api_key is None
        assert config.model is None
        assert config.detect_language is True
        assert config.word_timestamps is True
        assert config.profanity_filter is False

    def test_custom_config(self):
        config = TranscriptionConfig(
            provider="google",
            api_key="key123",
            model="default",
            language="en",
            detect_language=False,
        )
        assert config.provider == "google"
        assert config.api_key == "key123"

    def test_frozen_immutability(self):
        config = TranscriptionConfig()
        with pytest.raises(AttributeError):
            config.provider = "local"  # type: ignore[misc]
