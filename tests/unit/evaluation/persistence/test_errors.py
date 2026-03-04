"""
Unit Tests — Evaluation Persistence Errors

Tests persistence-specific error classes for the evaluation module.
"""

from __future__ import annotations

import pytest

from app.evaluation.persistence.errors import (
    DuplicateEvaluationError,
    DuplicateResultError,
    EvaluationNotFoundError,
    InterviewResultNotFoundError,
    PersistenceError,
)


# ═══════════════════════════════════════════════════════════════════════════
# PersistenceError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPersistenceError:
    def test_is_exception(self):
        """PersistenceError should be an Exception."""
        error = PersistenceError()
        assert isinstance(error, Exception)

    def test_default_message(self):
        """Default message should be descriptive."""
        error = PersistenceError()
        assert "persistence" in error.message.lower()

    def test_custom_message(self):
        """Custom message should be stored."""
        error = PersistenceError(message="Custom error")
        assert error.message == "Custom error"

    def test_default_error_code(self):
        """Default error code should be EVAL_PERSISTENCE_ERROR."""
        error = PersistenceError()
        assert error.error_code == "EVAL_PERSISTENCE_ERROR"

    def test_custom_error_code(self):
        """Custom error code should be stored."""
        error = PersistenceError(error_code="CUSTOM_CODE")
        assert error.error_code == "CUSTOM_CODE"

    def test_http_status_500(self):
        """HTTP status should be 500."""
        error = PersistenceError()
        assert error.http_status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationNotFoundError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationNotFoundError:
    def test_stores_evaluation_id(self):
        """Error should store the evaluation ID."""
        error = EvaluationNotFoundError(evaluation_id=42)
        assert error.evaluation_id == 42

    def test_message_includes_id(self):
        """Error message should include evaluation ID."""
        error = EvaluationNotFoundError(evaluation_id=99)
        assert "99" in error.message

    def test_http_status_404(self):
        """HTTP status should be 404."""
        error = EvaluationNotFoundError(evaluation_id=1)
        assert error.http_status_code == 404

    def test_error_code(self):
        """Error code should be EVALUATION_NOT_FOUND."""
        error = EvaluationNotFoundError(evaluation_id=1)
        assert error.error_code == "EVALUATION_NOT_FOUND"

    def test_metadata_includes_evaluation_id(self):
        """Metadata should include evaluation_id."""
        error = EvaluationNotFoundError(evaluation_id=123)
        assert error.metadata.get("evaluation_id") == 123


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultNotFoundError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultNotFoundError:
    def test_with_result_id(self):
        """Error should store result_id."""
        error = InterviewResultNotFoundError(result_id=5)
        assert error.result_id == 5
        assert "5" in error.message

    def test_with_submission_id(self):
        """Error should store submission_id."""
        error = InterviewResultNotFoundError(submission_id=10)
        assert error.submission_id == 10
        assert "10" in error.message

    def test_http_status_404(self):
        """HTTP status should be 404."""
        error = InterviewResultNotFoundError(result_id=1)
        assert error.http_status_code == 404

    def test_error_code(self):
        """Error code should be RESULT_NOT_FOUND."""
        error = InterviewResultNotFoundError(result_id=1)
        assert error.error_code == "RESULT_NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# DuplicateEvaluationError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicateEvaluationError:
    def test_stores_exchange_id(self):
        """Error should store the exchange ID."""
        error = DuplicateEvaluationError(interview_exchange_id=77)
        assert error.interview_exchange_id == 77

    def test_message_includes_exchange_id(self):
        """Error message should include exchange ID."""
        error = DuplicateEvaluationError(interview_exchange_id=77)
        assert "77" in error.message

    def test_http_status_409(self):
        """HTTP status should be 409."""
        error = DuplicateEvaluationError(interview_exchange_id=1)
        assert error.http_status_code == 409

    def test_error_code(self):
        """Error code should be DUPLICATE_EVALUATION."""
        error = DuplicateEvaluationError(interview_exchange_id=1)
        assert error.error_code == "DUPLICATE_EVALUATION"

    def test_with_existing_evaluation_id(self):
        """Optional existing_evaluation_id should be stored in metadata."""
        error = DuplicateEvaluationError(
            interview_exchange_id=1, existing_evaluation_id=50
        )
        assert error.existing_evaluation_id == 50
        assert error.metadata.get("existing_evaluation_id") == 50


# ═══════════════════════════════════════════════════════════════════════════
# DuplicateResultError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicateResultError:
    def test_stores_submission_id(self):
        """Error should store the submission ID."""
        error = DuplicateResultError(submission_id=88)
        assert error.submission_id == 88

    def test_message_includes_submission_id(self):
        """Error message should include submission ID."""
        error = DuplicateResultError(submission_id=88)
        assert "88" in error.message

    def test_http_status_409(self):
        """HTTP status should be 409."""
        error = DuplicateResultError(submission_id=1)
        assert error.http_status_code == 409

    def test_error_code(self):
        """Error code should be DUPLICATE_RESULT."""
        error = DuplicateResultError(submission_id=1)
        assert error.error_code == "DUPLICATE_RESULT"

    def test_with_existing_result_id(self):
        """Optional existing_result_id should be stored in metadata."""
        error = DuplicateResultError(submission_id=1, existing_result_id=20)
        assert error.existing_result_id == 20
        assert error.metadata.get("existing_result_id") == 20
