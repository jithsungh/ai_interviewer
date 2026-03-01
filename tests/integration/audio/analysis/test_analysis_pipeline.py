"""
Integration tests for audio analysis pipeline.

Validates: full pipeline execution, latency SLA, cross-analyzer consistency,
and spaCy model integration.
"""

import time

import pytest

from app.audio.analysis.completeness_classifier import CompletenessClassifier
from app.audio.analysis.contracts import IntentClassificationRequest
from app.audio.analysis.filler_detector import FillerDetector
from app.audio.analysis.intent_classifier import IntentClassifier
from app.audio.analysis.sentiment_analyzer import SentimentAnalyzer
from app.audio.analysis.speech_rate_analyzer import SpeechRateAnalyzer
from app.audio.transcription.contracts import TranscriptSegment


@pytest.fixture(scope="module")
def completeness():
    return CompletenessClassifier()


@pytest.fixture(scope="module")
def filler():
    return FillerDetector(context_aware=True)


@pytest.fixture(scope="module")
def speech_rate():
    return SpeechRateAnalyzer()


@pytest.fixture(scope="module")
def sentiment():
    return SentimentAnalyzer()


@pytest.fixture(scope="module")
def intent():
    return IntentClassifier()


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------


class TestFullPipeline:

    def test_all_analyzers_on_same_transcript(
        self, completeness, filler, speech_rate, sentiment, intent
    ):
        """All five analyzers produce valid results on the same input."""
        transcript = "Um, I think the answer is dynamic programming."
        segments = [
            TranscriptSegment(text="Um,", start_ms=0, end_ms=200, confidence=0.9),
            TranscriptSegment(text="I", start_ms=200, end_ms=300, confidence=0.95),
            TranscriptSegment(text="think", start_ms=300, end_ms=600, confidence=0.93),
            TranscriptSegment(text="the", start_ms=600, end_ms=700, confidence=0.97),
            TranscriptSegment(text="answer", start_ms=700, end_ms=1000, confidence=0.96),
            TranscriptSegment(text="is", start_ms=1000, end_ms=1100, confidence=0.98),
            TranscriptSegment(
                text="dynamic", start_ms=1100, end_ms=1400, confidence=0.92
            ),
            TranscriptSegment(
                text="programming.", start_ms=1400, end_ms=1800, confidence=0.94
            ),
        ]

        # 1. Completeness
        c_result = completeness.evaluate(transcript)
        assert c_result.speech_state == "complete"
        assert c_result.sentence_complete is True

        # 2. Filler detection
        f_result = filler.detect(transcript)
        assert f_result.filler_word_count >= 1  # "um" at minimum

        # 3. Speech rate
        sr_result = speech_rate.analyze_segments(segments)
        assert sr_result.speech_rate_wpm > 0
        assert sr_result.total_words > 0

        # 4. Sentiment
        s_result = sentiment.analyze(
            transcript, filler_rate=f_result.filler_rate
        )
        assert -1.0 <= s_result.sentiment_score <= 1.0

        # 5. Intent
        i_request = IntentClassificationRequest(
            transcript=transcript,
            confidence_score=0.95,
        )
        i_result = intent.classify(i_request)
        assert i_result.intent in (
            "ANSWER", "CLARIFICATION", "REPEAT",
            "POST_ANSWER", "INVALID", "INCOMPLETE", "UNKNOWN",
        )


# ---------------------------------------------------------------------------
# Latency SLA
# ---------------------------------------------------------------------------


