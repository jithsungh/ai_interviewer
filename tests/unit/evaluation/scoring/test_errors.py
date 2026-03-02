"""
Unit Tests — Scoring Errors

Tests exception classes and error metadata.
"""

from __future__ import annotations

import pytest

from app.evaluation.scoring.errors import (
    AIEvaluationError,
    EvaluationExistsError,
    ExchangeNotFoundError,
    InvalidRubricError,
    InvalidScoreError,
    MissingDimensionError,
    RubricNotFoundError,
    ScoreValidationError,
    ScoringError,
)


# ═══════════════════════════════════════════════════════════════════════════
# Base Error Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoringError:
    def test_base_error_instance(self):
        """ScoringError should be an Exception."""
        error = ScoringError(message="Test error")
        
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_error_code(self):
        """ScoringError should have error code."""
        error = ScoringError(message="Test")
        
        assert hasattr(error, "error_code")


# ═══════════════════════════════════════════════════════════════════════════
# Exchange Not Found Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeNotFoundError:
    def test_error_with_exchange_id(self):
        """ExchangeNotFoundError should include exchange ID."""
        error = ExchangeNotFoundError(exchange_id=123)
        
        assert error.exchange_id == 123
        assert "123" in str(error)

    def test_error_metadata(self):
        """Error should have metadata with exchange_id."""
        error = ExchangeNotFoundError(exchange_id=456)
        
        assert error.metadata.get("exchange_id") == 456


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Not Found Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRubricNotFoundError:
    def test_error_with_template_id(self):
        """RubricNotFoundError should include template ID."""
        error = RubricNotFoundError(template_id=5)
        
        assert error.template_id == 5
        assert "5" in str(error)

    def test_error_metadata(self):
        """Error metadata should include template_id."""
        error = RubricNotFoundError(template_id=100)
        
        assert error.metadata.get("template_id") == 100


# ═══════════════════════════════════════════════════════════════════════════
# Invalid Rubric Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInvalidRubricError:
    def test_error_with_rubric_id_and_reason(self):
        """InvalidRubricError should include rubric ID and reason."""
        error = InvalidRubricError(rubric_id=10, reason="No dimensions defined")
        
        assert error.rubric_id == 10
        assert error.reason == "No dimensions defined"
        assert "10" in str(error)
        assert "No dimensions" in str(error)


# ═══════════════════════════════════════════════════════════════════════════
# AI Evaluation Error Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAIEvaluationError:
    def test_error_with_details(self):
        """AIEvaluationError should include failure details."""
        error = AIEvaluationError(
            message="Timeout after 30s",
            provider="groq",
            retries_attempted=3,
        )
        
        assert "Timeout after 30s" in str(error)
        assert error.provider == "groq"
        assert error.retries_attempted == 3

    def test_error_metadata(self):
        """Error should have metadata."""
        error = AIEvaluationError(
            message="Invalid JSON response",
            provider="openai",
            retries_attempted=1,
        )
        
        assert error.metadata.get("provider") == "openai"
        assert error.metadata.get("retries_attempted") == 1


# ═══════════════════════════════════════════════════════════════════════════
# Invalid Score Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInvalidScoreError:
    def test_error_with_score_details(self):
        """InvalidScoreError should include score details."""
        error = InvalidScoreError(
            dimension_name="Accuracy",
            score=6.0,
            max_score=5.0,
        )
        
        assert error.dimension_name == "Accuracy"
        assert error.score == 6.0
        assert error.max_score == 5.0

    def test_error_message_format(self):
        """Error message should be descriptive."""
        error = InvalidScoreError(
            dimension_name="Communication",
            score=10.0,
            max_score=5.0,
        )
        
        message = str(error)
        assert "Communication" in message
        assert "10.0" in message
        assert "5.0" in message


# ═══════════════════════════════════════════════════════════════════════════
# Missing Dimension Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMissingDimensionError:
    def test_error_with_missing_list(self):
        """MissingDimensionError should include missing dimensions."""
        error = MissingDimensionError(
            missing_dimensions=["Accuracy", "Communication"]
        )
        
        assert error.missing_dimensions == ["Accuracy", "Communication"]
        assert "Accuracy" in str(error)
        assert "Communication" in str(error)

    def test_single_missing_dimension(self):
        """Single missing dimension should work."""
        error = MissingDimensionError(missing_dimensions=["Accuracy"])
        
        assert len(error.missing_dimensions) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Score Validation Error Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreValidationError:
    def test_error_with_message(self):
        """ScoreValidationError should accept custom message."""
        error = ScoreValidationError(message="Duplicate dimension scores")
        
        assert "Duplicate" in str(error)


# ═══════════════════════════════════════════════════════════════════════════
# Evaluation Exists Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationExistsError:
    def test_error_with_ids(self):
        """EvaluationExistsError should include IDs."""
        error = EvaluationExistsError(
            exchange_id=123,
            existing_evaluation_id=456,
        )
        
        assert error.exchange_id == 123
        assert error.existing_evaluation_id == 456

    def test_optional_evaluation_id(self):
        """Existing evaluation ID should be optional."""
        error = EvaluationExistsError(
            exchange_id=123,
            existing_evaluation_id=None,
        )
        
        assert error.existing_evaluation_id is None


# ═══════════════════════════════════════════════════════════════════════════
# Error Hierarchy Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHierarchy:
    def test_all_errors_inherit_from_scoring_error(self):
        """All scoring errors should inherit from ScoringError."""
        errors = [
            ExchangeNotFoundError(exchange_id=1),
            RubricNotFoundError(template_id=1),
            InvalidRubricError(rubric_id=1, reason="No dimensions"),
            AIEvaluationError(message="Test", provider="test", retries_attempted=1),
            InvalidScoreError(dimension_name="Test", score=1.0, max_score=5.0),
            MissingDimensionError(missing_dimensions=["Test"]),
            ScoreValidationError(message="Test"),
            EvaluationExistsError(exchange_id=1, existing_evaluation_id=1),
        ]
        
        for error in errors:
            assert isinstance(error, ScoringError)
            assert isinstance(error, Exception)
