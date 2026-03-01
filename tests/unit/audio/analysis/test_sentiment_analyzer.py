"""
Unit tests for SentimentAnalyzer.

Covers: positive/negative/neutral sentiment, hesitation detection,
frustration detection, score normalisation, and edge cases.
"""

import pytest

from app.audio.analysis.sentiment_analyzer import SentimentAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    return SentimentAnalyzer()


# ---------------------------------------------------------------------------
# Basic Sentiment
# ---------------------------------------------------------------------------


class TestBasicSentiment:

    def test_positive_sentiment(self, analyzer):
        result = analyzer.analyze("I'm confident this is the correct solution.")
        assert result.sentiment_score > 0.0
        assert result.confidence_level in ("medium", "high")

    def test_negative_sentiment(self, analyzer):
        result = analyzer.analyze(
            "I really don't know how to solve this problem."
        )
        assert result.sentiment_score < 0.0

    def test_neutral_sentiment(self, analyzer):
        result = analyzer.analyze("The function takes an integer parameter.")
        assert -0.3 < result.sentiment_score < 0.3

    def test_empty_transcript(self, analyzer):
        result = analyzer.analyze("")
        assert result.sentiment_score == 0.0
        assert result.confidence_level == "low"
        assert result.hesitation_detected is False

    def test_whitespace_only(self, analyzer):
        result = analyzer.analyze("   ")
        assert result.sentiment_score == 0.0


# ---------------------------------------------------------------------------
# Score Normalisation
# ---------------------------------------------------------------------------


class TestScoreNormalisation:

    def test_score_always_in_range(self, analyzer):
        """Sentiment score always between -1.0 and +1.0."""
        transcripts = [
            "Amazing wonderful excellent perfect!",
            "Terrible horrible awful worst ever!",
            "Neutral text about algorithms.",
            "",
        ]
        for t in transcripts:
            result = analyzer.analyze(t)
            assert -1.0 <= result.sentiment_score <= 1.0


# ---------------------------------------------------------------------------
# Hesitation Detection
# ---------------------------------------------------------------------------


class TestHesitationDetection:

    def test_hesitation_from_filler_rate(self, analyzer):
        """Hesitation detected when filler rate exceeds threshold."""
        result = analyzer.analyze(
            "Um, I think, uh, maybe, like, I don't know",
            filler_rate=0.5,
        )
        assert result.hesitation_detected is True

    def test_hesitation_from_keywords(self, analyzer):
        """Hesitation detected from uncertainty keywords."""
        result = analyzer.analyze("I don't know the answer.")
        assert result.hesitation_detected is True

    def test_no_hesitation_confident(self, analyzer):
        """No hesitation in confident response."""
        result = analyzer.analyze(
            "The answer is dynamic programming.",
            filler_rate=0.0,
        )
        assert result.hesitation_detected is False


# ---------------------------------------------------------------------------
# Frustration Detection
# ---------------------------------------------------------------------------


class TestFrustrationDetection:

    def test_frustration_detected(self, analyzer):
        result = analyzer.analyze(
            "This problem is really difficult and I can't figure it out."
        )
        assert result.sentiment_score < -0.3
        assert result.frustration_detected is True

    def test_no_frustration_positive(self, analyzer):
        result = analyzer.analyze("I'm very happy with this solution.")
        assert result.frustration_detected is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_same_output(self, analyzer):
        transcript = "I'm not sure about this approach."
        r1 = analyzer.analyze(transcript)
        r2 = analyzer.analyze(transcript)
        assert r1.sentiment_score == r2.sentiment_score
        assert r1.confidence_level == r2.confidence_level
        assert r1.hesitation_detected == r2.hesitation_detected
        assert r1.frustration_detected == r2.frustration_detected
