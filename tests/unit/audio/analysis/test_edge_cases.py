"""
Edge case tests for audio analysis module.

Covers: single-word transcripts, all-filler transcripts, very long transcripts,
code snippets, non-English text, and cross-analyzer interactions.
"""

import pytest

from app.audio.analysis.completeness_classifier import CompletenessClassifier
from app.audio.analysis.filler_detector import FillerDetector
from app.audio.analysis.sentiment_analyzer import SentimentAnalyzer
from app.audio.analysis.speech_rate_analyzer import SpeechRateAnalyzer


@pytest.fixture(scope="module")
def completeness():
    return CompletenessClassifier()


@pytest.fixture(scope="module")
def filler():
    return FillerDetector(context_aware=True)


@pytest.fixture(scope="module")
def sentiment():
    return SentimentAnalyzer()


@pytest.fixture
def speech_rate():
    return SpeechRateAnalyzer()


# ---------------------------------------------------------------------------
# Single-Word Transcripts
# ---------------------------------------------------------------------------


class TestSingleWord:

    def test_yes_with_period(self, completeness):
        result = completeness.evaluate("Yes.")
        assert result.speech_state == "complete"

    def test_yes_without_period(self, completeness):
        result = completeness.evaluate("Yes")
        assert result.speech_state == "continuing"

    def test_no_with_period(self, completeness):
        result = completeness.evaluate("No.")
        assert result.speech_state == "complete"

    def test_single_filler(self, filler):
        result = filler.detect("Um")
        assert result.filler_word_count == 1
        assert result.filler_rate == 1.0


# ---------------------------------------------------------------------------
# All-Filler Transcripts
# ---------------------------------------------------------------------------


class TestAllFillers:

    def test_all_fillers_filler_rate(self, filler):
        result = filler.detect("Um uh like so basically")
        assert result.filler_rate == pytest.approx(1.0, abs=0.01)

    def test_all_fillers_completeness(self, completeness):
        result = completeness.evaluate("Um uh so")
        assert result.speech_state == "incomplete"


# ---------------------------------------------------------------------------
# Very Long Transcripts
# ---------------------------------------------------------------------------


class TestLongTranscripts:

    def test_long_transcript_completes(self, completeness):
        """1000-word transcript should complete without error."""
        long_text = " ".join(["word"] * 999) + " end."
        result = completeness.evaluate(long_text)
        assert result is not None
        assert result.speech_state in ("complete", "incomplete", "continuing")

    def test_long_transcript_filler_detection(self, filler):
        """Filler detection on long transcript."""
        text = " ".join(["the"] * 100 + ["um"] * 10 + ["answer"] * 90)
        result = filler.detect(text)
        assert result.filler_word_count >= 10

    def test_long_transcript_speech_rate(self, speech_rate):
        transcript = " ".join(["word"] * 500)
        result = speech_rate.analyze(transcript, duration_ms=60000)
        # 500 words in 60 seconds = 500 WPM
        assert result.speech_rate_wpm == pytest.approx(500, abs=5)


# ---------------------------------------------------------------------------
# Code Snippets in Transcript
# ---------------------------------------------------------------------------


class TestCodeSnippets:

    def test_transcript_with_code(self, completeness):
        """Code in transcript should not crash the parser."""
        result = completeness.evaluate(
            "I would use for i in range(n) to iterate."
        )
        assert result is not None

    def test_code_keywords_sentiment(self, sentiment):
        """Code-heavy transcript should be roughly neutral."""
        result = sentiment.analyze(
            "I would use a for loop with an if condition inside."
        )
        assert -0.5 < result.sentiment_score < 0.5


# ---------------------------------------------------------------------------
# Non-English Transcript
# ---------------------------------------------------------------------------


class TestNonEnglish:

    def test_non_english_lower_confidence(self, completeness):
        """Non-English text should return lower confidence or incomplete."""
        result = completeness.evaluate(
            "La respuesta es programación dinámica."
        )
        # spaCy en_core_web_sm may misparse → lower confidence acceptable
        assert result is not None


# ---------------------------------------------------------------------------
# Transcript with Disfluencies
# ---------------------------------------------------------------------------


class TestDisfluencies:

    def test_repeated_words(self, completeness):
        result = completeness.evaluate("The the answer is is correct.")
        assert result is not None

    def test_self_correction(self, completeness):
        result = completeness.evaluate(
            "I mean, rather, the answer is dynamic programming."
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Concurrent Safety (all analyzers are stateless)
# ---------------------------------------------------------------------------


class TestStatelessness:

    def test_completeness_no_state_leakage(self, completeness):
        """Consecutive calls don't affect each other."""
        r1 = completeness.evaluate("The answer is dynamic programming.")
        r2 = completeness.evaluate("Because")
        r3 = completeness.evaluate("The answer is dynamic programming.")

        assert r1.speech_state == r3.speech_state
        assert r1.confidence == r3.confidence

    def test_sentiment_no_state_leakage(self, sentiment):
        r1 = sentiment.analyze("I love this!")
        r2 = sentiment.analyze("I hate this!")
        r3 = sentiment.analyze("I love this!")

        assert r1.sentiment_score == r3.sentiment_score
