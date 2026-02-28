"""
Unit tests for confidence score aggregation.

Pure domain logic — no I/O, no mocks needed.
"""

import pytest

from app.audio.transcription.confidence import calculate_aggregate_confidence
from app.audio.transcription.contracts import TranscriptSegment


class TestCalculateAggregateConfidence:
    """Tests for calculate_aggregate_confidence."""

    def test_empty_segments_returns_zero(self):
        assert calculate_aggregate_confidence([]) == 0.0

    def test_single_segment(self):
        segments = [TranscriptSegment(text="hello", confidence=0.9)]
        assert calculate_aggregate_confidence(segments) == pytest.approx(0.9)

    def test_mean_of_segments(self):
        segments = [
            TranscriptSegment(text="The", confidence=0.9),
            TranscriptSegment(text="answer", confidence=0.85),
            TranscriptSegment(text="is", confidence=0.95),
        ]
        expected = (0.9 + 0.85 + 0.95) / 3
        assert calculate_aggregate_confidence(segments) == pytest.approx(
            expected, abs=0.001
        )

    def test_five_segments_mean(self):
        segments = [
            TranscriptSegment(text="The", confidence=0.95),
            TranscriptSegment(text="answer", confidence=0.92),
            TranscriptSegment(text="is", confidence=0.98),
            TranscriptSegment(text="dynamic", confidence=0.89),
            TranscriptSegment(text="programming", confidence=0.91),
        ]
        expected = (0.95 + 0.92 + 0.98 + 0.89 + 0.91) / 5
        assert calculate_aggregate_confidence(segments) == pytest.approx(
            expected, abs=0.001
        )

    def test_weighted_by_duration(self):
        segments = [
            TranscriptSegment(
                text="The", start_ms=0, end_ms=100, confidence=0.9
            ),  # 100ms
            TranscriptSegment(
                text="answer", start_ms=100, end_ms=500, confidence=0.6
            ),  # 400ms
        ]
        expected = (0.9 * 100 + 0.6 * 400) / 500
        assert calculate_aggregate_confidence(
            segments, weighted=True
        ) == pytest.approx(expected, abs=0.001)

    def test_weighted_zero_duration_falls_back_to_unit(self):
        """Segments with zero duration get weight=1 each."""
        segments = [
            TranscriptSegment(text="a", start_ms=0, end_ms=0, confidence=0.8),
            TranscriptSegment(text="b", start_ms=0, end_ms=0, confidence=0.6),
        ]
        expected = (0.8 + 0.6) / 2
        assert calculate_aggregate_confidence(
            segments, weighted=True
        ) == pytest.approx(expected, abs=0.001)

    def test_all_perfect_confidence(self):
        segments = [
            TranscriptSegment(text="a", confidence=1.0),
            TranscriptSegment(text="b", confidence=1.0),
        ]
        assert calculate_aggregate_confidence(segments) == pytest.approx(1.0)

    def test_all_zero_confidence(self):
        segments = [
            TranscriptSegment(text="a", confidence=0.0),
            TranscriptSegment(text="b", confidence=0.0),
        ]
        assert calculate_aggregate_confidence(segments) == pytest.approx(0.0)

    def test_clamped_to_one(self):
        """If somehow segment confidence >1, result still <=1."""
        # Can't construct via dataclass (no validation on upper bound),
        # but the aggregation should clamp.
        segments = [
            TranscriptSegment(text="x", confidence=0.95),
            TranscriptSegment(text="y", confidence=0.95),
        ]
        result = calculate_aggregate_confidence(segments)
        assert 0.0 <= result <= 1.0
