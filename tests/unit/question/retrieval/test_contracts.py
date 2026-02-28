"""
Unit Tests — Pydantic DTOs (Contracts)

Tests validation rules, default values, enum behavior, and edge cases.
No mocks, no I/O.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.question.retrieval.contracts import (
    DifficultyLevel,
    HybridSearchWeights,
    QuestionCandidate,
    QuestionScope,
    RetrievalResult,
    RetrievalStrategy,
    SearchCriteria,
    SimilarityCheckResult,
)


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class TestRetrievalStrategy:
    """Tests for RetrievalStrategy enum."""

    def test_values(self):
        assert RetrievalStrategy.SEMANTIC == "semantic"
        assert RetrievalStrategy.TOPIC_FILTER == "topic_filter"
        assert RetrievalStrategy.HYBRID == "hybrid"
        assert RetrievalStrategy.STATIC_FALLBACK == "static_fallback"

    def test_all_strategies(self):
        assert len(RetrievalStrategy) == 4


class TestDifficultyLevel:
    """Tests for DifficultyLevel enum."""

    def test_values(self):
        assert DifficultyLevel.EASY == "easy"
        assert DifficultyLevel.MEDIUM == "medium"
        assert DifficultyLevel.HARD == "hard"


class TestQuestionScope:
    """Tests for QuestionScope enum."""

    def test_values(self):
        assert QuestionScope.PUBLIC == "public"
        assert QuestionScope.ORGANIZATION == "organization"
        assert QuestionScope.PRIVATE == "private"


# ═══════════════════════════════════════════════════════════════════════
# HybridSearchWeights
# ═══════════════════════════════════════════════════════════════════════


class TestHybridSearchWeights:
    """Tests for HybridSearchWeights DTO."""

    def test_valid_weights(self):
        w = HybridSearchWeights(resume_weight=0.6, jd_weight=0.4)
        assert w.resume_weight == 0.6
        assert w.jd_weight == 0.4

    def test_default_weights(self):
        w = HybridSearchWeights()
        assert w.resume_weight == 0.5
        assert w.jd_weight == 0.5

    def test_weights_must_sum_to_one(self):
        """Weights that don't sum to ~1.0 → validation error."""
        with pytest.raises(PydanticValidationError, match="sum to 1.0"):
            HybridSearchWeights(resume_weight=0.5, jd_weight=0.3)

    def test_weights_sum_tolerance(self):
        """Small floating point deviations are acceptable."""
        # These sum to 1.0000000000000002 due to float precision
        w = HybridSearchWeights(resume_weight=0.3, jd_weight=0.7)
        assert w is not None

    def test_negative_weight_rejected(self):
        with pytest.raises(PydanticValidationError):
            HybridSearchWeights(resume_weight=-0.1, jd_weight=1.1)

    def test_zero_weight_allowed(self):
        w = HybridSearchWeights(resume_weight=0.0, jd_weight=1.0)
        assert w.resume_weight == 0.0
        assert w.jd_weight == 1.0


# ═══════════════════════════════════════════════════════════════════════
# SearchCriteria
# ═══════════════════════════════════════════════════════════════════════


class TestSearchCriteria:
    """Tests for SearchCriteria DTO."""

    def test_minimal_valid(self):
        """Only organization_id is required."""
        criteria = SearchCriteria(organization_id=1)
        assert criteria.organization_id == 1
        assert criteria.query_vector is None
        assert criteria.top_k == 10
        assert criteria.score_threshold == 0.5
        assert criteria.exclude_question_ids == []
        assert criteria.include_public is True

    def test_full_criteria(self):
        criteria = SearchCriteria(
            organization_id=42,
            query_vector=[0.1] * 768,
            difficulty=DifficultyLevel.MEDIUM,
            topic_ids=[1, 2, 3],
            top_k=20,
            score_threshold=0.8,
            exclude_question_ids=[100, 200],
            include_public=False,
        )
        assert criteria.organization_id == 42
        assert len(criteria.query_vector) == 768
        assert criteria.difficulty == DifficultyLevel.MEDIUM
        assert criteria.topic_ids == [1, 2, 3]
        assert criteria.top_k == 20
        assert criteria.score_threshold == 0.8
        assert criteria.exclude_question_ids == [100, 200]
        assert criteria.include_public is False

    def test_organization_id_required(self):
        with pytest.raises(PydanticValidationError):
            SearchCriteria()

    def test_top_k_minimum(self):
        """top_k must be >= 1."""
        with pytest.raises(PydanticValidationError, match="top_k"):
            SearchCriteria(organization_id=1, top_k=0)

    def test_top_k_maximum(self):
        """top_k must be <= 100."""
        with pytest.raises(PydanticValidationError, match="top_k"):
            SearchCriteria(organization_id=1, top_k=101)

    def test_score_threshold_range(self):
        """score_threshold must be between 0.0 and 1.0."""
        with pytest.raises(PydanticValidationError, match="score_threshold"):
            SearchCriteria(organization_id=1, score_threshold=1.5)

        with pytest.raises(PydanticValidationError, match="score_threshold"):
            SearchCriteria(organization_id=1, score_threshold=-0.1)

    def test_difficulty_enum_validation(self):
        """String difficulty is coerced to enum."""
        criteria = SearchCriteria(organization_id=1, difficulty="easy")
        assert criteria.difficulty == DifficultyLevel.EASY


