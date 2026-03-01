"""
Unit Tests — Intent Classifier

Tests the UtteranceIntentClassification dataclass, RuleBasedIntentClassifier,
and UtteranceIntent / SemanticLevel enums.
"""

from __future__ import annotations

import pytest

from app.interview.exchanges.intent_classifier import (
    InterviewContext,
    RuleBasedIntentClassifier,
    SemanticLevel,
    UtteranceIntent,
    UtteranceIntentClassification,
)


# ═══════════════════════════════════════════════════════════════════════════
# UtteranceIntent enum
# ═══════════════════════════════════════════════════════════════════════════


class TestUtteranceIntentEnum:
    def test_all_values(self):
        values = {e.value for e in UtteranceIntent}
        assert values == {
            "ANSWER",
            "CLARIFICATION",
            "REPEAT",
            "POST_ANSWER",
            "INVALID",
            "INCOMPLETE",
            "UNKNOWN",
        }

    def test_string_coercion(self):
        assert UtteranceIntent("ANSWER") is UtteranceIntent.ANSWER
        assert UtteranceIntent("CLARIFICATION") is UtteranceIntent.CLARIFICATION


class TestSemanticLevelEnum:
    def test_all_values(self):
        values = {e.value for e in SemanticLevel}
        assert values == {"none", "surface", "deep"}


# ═══════════════════════════════════════════════════════════════════════════
# UtteranceIntentClassification dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestUtteranceIntentClassification:
    def test_valid_classification(self):
        c = UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=0.9,
            contains_solution_attempt=True,
            semantic_level=SemanticLevel.DEEP,
        )
        assert c.intent == UtteranceIntent.ANSWER
        assert c.confidence == 0.9
        assert c.contains_solution_attempt is True

    def test_frozen(self):
        c = UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=0.9,
            contains_solution_attempt=True,
            semantic_level=SemanticLevel.DEEP,
        )
        with pytest.raises(AttributeError):
            c.confidence = 0.5  # type: ignore

    def test_invalid_confidence_low(self):
        with pytest.raises(ValueError, match="confidence"):
            UtteranceIntentClassification(
                intent=UtteranceIntent.ANSWER,
                confidence=-0.1,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.NONE,
            )

    def test_invalid_confidence_high(self):
        with pytest.raises(ValueError, match="confidence"):
            UtteranceIntentClassification(
                intent=UtteranceIntent.ANSWER,
                confidence=1.1,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.NONE,
            )

    def test_boundary_confidence_zero(self):
        c = UtteranceIntentClassification(
            intent=UtteranceIntent.UNKNOWN,
            confidence=0.0,
            contains_solution_attempt=False,
            semantic_level=SemanticLevel.NONE,
        )
        assert c.confidence == 0.0

    def test_boundary_confidence_one(self):
        c = UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=1.0,
            contains_solution_attempt=True,
            semantic_level=SemanticLevel.DEEP,
        )
        assert c.confidence == 1.0

    def test_to_audit_dict(self):
        c = UtteranceIntentClassification(
            intent=UtteranceIntent.CLARIFICATION,
            confidence=0.95,
            contains_solution_attempt=False,
            semantic_level=SemanticLevel.SURFACE,
        )
        d = c.to_audit_dict()
        assert d["intent"] == "CLARIFICATION"
        assert d["confidence"] == 0.95
        assert d["contains_solution_attempt"] is False
        assert d["semantic_level"] == "surface"


# ═══════════════════════════════════════════════════════════════════════════
# RuleBasedIntentClassifier
# ═══════════════════════════════════════════════════════════════════════════


def _context(**overrides) -> InterviewContext:
    defaults = dict(
        question_text="What is polymorphism?",
        question_type="text",
        exchange_state="WAITING_INPUT",
    )
    defaults.update(overrides)
    return InterviewContext(**defaults)


class TestRuleBasedIntentClassifier:
    def setup_method(self):
        self.classifier = RuleBasedIntentClassifier()

    def test_empty_transcript_is_invalid(self):
        result = self.classifier.classify("", _context())
        assert result.intent == UtteranceIntent.INVALID
        assert result.confidence >= 0.9

    def test_whitespace_only_is_invalid(self):
        result = self.classifier.classify("   ", _context())
        assert result.intent == UtteranceIntent.INVALID

    def test_none_transcript_is_invalid(self):
        result = self.classifier.classify(None, _context())
        assert result.intent == UtteranceIntent.INVALID

    def test_answer_keywords(self):
        result = self.classifier.classify(
            "I would use a hash table for this problem",
            _context(),
        )
        assert result.intent == UtteranceIntent.ANSWER
        assert result.contains_solution_attempt is True
        assert result.semantic_level == SemanticLevel.DEEP

    def test_clarification_keywords(self):
        result = self.classifier.classify(
            "Can you clarify what you mean by optimal?",
            _context(),
        )
        assert result.intent == UtteranceIntent.CLARIFICATION
        assert result.contains_solution_attempt is False

    def test_repeat_keywords(self):
        result = self.classifier.classify(
            "Could you repeat the question please?",
            _context(),
        )
        assert result.intent == UtteranceIntent.REPEAT

    def test_post_answer_state(self):
        """In POST_ANSWER_WINDOW state, everything is POST_ANSWER."""
        result = self.classifier.classify(
            "Oh wait, I also wanted to mention...",
            _context(exchange_state="POST_ANSWER_WINDOW"),
        )
        assert result.intent == UtteranceIntent.POST_ANSWER

    def test_mixed_clarification_answer_defaults_to_answer(self):
        """Conservative rule: ambiguity → ANSWER."""
        result = self.classifier.classify(
            "Can you clarify? I would use a queue...",
            _context(),
        )
        assert result.intent == UtteranceIntent.ANSWER

    def test_incomplete_fragment(self):
        result = self.classifier.classify(
            "I think...",
            _context(),
        )
        assert result.intent == UtteranceIntent.INCOMPLETE

    def test_default_answer_for_unknown(self):
        """Ambiguous text defaults to ANSWER (conservative)."""
        result = self.classifier.classify(
            "This is a general statement about the topic at hand",
            _context(),
        )
        assert result.intent == UtteranceIntent.ANSWER

    def test_classifier_version(self):
        result = self.classifier.classify("My approach is to use BFS", _context())
        assert result.classifier_version == "rule-based-v1"

    def test_raw_transcript_preserved(self):
        transcript = "I would use dynamic programming"
        result = self.classifier.classify(transcript, _context())
        assert result.raw_transcript == transcript