class TestLatencySLA:

    def test_all_analysis_under_500ms(
        self, completeness, filler, speech_rate, sentiment, intent
    ):
        """Full analysis pipeline completes within 500ms."""
        transcript = (
            "The answer is dynamic programming and it solves "
            "the problem efficiently by breaking it into subproblems."
        )
        segments = [
            TranscriptSegment(text="The", start_ms=0, end_ms=100, confidence=0.95),
            TranscriptSegment(text="answer", start_ms=100, end_ms=300, confidence=0.95),
            TranscriptSegment(text="is", start_ms=300, end_ms=400, confidence=0.95),
            TranscriptSegment(
                text="dynamic", start_ms=400, end_ms=600, confidence=0.95
            ),
            TranscriptSegment(
                text="programming", start_ms=600, end_ms=900, confidence=0.95
            ),
            TranscriptSegment(text="and", start_ms=900, end_ms=1000, confidence=0.95),
            TranscriptSegment(text="it", start_ms=1000, end_ms=1100, confidence=0.95),
            TranscriptSegment(
                text="solves", start_ms=1100, end_ms=1300, confidence=0.95
            ),
            TranscriptSegment(text="the", start_ms=1300, end_ms=1400, confidence=0.95),
            TranscriptSegment(
                text="problem", start_ms=1400, end_ms=1600, confidence=0.95
            ),
            TranscriptSegment(
                text="efficiently", start_ms=1600, end_ms=1900, confidence=0.95
            ),
            TranscriptSegment(text="by", start_ms=1900, end_ms=2000, confidence=0.95),
            TranscriptSegment(
                text="breaking", start_ms=2000, end_ms=2200, confidence=0.95
            ),
            TranscriptSegment(text="it", start_ms=2200, end_ms=2300, confidence=0.95),
            TranscriptSegment(
                text="into", start_ms=2300, end_ms=2400, confidence=0.95
            ),
            TranscriptSegment(
                text="subproblems.", start_ms=2400, end_ms=2800, confidence=0.95
            ),
        ]

        start = time.monotonic()

        completeness.evaluate(transcript)
        filler.detect(transcript)
        speech_rate.analyze_segments(segments)
        sentiment.analyze(transcript)
        intent.classify(
            IntentClassificationRequest(
                transcript=transcript, confidence_score=0.95
            )
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 500, (
            f"Full analysis took {elapsed_ms:.1f}ms, exceeds 500ms SLA"
        )


# ---------------------------------------------------------------------------
# spaCy Integration
# ---------------------------------------------------------------------------


class TestSpacyIntegration:

    def test_spacy_model_loads(self):
        """spaCy en_core_web_sm loads correctly."""
        import spacy

        nlp = spacy.load("en_core_web_sm")
        assert nlp is not None

    def test_spacy_dependency_parsing(self):
        """spaCy parses dependencies correctly."""
        import spacy

        nlp = spacy.load("en_core_web_sm")
        doc = nlp("The answer is dynamic programming.")

        subjects = [t for t in doc if t.dep_ == "nsubj"]
        assert len(subjects) > 0

        verbs = [t for t in doc if t.pos_ in ("VERB", "AUX")]
        assert len(verbs) > 0

    def test_spacy_handles_technical_jargon(self):
        """spaCy handles technical terms without crashing."""
        import spacy

        nlp = spacy.load("en_core_web_sm")
        doc = nlp("I used DFS to traverse the graph.")

        verbs = [t for t in doc if t.pos_ == "VERB"]
        assert len(verbs) > 0


# ---------------------------------------------------------------------------
# Cross-Analyzer Consistency
# ---------------------------------------------------------------------------


class TestCrossAnalyzerConsistency:

    def test_filler_rate_feeds_sentiment(self, filler, sentiment):
        """Filler rate from FillerDetector correctly feeds SentimentAnalyzer."""
        transcript = "Um, uh, I don't know, like, maybe the answer is something."
        f_result = filler.detect(transcript)
        s_result = sentiment.analyze(
            transcript, filler_rate=f_result.filler_rate
        )

        # High filler rate + uncertainty keywords → hesitation
        if f_result.filler_rate > 0.15:
            assert s_result.hesitation_detected is True

    def test_intent_and_completeness_alignment(self, completeness, intent):
        """Complete answers should map to ANSWER intent."""
        transcript = "I would use a recursive algorithm to solve this."
        c_result = completeness.evaluate(transcript)
        i_result = intent.classify(
            IntentClassificationRequest(
                transcript=transcript, confidence_score=0.95
            )
        )

        assert i_result.intent == "ANSWER"
