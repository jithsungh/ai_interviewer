"""
Unit Tests — Aggregation Errors

Tests exception classes, error hierarchy, metadata, and HTTP status codes.
"""

from __future__ import annotations

import pytest

from app.evaluation.aggregation.errors import (
    AggregationAlreadyExistsError,
    AggregationError,
    IncompleteEvaluationError,
    InterviewNotFoundError,
    NoExchangesError,
    SummaryGenerationError,
    TemplateWeightsNotFoundError,
)
from app.shared.errors import BaseError


# ═══════════════════════════════════════════════════════════════════════════
# Base Error Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAggregationError:
    def test_inherits_base_error(self):
        error = AggregationError(message="Test")
        assert isinstance(error, BaseError)
        assert isinstance(error, Exception)

    def test_default_error_code(self):
        error = AggregationError(message="Something failed")
        assert error.error_code == "AGGREGATION_ERROR"
        assert error.http_status_code == 500

    def test_custom_error_code(self):
        error = AggregationError(
            message="Custom",
            error_code="CUSTOM_CODE",
            http_status_code=400,
        )
        assert error.error_code == "CUSTOM_CODE"
        assert error.http_status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# IncompleteEvaluationError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestIncompleteEvaluationError:
    def test_with_pending_ids(self):
        error = IncompleteEvaluationError(
            pending_exchange_ids=[10, 20, 30],
            submission_id=1,
        )
        assert error.pending_exchange_ids == [10, 20, 30]
        assert error.submission_id == 1
        assert error.error_code == "INCOMPLETE_EVALUATION"
        assert error.http_status_code == 422
        assert "3 exchange(s)" in str(error)
        assert "[10, 20, 30]" in str(error)

    def test_metadata(self):
        error = IncompleteEvaluationError(
            pending_exchange_ids=[5],
            submission_id=99,
        )
        assert error.metadata["pending_count"] == 1
        assert error.metadata["pending_exchange_ids"] == [5]
        assert error.metadata["submission_id"] == 99

    def test_single_pending(self):
        error = IncompleteEvaluationError(pending_exchange_ids=[42])
        assert "1 exchange(s)" in str(error)


# ═══════════════════════════════════════════════════════════════════════════
# InterviewNotFoundError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewNotFoundError:
    def test_with_submission_id(self):
        error = InterviewNotFoundError(submission_id=123)
        assert error.submission_id == 123
        assert error.error_code == "INTERVIEW_NOT_FOUND"
        assert error.http_status_code == 404
        assert "123" in str(error)

    def test_metadata(self):
        error = InterviewNotFoundError(submission_id=456)
        assert error.metadata["submission_id"] == 456


# ═══════════════════════════════════════════════════════════════════════════
# AggregationAlreadyExistsError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAggregationAlreadyExistsError:
    def test_with_ids(self):
        error = AggregationAlreadyExistsError(
            submission_id=1,
            existing_result_id=42,
        )
        assert error.submission_id == 1
        assert error.existing_result_id == 42
        assert error.error_code == "AGGREGATION_EXISTS"
        assert error.http_status_code == 409
        assert "force_reaggregate=true" in str(error)

    def test_metadata(self):
        error = AggregationAlreadyExistsError(
            submission_id=5,
            existing_result_id=10,
        )
        assert error.metadata["submission_id"] == 5
        assert error.metadata["existing_result_id"] == 10


# ═══════════════════════════════════════════════════════════════════════════
# TemplateWeightsNotFoundError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateWeightsNotFoundError:
    def test_with_template_id(self):
        error = TemplateWeightsNotFoundError(template_id=7)
        assert error.template_id == 7
        assert error.error_code == "TEMPLATE_WEIGHTS_NOT_FOUND"
        assert error.http_status_code == 422

    def test_custom_reason(self):
        error = TemplateWeightsNotFoundError(
            template_id=7,
            reason="Template structure is empty",
        )
        assert "Template structure is empty" in str(error)


# ═══════════════════════════════════════════════════════════════════════════
# SummaryGenerationError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryGenerationError:
    def test_basic(self):
        error = SummaryGenerationError(message="Timeout after 30s")
        assert error.error_code == "SUMMARY_GENERATION_FAILED"
        assert error.http_status_code == 502
        assert "Timeout after 30s" in str(error)

    def test_with_provider(self):
        error = SummaryGenerationError(
            message="Rate limited",
            provider="groq",
        )
        assert error.provider == "groq"
        assert error.metadata["provider"] == "groq"


# ═══════════════════════════════════════════════════════════════════════════
# NoExchangesError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestNoExchangesError:
    def test_with_submission_id(self):
        error = NoExchangesError(submission_id=99)
        assert error.error_code == "NO_EXCHANGES"
        assert error.http_status_code == 422
        assert "99" in str(error)
