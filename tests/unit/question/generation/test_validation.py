"""
Unit Tests — Post-Generation Validation

Tests validate_generated_question() and individual check functions.
Pure domain logic — no mocks needed (except cosine_similarity bypass).
"""

import pytest

from app.question.generation.domain.entities import GeneratedQuestionOutput
from app.question.generation.domain.validation import (
    ValidationResult,
    check_difficulty_match,
    check_not_empty,
    check_semantic_similarity,
    check_topic_allowed,
    validate_generated_question,
)


# ════════════════════════════════════════════════════════════════════════════
# check_difficulty_match
# ════════════════════════════════════════════════════════════════════════════


class TestDifficultyMatch:

    def test_exact_match(self):
        assert check_difficulty_match("medium", "medium") is True

    def test_case_insensitive(self):
        assert check_difficulty_match("HARD", "hard") is True

    def test_mismatch(self):
        assert check_difficulty_match("easy", "hard") is False

    def test_whitespace_tolerated(self):
        assert check_difficulty_match("  medium  ", "medium") is True


# ════════════════════════════════════════════════════════════════════════════
# check_topic_allowed
# ════════════════════════════════════════════════════════════════════════════


class TestTopicAllowed:

    def test_topic_in_list(self):
        assert check_topic_allowed("algorithms", ["algorithms", "data_structures"]) is True

    def test_topic_not_in_list(self):
        assert check_topic_allowed("microservices", ["algorithms"]) is False

    def test_case_insensitive(self):
        assert check_topic_allowed("Algorithms", ["algorithms"]) is True

    def test_empty_allowed_list_permissive(self):
        assert check_topic_allowed("anything", []) is True


# ════════════════════════════════════════════════════════════════════════════
# check_not_empty
# ════════════════════════════════════════════════════════════════════════════


class TestNotEmpty:

    def test_valid_texts(self):
        ok, reason = check_not_empty(
            "What is the time complexity of quicksort?",
            "O(n log n) average, O(n^2) worst case."
        )
        assert ok is True
        assert reason == ""

    def test_short_question(self):
        ok, reason = check_not_empty("What?", "A valid answer here.")
        assert ok is False
        assert "too short" in reason

    def test_short_answer(self):
        ok, reason = check_not_empty("This is a perfectly valid question text.", "ok")
        assert ok is False
        assert "too short" in reason

    def test_vague_question(self):
        ok, reason = check_not_empty(
            "Tell me something about anything in tech.",
            "Key points include x, y, z."
        )
        assert ok is False
        assert "vague" in reason


# ════════════════════════════════════════════════════════════════════════════
# check_semantic_similarity
# ════════════════════════════════════════════════════════════════════════════


class TestSemanticSimilarity:

    def test_no_history_always_acceptable(self):
        ok, score = check_semantic_similarity("What is X?", [], None, 0.85)
        assert ok is True
        assert score == 0.0

    def test_no_embedding_skips_check(self):
        ok, score = check_semantic_similarity(
            "What is X?",
            [[0.1, 0.2, 0.3]],
            None,  # embedding provider unavailable
            0.85,
        )
        assert ok is True
        assert score == 0.0

    def test_identical_embedding_rejected(self):
        emb = [1.0, 0.0, 0.0]
        ok, score = check_semantic_similarity(
            "same question",
            [emb],
            emb,
            0.85,
        )
        assert ok is False
        assert score >= 0.99

    def test_orthogonal_embedding_accepted(self):
        ok, score = check_semantic_similarity(
            "different question",
            [[1.0, 0.0, 0.0]],
            [0.0, 1.0, 0.0],
            0.85,
        )
        assert ok is True
        assert score < 0.01


# ════════════════════════════════════════════════════════════════════════════
# validate_generated_question (combined)
# ════════════════════════════════════════════════════════════════════════════


class TestCombinedValidation:

    @staticmethod
    def _make_output(**overrides) -> GeneratedQuestionOutput:
        defaults = dict(
            question_text="Explain how garbage collection works in Java.",
            expected_answer="Mark-and-sweep, generational GC, root set traversal.",
            difficulty="medium",
            topic="algorithms",
        )
        defaults.update(overrides)
        return GeneratedQuestionOutput(**defaults)

    def test_all_checks_pass(self):
        output = self._make_output()
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[],
        )
        assert result.passed is True
        assert result.failures == []

    def test_difficulty_mismatch_fails(self):
        output = self._make_output(difficulty="hard")
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[],
        )
        assert result.passed is False
        assert result.difficulty_match is False
        assert any("difficulty_mismatch" in f for f in result.failures)

    def test_topic_not_allowed_fails(self):
        output = self._make_output(topic="cooking")
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[],
        )
        assert result.passed is False
        assert result.topic_allowed is False

    def test_empty_question_fails(self):
        output = self._make_output(question_text="Hi", expected_answer="x")
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[],
        )
        assert result.passed is False
        assert result.not_empty is False

    def test_multiple_failures_aggregated(self):
        output = self._make_output(
            question_text="Hi",
            difficulty="hard",
            topic="cooking",
        )
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[],
        )
        assert result.passed is False
        assert len(result.failures) >= 3

    def test_similarity_rejection(self):
        emb = [1.0, 0.0, 0.0]
        output = self._make_output()
        result = validate_generated_question(
            output=output,
            requested_difficulty="medium",
            allowed_topics=["algorithms"],
            previous_question_embeddings=[emb],
            new_embedding=emb,
            similarity_threshold=0.85,
        )
        assert result.passed is False
        assert any("too_similar" in f for f in result.failures)