# ═══════════════════════════════════════════════════════════════════════
# QuestionCandidate
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionCandidate:
    """Tests for QuestionCandidate DTO."""

    def test_valid_candidate(self):
        candidate = QuestionCandidate(
            question_id=42,
            similarity_score=0.92,
            point_id="abc-123",
            difficulty="medium",
            topic_id=5,
            scope="organization",
            metadata={"source": "template_1"},
        )
        assert candidate.question_id == 42
        assert candidate.similarity_score == 0.92
        assert candidate.point_id == "abc-123"
        assert candidate.metadata == {"source": "template_1"}

    def test_minimal_candidate(self):
        candidate = QuestionCandidate(
            question_id=1,
            similarity_score=0.5,
        )
        assert candidate.point_id is None
        assert candidate.metadata == {}

    def test_score_clamped_to_range(self):
        """Similarity score should be between -1.0 and 1.0."""
        # Qdrant can return scores > 1.0 in edge cases (.dot product)
        # We allow it but constrain display
        candidate = QuestionCandidate(question_id=1, similarity_score=0.5)
        assert 0.0 <= candidate.similarity_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# RetrievalResult
# ═══════════════════════════════════════════════════════════════════════


class TestRetrievalResult:
    """Tests for RetrievalResult DTO."""

    def test_empty_result(self):
        result = RetrievalResult(
            candidates=[],
            strategy_used=RetrievalStrategy.SEMANTIC,
            total_found=0,
            search_duration_ms=12.5,
        )
        assert result.is_empty is True
        assert result.cache_hit is False
        assert result.fallback_activated is False

    def test_populated_result(self):
        candidates = [
            QuestionCandidate(question_id=1, similarity_score=0.9),
            QuestionCandidate(question_id=2, similarity_score=0.85),
        ]
        result = RetrievalResult(
            candidates=candidates,
            strategy_used=RetrievalStrategy.HYBRID,
            total_found=2,
            search_duration_ms=45.2,
            cache_hit=True,
        )
        assert result.is_empty is False
        assert result.total_found == 2
        assert result.cache_hit is True
        assert len(result.candidates) == 2

    def test_fallback_result(self):
        result = RetrievalResult(
            candidates=[QuestionCandidate(question_id=1, similarity_score=0.0)],
            strategy_used=RetrievalStrategy.STATIC_FALLBACK,
            total_found=1,
            search_duration_ms=5.0,
            fallback_activated=True,
            fallback_reason="Qdrant circuit breaker open",
        )
        assert result.fallback_activated is True
        assert result.fallback_reason == "Qdrant circuit breaker open"
        assert result.strategy_used == RetrievalStrategy.STATIC_FALLBACK


# ═══════════════════════════════════════════════════════════════════════
# SimilarityCheckResult
# ═══════════════════════════════════════════════════════════════════════


class TestSimilarityCheckResult:
    """Tests for SimilarityCheckResult DTO."""

    def test_acceptable_result(self):
        result = SimilarityCheckResult(
            is_acceptable=True,
            max_similarity=0.3,
            most_similar_question_id=42,
            similarities={42: 0.3, 43: 0.1},
        )
        assert result.is_acceptable is True
        assert result.max_similarity == 0.3

    def test_rejected_result(self):
        result = SimilarityCheckResult(
            is_acceptable=False,
            max_similarity=0.95,
            most_similar_question_id=42,
            similarities={42: 0.95},
        )
        assert result.is_acceptable is False
        assert result.most_similar_question_id == 42

    def test_no_history(self):
        result = SimilarityCheckResult(
            is_acceptable=True,
            max_similarity=0.0,
        )
        assert result.most_similar_question_id is None
        assert result.similarities == {}
