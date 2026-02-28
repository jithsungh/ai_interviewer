"""
Unit tests for coding.execution.service — ExecutionService orchestration

Tests use mock repositories and sandbox to validate business logic
without requiring a database or Docker.
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.coding.enums import ExecutionStatus
from app.coding.enums import TestCaseStatus as _TCStatus
from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    ExecutionResult,
    SubmissionData,
)
from app.coding.execution.contracts import TestCase as _TC
from app.coding.execution.contracts import TestCaseExecutionResult as _TCResult
from app.coding.execution.service import ExecutionService
from app.coding.persistence.entities import CodeExecutionResult, CodeSubmission
from app.coding.sandbox.contracts import SandboxExecutionResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_submission(
    submission_id: int = 1,
    status: str = "pending",
) -> CodeSubmission:
    return CodeSubmission(
        id=submission_id,
        interview_exchange_id=100,
        coding_problem_id=10,
        language="python3",
        source_code="print(int(input())**2)",
        execution_status=status,
    )


def _make_test_case(
    test_case_id: int = 1,
    input_data: str = "5\n",
    expected_output: str = "25\n",
    weight: float = 1.0,
    is_hidden: bool = False,
) -> _TC:
    return _TC(
        test_case_id=test_case_id,
        input_data=input_data,
        expected_output=expected_output,
        weight=weight,
        time_limit_ms=2000,
        memory_limit_kb=262144,
        is_hidden=is_hidden,
    )


def _make_command(
    submission_id: int = 1,
    test_cases: list = None,
) -> ExecuteSubmissionCommand:
    return ExecuteSubmissionCommand(
        submission_id=submission_id,
        submission_data=SubmissionData(
            language="python3",
            source_code="print(int(input())**2)",
            coding_problem_id=10,
        ),
        test_cases=test_cases or [_make_test_case()],
    )


def _make_sandbox_result(
    stdout: str = "25\n",
    stderr: str = "",
    exit_code: int = 0,
    runtime_ms: int = 150,
    memory_kb: int = 8192,
    timed_out: bool = False,
    memory_exceeded: bool = False,
    compilation_output: str = "",
) -> SandboxExecutionResult:
    return SandboxExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        runtime_ms=runtime_ms,
        memory_kb=memory_kb,
        timed_out=timed_out,
        memory_exceeded=memory_exceeded,
        compilation_output=compilation_output,
    )


def _build_service(
    submission: CodeSubmission = None,
    sandbox_result: SandboxExecutionResult = None,
    result_exists: bool = False,
):
    """Build an ExecutionService with mocked dependencies.

    ``get_for_update`` is called twice in the happy path:
    1. In ``execute()`` — expects the initial (pending) submission.
    2. In ``_finalize_submission()`` — expects a *running* submission
       (because the first call already transitioned it).
    The ``side_effect`` list ensures each call gets the right status.
    """
    sub_repo = MagicMock()
    res_repo = MagicMock()
    sandbox = MagicMock()

    initial = submission if submission is not None else _make_submission()
    # After the first update_status the row would be "running" in a real DB.
    running = _make_submission(
        submission_id=initial.id,
        status="running",
    )
    sub_repo.get_for_update.side_effect = [initial, running]

    sub_repo.update_status.return_value = None

    if sandbox_result is not None:
        sandbox.execute.return_value = sandbox_result
    else:
        sandbox.execute.return_value = _make_sandbox_result()

    res_repo.exists.return_value = result_exists
    res_repo.create.return_value = MagicMock()

    service = ExecutionService(
        submission_repo=sub_repo,
        result_repo=res_repo,
        sandbox_executor=sandbox,
    )
    return service, sub_repo, res_repo, sandbox


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecutionServiceHappyPath:
    """Test successful execution scenarios."""

    def test_single_test_passed(self):
        service, sub_repo, res_repo, sandbox = _build_service()
        cmd = _make_command()

        result = service.execute(cmd)

        assert result.execution_status == ExecutionStatus.PASSED
        assert result.score == 100.0
        assert len(result.test_results) == 1
        assert result.test_results[0].passed is True
        assert result.test_results[0].feedback == "Passed"

    def test_multiple_tests_all_passed(self):
        tc1 = _make_test_case(test_case_id=1, input_data="2\n", expected_output="4\n")
        tc2 = _make_test_case(test_case_id=2, input_data="3\n", expected_output="9\n")

        service, sub_repo, res_repo, sandbox = _build_service()
        sandbox.execute.side_effect = [
            _make_sandbox_result(stdout="4\n"),
            _make_sandbox_result(stdout="9\n"),
        ]

        result = service.execute(_make_command(test_cases=[tc1, tc2]))

        assert result.execution_status == ExecutionStatus.PASSED
        assert result.score == 100.0
        assert all(r.passed for r in result.test_results)

    def test_partial_score(self):
        tc1 = _make_test_case(test_case_id=1, weight=1.0, expected_output="4\n")
        tc2 = _make_test_case(test_case_id=2, weight=2.0, expected_output="9\n")
        tc3 = _make_test_case(test_case_id=3, weight=1.0, expected_output="16\n")

        service, sub_repo, res_repo, sandbox = _build_service()
        sandbox.execute.side_effect = [
            _make_sandbox_result(stdout="4\n"),   # pass
            _make_sandbox_result(stdout="9\n"),   # pass
            _make_sandbox_result(stdout="15\n"),  # fail (wrong answer)
        ]

        result = service.execute(_make_command(test_cases=[tc1, tc2, tc3]))

        assert result.execution_status == ExecutionStatus.FAILED
        assert result.score == 75.0  # (1+2)/(1+2+1) * 100
        assert result.test_results[2].passed is False

    def test_status_transitions_called(self):
        """Verify pending → running → terminal transitions."""
        service, sub_repo, res_repo, sandbox = _build_service()

        service.execute(_make_command())

        # First call: pending → running
        first_update = sub_repo.update_status.call_args_list[0]
        assert first_update.args == (1, "running")

        # Second call: running → passed (final)
        second_update = sub_repo.update_status.call_args_list[1]
        assert second_update.args == (1, "passed")

    def test_test_result_persisted(self):
        service, sub_repo, res_repo, sandbox = _build_service()

        service.execute(_make_command())

        res_repo.create.assert_called_once()
        call_kwargs = res_repo.create.call_args
        assert call_kwargs.kwargs.get("passed") or call_kwargs[1].get("passed", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)


class TestExecutionServiceFailures:
    """Test failure classification scenarios."""

    def test_wrong_answer(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            sandbox_result=_make_sandbox_result(stdout="WRONG\n"),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.FAILED
        assert result.score == 0.0
        assert result.test_results[0].status == _TCStatus.FAILED
        assert result.test_results[0].feedback == "Wrong Answer"

    def test_timeout(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            sandbox_result=_make_sandbox_result(
                stdout="", timed_out=True, exit_code=124, runtime_ms=2000
            ),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.TIMEOUT
        assert result.test_results[0].status == _TCStatus.TIMEOUT
        assert result.test_results[0].feedback == "Time Limit Exceeded"

    def test_memory_exceeded(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            sandbox_result=_make_sandbox_result(
                stdout="", memory_exceeded=True, exit_code=137, memory_kb=262144
            ),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.MEMORY_EXCEEDED
        assert result.test_results[0].status == _TCStatus.MEMORY_EXCEEDED
        assert result.test_results[0].feedback == "Memory Limit Exceeded"

    def test_runtime_error(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            sandbox_result=_make_sandbox_result(
                stdout="", stderr="ZeroDivisionError", exit_code=1
            ),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        assert result.test_results[0].status == _TCStatus.RUNTIME_ERROR
        assert result.test_results[0].feedback == "Runtime Error"

    def test_compilation_error(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            sandbox_result=_make_sandbox_result(
                stdout="",
                exit_code=1,
                compilation_output="error: expected ';' at line 5",
            ),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        assert result.test_results[0].feedback == "Compilation Error"

    def test_sandbox_exception(self):
        service, sub_repo, res_repo, sandbox = _build_service()
        sandbox.execute.side_effect = RuntimeError("Docker not available")

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        assert result.test_results[0].status == _TCStatus.RUNTIME_ERROR
        assert result.test_results[0].feedback == "System Error"


class TestExecutionServiceConcurrency:
    """Test concurrent execution prevention."""

    def test_submission_not_found(self):
        service, sub_repo, res_repo, sandbox = _build_service()
        sub_repo.get_for_update.side_effect = None
        sub_repo.get_for_update.return_value = None

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        sandbox.execute.assert_not_called()

    def test_already_terminal(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            submission=_make_submission(status="passed"),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        sandbox.execute.assert_not_called()

    def test_already_running(self):
        service, sub_repo, res_repo, sandbox = _build_service(
            submission=_make_submission(status="running"),
        )

        result = service.execute(_make_command())

        assert result.execution_status == ExecutionStatus.ERROR
        sandbox.execute.assert_not_called()


class TestExecutionServiceIdempotency:
    """Test idempotent re-execution of test cases."""

    def test_skips_already_executed_test_case(self):
        service, sub_repo, res_repo, sandbox = _build_service()
        res_repo.exists.return_value = True
        res_repo.get_by_submission_and_test.return_value = CodeExecutionResult(
            id=1,
            code_submission_id=1,
            test_case_id=1,
            passed=True,
            actual_output="25\n",
            runtime_ms=150,
            memory_kb=8192,
            exit_code=0,
            runtime_output="",
            feedback="Passed",
        )

        result = service.execute(_make_command())

        sandbox.execute.assert_not_called()
        res_repo.create.assert_not_called()
        assert len(result.test_results) == 1
        assert result.test_results[0].passed is True


class TestFinalStatusDetermination:
    """Test _determine_final_status static method."""

    def _make_tc_result(self, status: _TCStatus, passed: bool):
        return _TCResult(
            test_case_id=1,
            status=status,
            passed=passed,
            actual_output="",
            runtime_ms=0,
            memory_kb=0,
            exit_code=0,
            stderr="",
            feedback="",
        )

    def test_all_passed(self):
        results = [self._make_tc_result(_TCStatus.PASSED, True)]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.PASSED

    def test_empty_results_error(self):
        assert ExecutionService._determine_final_status([]) == ExecutionStatus.ERROR

    def test_timeout_priority(self):
        results = [
            self._make_tc_result(_TCStatus.PASSED, True),
            self._make_tc_result(_TCStatus.TIMEOUT, False),
            self._make_tc_result(_TCStatus.FAILED, False),
        ]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.TIMEOUT

    def test_memory_exceeded_priority(self):
        results = [
            self._make_tc_result(_TCStatus.PASSED, True),
            self._make_tc_result(_TCStatus.MEMORY_EXCEEDED, False),
            self._make_tc_result(_TCStatus.FAILED, False),
        ]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.MEMORY_EXCEEDED

    def test_runtime_error_priority(self):
        results = [
            self._make_tc_result(_TCStatus.PASSED, True),
            self._make_tc_result(_TCStatus.RUNTIME_ERROR, False),
        ]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.ERROR

    def test_all_failed_is_failed(self):
        results = [
            self._make_tc_result(_TCStatus.FAILED, False),
            self._make_tc_result(_TCStatus.FAILED, False),
        ]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.FAILED

    def test_timeout_beats_memory_exceeded(self):
        """Timeout has higher priority than memory exceeded."""
        results = [
            self._make_tc_result(_TCStatus.TIMEOUT, False),
            self._make_tc_result(_TCStatus.MEMORY_EXCEEDED, False),
        ]
        assert ExecutionService._determine_final_status(results) == ExecutionStatus.TIMEOUT


class TestClassifyTestCaseResult:
    """Test _classify_test_case_result static method."""

    def test_passed(self):
        sr = _make_sandbox_result(stdout="42\n")
        tc = _make_test_case(expected_output="42\n")
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.PASSED

    def test_wrong_answer(self):
        sr = _make_sandbox_result(stdout="43\n")
        tc = _make_test_case(expected_output="42\n")
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.FAILED

    def test_timeout(self):
        sr = _make_sandbox_result(timed_out=True, exit_code=124)
        tc = _make_test_case()
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.TIMEOUT

    def test_memory_exceeded(self):
        sr = _make_sandbox_result(memory_exceeded=True, exit_code=137)
        tc = _make_test_case()
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.MEMORY_EXCEEDED

    def test_runtime_error(self):
        sr = _make_sandbox_result(exit_code=1, stdout="")
        tc = _make_test_case()
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.RUNTIME_ERROR

    def test_timeout_beats_wrong_answer(self):
        """If timed_out is True, status is TIMEOUT regardless of output."""
        sr = _make_sandbox_result(stdout="wrong", timed_out=True, exit_code=124)
        tc = _make_test_case(expected_output="correct")
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.TIMEOUT

    def test_trailing_whitespace_normalized(self):
        """Output comparison should normalize trailing whitespace."""
        sr = _make_sandbox_result(stdout="42  \n\n")
        tc = _make_test_case(expected_output="42\n")
        assert ExecutionService._classify_test_case_result(sr, tc) == _TCStatus.PASSED
