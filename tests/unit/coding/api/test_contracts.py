"""
Unit Tests — Coding API Contracts (Pydantic Models)

Validates request/response model validation, serialization,
and edge cases for all coding API contracts.
"""

import pytest
from datetime import datetime, timezone

from app.coding.api.contracts import (
    CodeSubmissionError,
    ExecutionStatusResponse,
    SubmissionSummary,
    SubmitCodeRequest,
    SubmitCodeResponse,
    TestCaseResultDTO as _TestCaseResultDTO,
)


# ==========================================================================
# SubmitCodeRequest
# ==========================================================================


class TestSubmitCodeRequest:
    """Tests for SubmitCodeRequest validation."""

    def test_valid_request(self):
        """Accept a well-formed submission request."""
        req = SubmitCodeRequest(
            interview_exchange_id=1,
            coding_problem_id=2,
            language="python3",
            source_code="print('hello')",
        )
        assert req.interview_exchange_id == 1
        assert req.coding_problem_id == 2
        assert req.language == "python3"
        assert req.source_code == "print('hello')"

    def test_valid_languages(self):
        """Accept all supported languages."""
        for lang in ("cpp", "java", "python3"):
            req = SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=1,
                language=lang,
                source_code="code",
            )
            assert req.language == lang

    def test_invalid_language_rejected(self):
        """Reject unsupported languages."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=1,
                language="ruby",
                source_code="code",
            )

    def test_zero_exchange_id_rejected(self):
        """Reject exchange_id <= 0."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=0,
                coding_problem_id=1,
                language="python3",
                source_code="code",
            )

    def test_negative_exchange_id_rejected(self):
        """Reject negative exchange_id."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=-1,
                coding_problem_id=1,
                language="python3",
                source_code="code",
            )

    def test_zero_problem_id_rejected(self):
        """Reject coding_problem_id <= 0."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=0,
                language="python3",
                source_code="code",
            )

    def test_empty_source_code_rejected(self):
        """Reject empty source code."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=1,
                language="python3",
                source_code="",
            )

    def test_whitespace_only_source_code_rejected(self):
        """Reject whitespace-only source code (stripped to empty)."""
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=1,
                language="python3",
                source_code="   \n\t  ",
            )

    def test_source_code_trimmed(self):
        """Source code is trimmed of leading/trailing whitespace."""
        req = SubmitCodeRequest(
            interview_exchange_id=1,
            coding_problem_id=1,
            language="python3",
            source_code="  print('hello')  ",
        )
        assert req.source_code == "print('hello')"

    def test_max_length_source_code(self):
        """Accept source code at exactly 50000 chars."""
        code = "x" * 50000
        req = SubmitCodeRequest(
            interview_exchange_id=1,
            coding_problem_id=1,
            language="python3",
            source_code=code,
        )
        assert len(req.source_code) == 50000

    def test_over_max_length_rejected(self):
        """Reject source code exceeding 50000 chars."""
        code = "x" * 50001
        with pytest.raises(Exception):
            SubmitCodeRequest(
                interview_exchange_id=1,
                coding_problem_id=1,
                language="python3",
                source_code=code,
            )

    def test_json_serialization(self):
        """Verify JSON round-trip serialization."""
        req = SubmitCodeRequest(
            interview_exchange_id=42,
            coding_problem_id=7,
            language="cpp",
            source_code="#include <iostream>",
        )
        data = req.model_dump()
        assert data["interview_exchange_id"] == 42
        assert data["language"] == "cpp"

        # Round-trip
        req2 = SubmitCodeRequest(**data)
        assert req2 == req


# ==========================================================================
# SubmitCodeResponse
# ==========================================================================


class TestSubmitCodeResponse:
    """Tests for SubmitCodeResponse model."""

    def test_default_values(self):
        """Verify default field values."""
        resp = SubmitCodeResponse(submission_id=1)
        assert resp.execution_status == "pending"
        assert resp.message == "Code submitted successfully. Execution in progress."

    def test_custom_message(self):
        """Accept custom message."""
        resp = SubmitCodeResponse(
            submission_id=1,
            execution_status="running",
            message="Custom",
        )
        assert resp.execution_status == "running"
        assert resp.message == "Custom"


# ==========================================================================
# TestCaseResultDTO
# ==========================================================================


class TestTestCaseResultDTO:
    """Tests for TestCaseResultDTO model."""

    def test_visible_test_case(self):
        """Visible test case includes all fields."""
        dto = _TestCaseResultDTO(
            test_case_id=1,
            test_case_name="Test 1",
            passed=True,
            visible=True,
            actual_output="hello",
            expected_output="hello",
            runtime_ms=45,
            memory_kb=1024,
            feedback="Passed",
        )
        assert dto.visible is True
        assert dto.actual_output == "hello"
        assert dto.expected_output == "hello"

    def test_hidden_test_case(self):
        """Hidden test case has None for outputs."""
        dto = _TestCaseResultDTO(
            test_case_id=2,
            test_case_name="Hidden Test",
            passed=True,
            visible=False,
            actual_output=None,
            expected_output=None,
            runtime_ms=50,
            memory_kb=512,
            feedback="Passed",
        )
        assert dto.visible is False
        assert dto.actual_output is None
        assert dto.expected_output is None


# ==========================================================================
# ExecutionStatusResponse
# ==========================================================================


class TestExecutionStatusResponse:
    """Tests for ExecutionStatusResponse model."""

    def test_pending_response(self):
        """Pending submission has empty test results and zero score."""
        now = datetime.now(timezone.utc)
        resp = ExecutionStatusResponse(
            submission_id=1,
            interview_exchange_id=10,
            coding_problem_id=5,
            language="python3",
            execution_status="pending",
            score=0.0,
            test_results=[],
            submitted_at=now,
        )
        assert resp.execution_status == "pending"
        assert resp.score == 0.0
        assert resp.test_results == []
        assert resp.executed_at is None

    def test_completed_response_with_results(self):
        """Completed submission includes test results."""
        now = datetime.now(timezone.utc)
        resp = ExecutionStatusResponse(
            submission_id=1,
            interview_exchange_id=10,
            coding_problem_id=5,
            language="cpp",
            execution_status="passed",
            score=100.0,
            execution_time_ms=200,
            memory_kb=8000,
            test_results=[
                _TestCaseResultDTO(
                    test_case_id=1,
                    test_case_name="Test 1",
                    passed=True,
                    visible=True,
                    actual_output="42",
                    expected_output="42",
                    runtime_ms=100,
                    memory_kb=8000,
                    feedback="Passed",
                ),
            ],
            submitted_at=now,
            executed_at=now,
        )
        assert resp.execution_status == "passed"
        assert len(resp.test_results) == 1

    def test_all_execution_statuses(self):
        """All valid execution status values are accepted."""
        now = datetime.now(timezone.utc)
        for status in (
            "pending", "running", "passed", "failed",
            "error", "timeout", "memory_exceeded",
        ):
            resp = ExecutionStatusResponse(
                submission_id=1,
                interview_exchange_id=1,
                coding_problem_id=1,
                language="python3",
                execution_status=status,
                score=0.0,
                test_results=[],
                submitted_at=now,
            )
            assert resp.execution_status == status


# ==========================================================================
# SubmissionSummary
# ==========================================================================


class TestSubmissionSummary:
    """Tests for SubmissionSummary model."""

    def test_summary_fields(self):
        """Verify all summary fields are present."""
        now = datetime.now(timezone.utc)
        summary = SubmissionSummary(
            submission_id=1,
            interview_exchange_id=10,
            coding_problem_id=5,
            language="java",
            execution_status="passed",
            score=85.5,
            submitted_at=now,
        )
        assert summary.submission_id == 1
        assert summary.language == "java"
        assert summary.score == 85.5


# ==========================================================================
# CodeSubmissionError
# ==========================================================================


class TestCodeSubmissionError:
    """Tests for CodeSubmissionError model."""

    def test_error_with_details(self):
        """Error response includes details."""
        err = CodeSubmissionError(
            error="DUPLICATE_SUBMISSION",
            message="Already submitted",
            details={"existing_submission_id": 42},
        )
        assert err.error == "DUPLICATE_SUBMISSION"
        assert err.details["existing_submission_id"] == 42

    def test_error_without_details(self):
        """Error response works without optional fields."""
        err = CodeSubmissionError(
            error="NOT_FOUND",
            message="Not found",
        )
        assert err.details is None
        assert err.request_id is None
