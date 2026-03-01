"""
Unit tests for IntentClassifier.

Covers: all intent classifications, ASR confidence gating,
post-answer detection, silence detection, keyword matching,
and determinism.
"""

import pytest

from app.audio.analysis.contracts import IntentClassificationRequest
from app.audio.analysis.intent_classifier import IntentClassifier


@pytest.fixture
def classifier():
    return IntentClassifier()


# ---------------------------------------------------------------------------
# POST_ANSWER Detection
# ---------------------------------------------------------------------------


class TestPostAnswer:

    def test_post_answer_after_submission(self, classifier):
        """Any speech after previous submission → POST_ANSWER."""
        request = IntentClassificationRequest(
            transcript="I also want to mention sorting.",
            confidence_score=0.95,
            previous_submissions=1,
        )
        result = classifier.classify(request)
        assert result.intent == "POST_ANSWER"
        assert result.confidence == 0.95
        assert result.contains_solution_attempt is False

    def test_post_answer_multiple_submissions(self, classifier):
        request = IntentClassificationRequest(
            transcript="Wait, I have another idea.",
            confidence_score=0.95,
            previous_submissions=3,
        )
        result = classifier.classify(request)
        assert result.intent == "POST_ANSWER"


# ---------------------------------------------------------------------------
# ASR Confidence Gating
# ---------------------------------------------------------------------------


class TestASRConfidence:

    def test_low_asr_confidence_invalid(self, classifier):
        """Low ASR confidence → INVALID with warning."""
        request = IntentClassificationRequest(
            transcript="mumble mumble",
            confidence_score=0.5,
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"
        assert result.low_asr_confidence_warning is True
        assert result.confidence == 0.80

    def test_borderline_asr_confidence(self, classifier):
        """Exactly at threshold → passes."""
        request = IntentClassificationRequest(
            transcript="I would use an algorithm",
            confidence_score=0.70,
        )
        result = classifier.classify(request)
        assert result.intent != "INVALID" or result.low_asr_confidence_warning is False


# ---------------------------------------------------------------------------
# Silence / Empty Detection
# ---------------------------------------------------------------------------


class TestSilenceDetection:

    def test_empty_transcript(self, classifier):
        request = IntentClassificationRequest(
            transcript="", confidence_score=0.95
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"
        assert result.low_asr_confidence_warning is False

    def test_silence_marker(self, classifier):
        request = IntentClassificationRequest(
            transcript="[silence]", confidence_score=0.95
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"

    def test_noise_marker(self, classifier):
        request = IntentClassificationRequest(
            transcript="[noise]", confidence_score=0.95
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"

    def test_filler_only_silence(self, classifier):
        request = IntentClassificationRequest(
            transcript="um", confidence_score=0.95
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"


# ---------------------------------------------------------------------------
# ANSWER Detection
# ---------------------------------------------------------------------------


class TestAnswerDetection:

    def test_solution_keywords(self, classifier):
        request = IntentClassificationRequest(
            transcript="I would use a recursive algorithm to solve this.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "ANSWER"
        assert result.contains_solution_attempt is True
        assert result.semantic_depth == "deep"

    def test_code_keywords(self, classifier):
        request = IntentClassificationRequest(
            transcript="I would implement a for loop to iterate through the array.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "ANSWER"
        assert result.contains_solution_attempt is True

    def test_data_structure_keywords(self, classifier):
        request = IntentClassificationRequest(
            transcript="I would use a stack to keep track of elements.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "ANSWER"


# ---------------------------------------------------------------------------
# CLARIFICATION Detection
# ---------------------------------------------------------------------------


class TestClarificationDetection:

    def test_clarification_keywords(self, classifier):
        request = IntentClassificationRequest(
            transcript="What do you mean by that?",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "CLARIFICATION"
        assert result.contains_solution_attempt is False
        assert result.semantic_depth == "surface"

    def test_explain_request(self, classifier):
        request = IntentClassificationRequest(
            transcript="Can you explain the problem again?",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "CLARIFICATION"


# ---------------------------------------------------------------------------
# REPEAT Detection
# ---------------------------------------------------------------------------


class TestRepeatDetection:

    def test_repeat_phrase(self, classifier):
        request = IntentClassificationRequest(
            transcript="Can you say that again please?",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "REPEAT"
        assert result.semantic_depth == "none"

    def test_one_more_time(self, classifier):
        request = IntentClassificationRequest(
            transcript="One more time please.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "REPEAT"


# ---------------------------------------------------------------------------
# UNKNOWN (Ambiguous)
# ---------------------------------------------------------------------------


class TestUnknown:

    def test_ambiguous_utterance(self, classifier):
        request = IntentClassificationRequest(
            transcript="Hmm well let me think about that.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "UNKNOWN"
        assert result.confidence == 0.60

    def test_generic_acknowledgement(self, classifier):
        request = IntentClassificationRequest(
            transcript="Okay sure.",
            confidence_score=0.95,
        )
        result = classifier.classify(request)
        assert result.intent == "UNKNOWN"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_same_output(self, classifier):
        request = IntentClassificationRequest(
            transcript="I would use recursion to solve this problem.",
            confidence_score=0.95,
        )
        r1 = classifier.classify(request)
        r2 = classifier.classify(request)

        assert r1.intent == r2.intent
        assert r1.confidence == r2.confidence
        assert r1.contains_solution_attempt == r2.contains_solution_attempt
        assert r1.semantic_depth == r2.semantic_depth
        assert r1.low_asr_confidence_warning == r2.low_asr_confidence_warning


# ---------------------------------------------------------------------------
# Priority Order
# ---------------------------------------------------------------------------


class TestPriorityOrder:

    def test_post_answer_overrides_everything(self, classifier):
        """POST_ANSWER check runs before any keyword checks."""
        request = IntentClassificationRequest(
            transcript="I would use an algorithm.",
            confidence_score=0.95,
            previous_submissions=1,
        )
        result = classifier.classify(request)
        assert result.intent == "POST_ANSWER"

    def test_asr_check_before_keywords(self, classifier):
        """Low ASR confidence checked before keyword analysis."""
        request = IntentClassificationRequest(
            transcript="I would use an algorithm.",
            confidence_score=0.3,
        )
        result = classifier.classify(request)
        assert result.intent == "INVALID"
        assert result.low_asr_confidence_warning is True
