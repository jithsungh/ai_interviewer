"""
Unit tests for audio analysis contracts (dataclass validation).

Covers input validation, immutability, enums, and edge cases.
"""

import pytest

from app.audio.analysis.contracts import (
    CompletenessRequest,
    CompletenessResult,
    ConfidenceLevel,
    FillerDetectionRequest,
    FillerDetectionResult,
    FillerWord,
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentType,
    SemanticDepth,
    SentimentRequest,
    SentimentResult,
    SpeechRateRequest,
    SpeechRateResult,
    SpeechState,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestEnums:

    def test_speech_state_values(self):
        assert SpeechState.COMPLETE == "complete"
        assert SpeechState.INCOMPLETE == "incomplete"
        assert SpeechState.CONTINUING == "continuing"

    def test_intent_type_values(self):
        assert IntentType.ANSWER == "ANSWER"
        assert IntentType.CLARIFICATION == "CLARIFICATION"
        assert IntentType.REPEAT == "REPEAT"
        assert IntentType.POST_ANSWER == "POST_ANSWER"
        assert IntentType.INVALID == "INVALID"
        assert IntentType.UNKNOWN == "UNKNOWN"

    def test_semantic_depth_values(self):
        assert SemanticDepth.NONE == "none"
        assert SemanticDepth.SURFACE == "surface"
        assert SemanticDepth.DEEP == "deep"

    def test_confidence_level_values(self):
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.LOW == "low"


# ---------------------------------------------------------------------------
# Input Contract Tests
# ---------------------------------------------------------------------------


class TestCompletenessRequest:

    def test_valid_construction(self):
        req = CompletenessRequest(transcript="Hello world")
        assert req.transcript == "Hello world"
        assert req.segments == ()

    def test_none_transcript_raises(self):
        with pytest.raises(ValueError, match="None"):
            CompletenessRequest(transcript=None)

    def test_immutable(self):
        req = CompletenessRequest(transcript="test")
        with pytest.raises(AttributeError):
            req.transcript = "changed"


class TestFillerDetectionRequest:

    def test_valid_construction(self):
        req = FillerDetectionRequest(transcript="Hello")
        assert req.context_aware is True

    def test_context_aware_default(self):
        req = FillerDetectionRequest(transcript="test")
        assert req.context_aware is True

    def test_none_transcript_raises(self):
        with pytest.raises(ValueError, match="None"):
            FillerDetectionRequest(transcript=None)


class TestSpeechRateRequest:

    def test_valid_construction(self):
        req = SpeechRateRequest(transcript="Hello world")
        assert req.exclude_pauses is True
        assert req.segments == ()


class TestSentimentRequest:

    def test_valid_construction(self):
        req = SentimentRequest(transcript="Hello")
        assert req.audio_features is None


class TestIntentClassificationRequest:

    def test_valid_construction(self):
        req = IntentClassificationRequest(
            transcript="Hello",
            confidence_score=0.9,
        )
        assert req.previous_submissions == 0
        assert req.question_context is None

    def test_invalid_confidence_score_high(self):
        with pytest.raises(ValueError, match="confidence_score"):
            IntentClassificationRequest(transcript="test", confidence_score=1.5)

    def test_invalid_confidence_score_low(self):
        with pytest.raises(ValueError, match="confidence_score"):
            IntentClassificationRequest(transcript="test", confidence_score=-0.1)

    def test_negative_previous_submissions(self):
        with pytest.raises(ValueError, match="previous_submissions"):
            IntentClassificationRequest(
                transcript="test",
                confidence_score=0.9,
                previous_submissions=-1,
            )

    def test_immutable(self):
        req = IntentClassificationRequest(transcript="test", confidence_score=0.9)
        with pytest.raises(AttributeError):
            req.confidence_score = 0.5


# ---------------------------------------------------------------------------
# Output Contract Tests
# ---------------------------------------------------------------------------


class TestCompletenessResult:

    def test_valid_complete(self):
        result = CompletenessResult(
            speech_state="complete",
            sentence_complete=True,
            confidence=0.9,
        )
        assert result.speech_state == "complete"
        assert result.incomplete_reason is None

    def test_valid_incomplete(self):
        result = CompletenessResult(
            speech_state="incomplete",
            sentence_complete=False,
            confidence=0.85,
            incomplete_reason="ends_with_conjunction",
        )
        assert result.incomplete_reason == "ends_with_conjunction"

    def test_invalid_speech_state(self):
        with pytest.raises(ValueError, match="speech_state"):
            CompletenessResult(
                speech_state="invalid_state",
                sentence_complete=False,
                confidence=0.5,
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError, match="confidence"):
            CompletenessResult(
                speech_state="complete",
                sentence_complete=True,
                confidence=1.5,
            )

    def test_immutable(self):
        result = CompletenessResult(
            speech_state="complete", sentence_complete=True, confidence=0.9
        )
        with pytest.raises(AttributeError):
            result.speech_state = "incomplete"


class TestFillerWord:

    def test_valid_construction(self):
        fw = FillerWord(word="um", position=0)
        assert fw.timestamp_ms is None

    def test_empty_word_raises(self):
        with pytest.raises(ValueError, match="empty"):
            FillerWord(word="", position=0)

    def test_negative_position_raises(self):
        with pytest.raises(ValueError, match="position"):
            FillerWord(word="um", position=-1)


class TestFillerDetectionResult:

    def test_valid_construction(self):
        result = FillerDetectionResult(
            filler_word_count=3,
            filler_rate=0.3,
            filler_positions=(),
        )
        assert result.filler_word_count == 3

    def test_negative_count_raises(self):
        with pytest.raises(ValueError, match="filler_word_count"):
            FillerDetectionResult(filler_word_count=-1, filler_rate=0.0)

    def test_filler_rate_out_of_range(self):
        with pytest.raises(ValueError, match="filler_rate"):
            FillerDetectionResult(filler_word_count=0, filler_rate=1.5)


class TestSpeechRateResult:

    def test_valid_construction(self):
        result = SpeechRateResult(
            speech_rate_wpm=150.0,
            total_words=10,
            speech_duration_ms=4000,
            total_duration_ms=5000,
            long_pause_count=1,
            longest_pause_ms=1500,
        )
        assert result.speech_rate_wpm == 150.0

    def test_negative_wpm_raises(self):
        with pytest.raises(ValueError, match="speech_rate_wpm"):
            SpeechRateResult(
                speech_rate_wpm=-1, total_words=0,
                speech_duration_ms=0, total_duration_ms=0,
                long_pause_count=0, longest_pause_ms=0,
            )


class TestSentimentResult:

    def test_valid_construction(self):
        result = SentimentResult(
            sentiment_score=0.5,
            confidence_level="high",
            hesitation_detected=False,
            frustration_detected=False,
        )
        assert result.sentiment_score == 0.5

    def test_score_out_of_range(self):
        with pytest.raises(ValueError, match="sentiment_score"):
            SentimentResult(
                sentiment_score=1.5,
                confidence_level="high",
                hesitation_detected=False,
                frustration_detected=False,
            )

    def test_invalid_confidence_level(self):
        with pytest.raises(ValueError, match="confidence_level"):
            SentimentResult(
                sentiment_score=0.5,
                confidence_level="invalid",
                hesitation_detected=False,
                frustration_detected=False,
            )


class TestIntentClassificationResult:

    def test_valid_construction(self):
        result = IntentClassificationResult(
            intent="ANSWER",
            confidence=0.9,
            contains_solution_attempt=True,
            semantic_depth="deep",
            low_asr_confidence_warning=False,
        )
        assert result.intent == "ANSWER"

    def test_invalid_intent(self):
        with pytest.raises(ValueError, match="intent"):
            IntentClassificationResult(
                intent="BOGUS",
                confidence=0.9,
                contains_solution_attempt=False,
                semantic_depth="none",
                low_asr_confidence_warning=False,
            )

    def test_invalid_semantic_depth(self):
        with pytest.raises(ValueError, match="semantic_depth"):
            IntentClassificationResult(
                intent="ANSWER",
                confidence=0.9,
                contains_solution_attempt=True,
                semantic_depth="ultra",
                low_asr_confidence_warning=False,
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError, match="confidence"):
            IntentClassificationResult(
                intent="ANSWER",
                confidence=1.5,
                contains_solution_attempt=True,
                semantic_depth="deep",
                low_asr_confidence_warning=False,
            )
