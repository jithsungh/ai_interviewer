"""
Unit tests for SpeechRateAnalyzer.

Covers: WPM calculation, pause detection, segment-based analysis,
empty transcripts, and abnormal speech rate thresholds.
"""

import pytest

from app.audio.analysis.speech_rate_analyzer import SpeechRateAnalyzer
from app.audio.transcription.contracts import TranscriptSegment


@pytest.fixture
def analyzer():
    return SpeechRateAnalyzer()


# ---------------------------------------------------------------------------
# Simple WPM Calculation
# ---------------------------------------------------------------------------


class TestSimpleAnalysis:

    def test_wpm_calculation(self, analyzer):
        """9 words in 3 seconds = 180 WPM."""
        transcript = "one two three four five six seven eight nine"
        result = analyzer.analyze(transcript, duration_ms=3000)
        assert result.speech_rate_wpm == pytest.approx(180, abs=1)
        assert result.total_words == 9

    def test_empty_transcript_zero_wpm(self, analyzer):
        result = analyzer.analyze("", duration_ms=1000)
        assert result.speech_rate_wpm == 0.0
        assert result.total_words == 0

    def test_zero_duration(self, analyzer):
        result = analyzer.analyze("hello world", duration_ms=0)
        assert result.speech_rate_wpm == 0.0

    def test_negative_duration(self, analyzer):
        result = analyzer.analyze("hello", duration_ms=-100)
        assert result.speech_rate_wpm == 0.0


# ---------------------------------------------------------------------------
# Segment-Based Analysis
# ---------------------------------------------------------------------------


class TestSegmentAnalysis:

    def test_segments_with_pause(self, analyzer):
        """Two segments with a 2-second gap → 1 long pause."""
        segments = [
            TranscriptSegment(text="First", start_ms=0, end_ms=500, confidence=0.9),
            TranscriptSegment(
                text="Second", start_ms=2500, end_ms=3000, confidence=0.9
            ),
        ]
        result = analyzer.analyze_segments(segments)
        assert result.long_pause_count == 1
        assert result.longest_pause_ms == 2000

    def test_speech_rate_excludes_pauses(self, analyzer):
        """WPM calculated on speech time only, excluding pauses."""
        segments = [
            TranscriptSegment(
                text="one two three", start_ms=0, end_ms=2000, confidence=0.9
            ),
            # 5 second pause
            TranscriptSegment(
                text="four five six seven",
                start_ms=7000,
                end_ms=10000,
                confidence=0.9,
            ),
        ]
        result = analyzer.analyze_segments(segments)

        # 7 words over 5 seconds actual speech = 84 WPM
        assert result.speech_duration_ms == 5000
        assert result.total_duration_ms == 10000
        assert result.speech_rate_wpm == pytest.approx(84, abs=5)

    def test_no_pauses(self, analyzer):
        """Consecutive segments with no gaps."""
        segments = [
            TranscriptSegment(text="hello", start_ms=0, end_ms=500, confidence=0.9),
            TranscriptSegment(
                text="world", start_ms=500, end_ms=1000, confidence=0.9
            ),
        ]
        result = analyzer.analyze_segments(segments)
        assert result.long_pause_count == 0
        assert result.longest_pause_ms == 0
        assert result.speech_duration_ms == result.total_duration_ms

    def test_empty_segments(self, analyzer):
        result = analyzer.analyze_segments([])
        assert result.speech_rate_wpm == 0.0
        assert result.total_words == 0

    def test_single_segment(self, analyzer):
        segments = [
            TranscriptSegment(
                text="hello world", start_ms=0, end_ms=1000, confidence=0.9
            ),
        ]
        result = analyzer.analyze_segments(segments)
        assert result.total_words == 2
        assert result.long_pause_count == 0


# ---------------------------------------------------------------------------
# Speech Rate Thresholds
# ---------------------------------------------------------------------------


class TestThresholds:

    def test_slow_threshold(self):
        analyzer = SpeechRateAnalyzer(slow_threshold_wpm=80)
        assert analyzer.slow_threshold_wpm == 80

        # 5 words in 5 seconds = 60 WPM (below threshold)
        result = analyzer.analyze("one two three four five", duration_ms=5000)
        assert result.speech_rate_wpm < analyzer.slow_threshold_wpm

    def test_fast_threshold(self):
        analyzer = SpeechRateAnalyzer(fast_threshold_wpm=200)
        assert analyzer.fast_threshold_wpm == 200

        # 30 words in 6 seconds = 300 WPM (above threshold)
        transcript = " ".join(["word"] * 30)
        result = analyzer.analyze(transcript, duration_ms=6000)
        assert result.speech_rate_wpm > analyzer.fast_threshold_wpm


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_same_output(self, analyzer):
        segments = [
            TranscriptSegment(
                text="one two three", start_ms=0, end_ms=2000, confidence=0.9
            ),
            TranscriptSegment(
                text="four five", start_ms=5000, end_ms=6000, confidence=0.9
            ),
        ]
        r1 = analyzer.analyze_segments(segments)
        r2 = analyzer.analyze_segments(segments)
        assert r1.speech_rate_wpm == r2.speech_rate_wpm
        assert r1.long_pause_count == r2.long_pause_count
