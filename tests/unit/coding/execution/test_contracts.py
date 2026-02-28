"""
Unit tests for coding.execution.contracts — Command & result DTOs
"""

import pytest
from app.coding.enums import ExecutionStatus
from app.coding.enums import TestCaseStatus as _TestCaseStatus
from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    ExecutionResult,
    SubmissionData,
)
from app.coding.execution.contracts import TestCase as _TestCase
from app.coding.execution.contracts import TestCaseExecutionResult as _TestCaseExecutionResult


class TestSubmissionData:
    """Verify SubmissionData frozen dataclass."""

    def test_create(self):
        sd = SubmissionData(language="python3", source_code="print(1)", coding_problem_id=42)
        assert sd.language == "python3"
        assert sd.source_code == "print(1)"
        assert sd.coding_problem_id == 42

    def test_immutable(self):
        sd = SubmissionData(language="cpp", source_code="int main(){}", coding_problem_id=1)
        with pytest.raises(AttributeError):
            sd.language = "java"  # type: ignore[misc]


class TestTestCaseContract:
    """Verify TestCase frozen dataclass."""

    def test_create(self):
        tc = _TestCase(
            test_case_id=1,
            input_data="5\n",
            expected_output="25\n",
            weight=2.0,
            time_limit_ms=2000,
            memory_limit_kb=262144,
            is_hidden=False,
        )
        assert tc.test_case_id == 1
        assert tc.weight == 2.0
        assert tc.is_hidden is False

    def test_immutable(self):
        tc = _TestCase(
            test_case_id=1,
            input_data="",
            expected_output="",
            weight=1.0,
            time_limit_ms=1000,
            memory_limit_kb=128000,
            is_hidden=True,
        )
        with pytest.raises(AttributeError):
            tc.weight = 5.0  # type: ignore[misc]


class TestExecuteSubmissionCommand:
    """Verify ExecuteSubmissionCommand frozen dataclass."""

    def test_create(self):
        sd = SubmissionData(language="java", source_code="class S{}", coding_problem_id=10)
        tc = _TestCase(
            test_case_id=1,
            input_data="",
            expected_output="Hello\n",
            weight=1.0,
            time_limit_ms=2000,
            memory_limit_kb=262144,
            is_hidden=False,
        )
        cmd = ExecuteSubmissionCommand(submission_id=99, submission_data=sd, test_cases=[tc])
        assert cmd.submission_id == 99
        assert len(cmd.test_cases) == 1

    def test_immutable(self):
        sd = SubmissionData(language="python3", source_code="x=1", coding_problem_id=1)
        cmd = ExecuteSubmissionCommand(submission_id=1, submission_data=sd, test_cases=[])
        with pytest.raises(AttributeError):
            cmd.submission_id = 2  # type: ignore[misc]


class TestTCExecutionResult:
    """Verify TestCaseExecutionResult frozen dataclass."""

    def test_passed_result(self):
        r = _TestCaseExecutionResult(
            test_case_id=1,
            status=_TestCaseStatus.PASSED,
            passed=True,
            actual_output="42\n",
            runtime_ms=150,
            memory_kb=8192,
            exit_code=0,
            stderr="",
            feedback="Passed",
        )
        assert r.passed is True
        assert r.status == _TestCaseStatus.PASSED

    def test_failed_result(self):
        r = _TestCaseExecutionResult(
            test_case_id=2,
            status=_TestCaseStatus.FAILED,
            passed=False,
            actual_output="43\n",
            runtime_ms=100,
            memory_kb=4096,
            exit_code=0,
            stderr="",
            feedback="Wrong Answer",
        )
        assert r.passed is False
        assert r.feedback == "Wrong Answer"

    def test_timeout_result(self):
        r = _TestCaseExecutionResult(
            test_case_id=3,
            status=_TestCaseStatus.TIMEOUT,
            passed=False,
            actual_output="",
            runtime_ms=2000,
            memory_kb=0,
            exit_code=124,
            stderr="",
            feedback="Time Limit Exceeded",
        )
        assert r.exit_code == 124


class TestExecutionResult:
    """Verify ExecutionResult frozen dataclass."""

    def test_all_passed(self):
        r = ExecutionResult(
            submission_id=1,
            execution_status=ExecutionStatus.PASSED,
            score=100.0,
            total_execution_time_ms=300,
            peak_memory_kb=8192,
            compiler_output=None,
            test_results=[],
        )
        assert r.score == 100.0
        assert r.execution_status == ExecutionStatus.PASSED

    def test_partial_score(self):
        r = ExecutionResult(
            submission_id=2,
            execution_status=ExecutionStatus.FAILED,
            score=66.67,
            total_execution_time_ms=500,
            peak_memory_kb=16384,
            compiler_output=None,
            test_results=[],
        )
        assert r.score == 66.67

    def test_error_with_compiler_output(self):
        r = ExecutionResult(
            submission_id=3,
            execution_status=ExecutionStatus.ERROR,
            score=0.0,
            total_execution_time_ms=0,
            peak_memory_kb=0,
            compiler_output="error: expected ';'",
            test_results=[],
        )
        assert r.compiler_output is not None
