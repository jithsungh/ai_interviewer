"""
Execution Service — Lifecycle orchestrator for code submissions

Orchestrates the full execution workflow:
1.  Acquire lock on submission  (prevent concurrent execution)
2.  Transition status pending → running
3.  For each test case:
    a. Execute code via sandbox
    b. Compare output vs expected
    c. Classify result (passed / failed / timeout / OOM / error)
    d. Persist individual test case result
4.  Calculate weighted score
5.  Determine final status
6.  Persist final status + score atomically
7.  Return structured ``ExecutionResult``

The service is **synchronous** and **blocking**.  It is designed to
be called from a Celery worker or equivalent task runner, not from
the FastAPI request cycle.

No FastAPI imports.  No direct DB imports.  Business logic only.

References:
- execution/REQUIREMENTS.md §5 (Execution Workflow)
- execution/REQUIREMENTS.md §6 (Invariants & Constraints)
- execution/REQUIREMENTS.md §7 (Dependent Modules)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.coding.enums import ExecutionStatus, TestCaseStatus
from app.coding.evaluation.comparator import compare_outputs
from app.coding.evaluation.scorer import calculate_score, generate_feedback
from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    ExecutionResult,
    TestCase,
    TestCaseExecutionResult,
)
from app.coding.execution.state_machine import (
    is_terminal_state,
    is_valid_transition,
    validate_transition,
)
from app.coding.persistence.protocols import (
    CodeExecutionResultRepository,
    CodeSubmissionRepository,
)
from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult
from app.coding.sandbox.executor import SandboxExecutor
from app.shared.observability.logging import ContextLogger, get_context_logger
from app.shared.observability.metrics import metrics

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    Orchestrates code execution for a single submission.

    Injected with repository protocols and the sandbox executor via
    constructor (dependency injection).  The service is stateless —
    all mutable state is managed through the repositories.

    Thread safety: safe to share across threads provided each call
    to ``execute()`` uses a separate database session (and therefore
    separate repository instances bound to that session).
    """

    def __init__(
        self,
        submission_repo: CodeSubmissionRepository,
        result_repo: CodeExecutionResultRepository,
        sandbox_executor: SandboxExecutor,
    ) -> None:
        self._submission_repo = submission_repo
        self._result_repo = result_repo
        self._sandbox = sandbox_executor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, command: ExecuteSubmissionCommand) -> ExecutionResult:
        """
        Execute a code submission against all test cases.

        This is the **single entry point** for the execution lifecycle.

        Args:
            command: The execution command containing submission data
                     and test cases.

        Returns:
            ``ExecutionResult`` with the final status, score, and
            per-test-case outcomes.
        """
        ctx_logger = get_context_logger(submission_id=command.submission_id)

        ctx_logger.info(
            "Execution started",
            event_type="execution_started",
            metadata={
                "submission_id": command.submission_id,
                "language": command.submission_data.language,
                "test_case_count": len(command.test_cases),
            },
        )

        # Step 1 — Acquire lock and transition to RUNNING
        submission = self._submission_repo.get_for_update(command.submission_id)
        if submission is None:
            ctx_logger.warning(
                "Submission not found",
                event_type="execution_submission_not_found",
                metadata={"submission_id": command.submission_id},
            )
            return self._error_result(command.submission_id, "Submission not found")

        current_status = ExecutionStatus(submission.execution_status)

        if is_terminal_state(current_status):
            ctx_logger.warning(
                "Submission already in terminal state",
                event_type="execution_already_terminal",
                metadata={
                    "submission_id": command.submission_id,
                    "current_status": current_status.value,
                },
            )
            return self._error_result(
                command.submission_id,
                f"Submission already finalized: {current_status.value}",
            )

        if not is_valid_transition(current_status, ExecutionStatus.RUNNING):
            ctx_logger.warning(
                "Cannot transition to running",
                event_type="execution_invalid_transition",
                metadata={
                    "submission_id": command.submission_id,
                    "current_status": current_status.value,
                },
            )
            return self._error_result(
                command.submission_id,
                f"Cannot run submission in state: {current_status.value}",
            )

        # Transition: pending → running
        self._submission_repo.update_status(
            command.submission_id, ExecutionStatus.RUNNING.value
        )

        # Step 2 — Execute test cases
        try:
            test_results = self._execute_all_test_cases(command, ctx_logger)
        except Exception as exc:
            ctx_logger.error(
                "Execution failed with unexpected error",
                event_type="execution_unexpected_error",
                metadata={
                    "submission_id": command.submission_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            self._finalize_submission(
                command.submission_id,
                ExecutionStatus.ERROR,
                score=0.0,
                execution_time_ms=0,
                memory_kb=0,
                compiler_output=None,
                ctx_logger=ctx_logger,
            )
            return self._error_result(command.submission_id, str(exc))

        # Step 3 — Calculate score
        weights = [tc.weight for tc in command.test_cases]
        passed_flags = [r.passed for r in test_results]
        score = calculate_score(weights, passed_flags)

        # Step 4 — Compute aggregate metrics
        total_time = sum(r.runtime_ms for r in test_results)
        peak_memory = max((r.memory_kb for r in test_results), default=0)

        # Step 5 — Determine final status
        final_status = self._determine_final_status(test_results)

        # Step 6 — Check for compilation output (first test may have it)
        compiler_output = self._extract_compiler_output(test_results)

        # Step 7 — Persist final status
        self._finalize_submission(
            command.submission_id,
            final_status,
            score=score,
            execution_time_ms=total_time,
            memory_kb=peak_memory,
            compiler_output=compiler_output,
            ctx_logger=ctx_logger,
        )

        result = ExecutionResult(
            submission_id=command.submission_id,
            execution_status=final_status,
            score=score,
            total_execution_time_ms=total_time,
            peak_memory_kb=peak_memory,
            compiler_output=compiler_output,
            test_results=test_results,
        )

        ctx_logger.info(
            "Execution completed",
            event_type="execution_completed",
            metadata={
                "submission_id": command.submission_id,
                "final_status": final_status.value,
                "score": score,
                "total_time_ms": total_time,
                "peak_memory_kb": peak_memory,
            },
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_all_test_cases(
        self,
        command: ExecuteSubmissionCommand,
        ctx_logger: ContextLogger,
    ) -> List[TestCaseExecutionResult]:
        """
        Execute every test case sequentially and persist results.

        Idempotent: skips test cases that already have a persisted result
        (supports retry after partial execution).
        """
        results: List[TestCaseExecutionResult] = []

        for tc in command.test_cases:
            # Idempotency: skip if result already exists
            if self._result_repo.exists(command.submission_id, tc.test_case_id):
                ctx_logger.info(
                    "Skipping already-executed test case",
                    event_type="execution_test_case_skipped",
                    metadata={
                        "submission_id": command.submission_id,
                        "test_case_id": tc.test_case_id,
                    },
                )
                existing = self._result_repo.get_by_submission_and_test(
                    command.submission_id, tc.test_case_id
                )
                if existing is not None:
                    results.append(
                        TestCaseExecutionResult(
                            test_case_id=existing.test_case_id,
                            status=(
                                TestCaseStatus.PASSED
                                if existing.passed
                                else TestCaseStatus.FAILED
                            ),
                            passed=existing.passed,
                            actual_output=existing.actual_output or "",
                            runtime_ms=existing.runtime_ms or 0,
                            memory_kb=existing.memory_kb or 0,
                            exit_code=existing.exit_code or 0,
                            stderr=existing.runtime_output or "",
                            feedback=existing.feedback or "",
                        )
                    )
                continue

            tc_result = self._execute_single_test_case(command, tc, ctx_logger)
            results.append(tc_result)

            # Persist individual result
            self._result_repo.create(
                code_submission_id=command.submission_id,
                test_case_id=tc.test_case_id,
                passed=tc_result.passed,
                actual_output=tc_result.actual_output,
                runtime_ms=tc_result.runtime_ms,
                memory_kb=tc_result.memory_kb,
                exit_code=tc_result.exit_code,
                runtime_output=tc_result.stderr,
                feedback=tc_result.feedback,
            )

        return results

    def _execute_single_test_case(
        self,
        command: ExecuteSubmissionCommand,
        tc: TestCase,
        ctx_logger: ContextLogger,
    ) -> TestCaseExecutionResult:
        """
        Execute a single test case via the sandbox and classify the result.
        """
        sandbox_request = SandboxExecutionRequest(
            language=command.submission_data.language,
            source_code=command.submission_data.source_code,
            input_data=tc.input_data,
            time_limit_ms=tc.time_limit_ms,
            memory_limit_kb=tc.memory_limit_kb,
        )

        try:
            sandbox_result: SandboxExecutionResult = self._sandbox.execute(
                sandbox_request
            )
        except Exception as exc:
            ctx_logger.error(
                "Sandbox execution failed",
                event_type="sandbox_execution_exception",
                metadata={
                    "submission_id": command.submission_id,
                    "test_case_id": tc.test_case_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return TestCaseExecutionResult(
                test_case_id=tc.test_case_id,
                status=TestCaseStatus.RUNTIME_ERROR,
                passed=False,
                actual_output="",
                runtime_ms=0,
                memory_kb=0,
                exit_code=-1,
                stderr=str(exc),
                feedback="System Error",
            )

        # Check for compilation error
        if sandbox_result.compilation_output:
            return TestCaseExecutionResult(
                test_case_id=tc.test_case_id,
                status=TestCaseStatus.RUNTIME_ERROR,
                passed=False,
                actual_output="",
                runtime_ms=0,
                memory_kb=0,
                exit_code=sandbox_result.exit_code,
                stderr=sandbox_result.compilation_output,
                feedback="Compilation Error",
            )

        # Classify result
        status = self._classify_test_case_result(sandbox_result, tc)
        passed = status == TestCaseStatus.PASSED
        feedback = generate_feedback(status)

        return TestCaseExecutionResult(
            test_case_id=tc.test_case_id,
            status=status,
            passed=passed,
            actual_output=sandbox_result.stdout,
            runtime_ms=sandbox_result.runtime_ms,
            memory_kb=sandbox_result.memory_kb,
            exit_code=sandbox_result.exit_code,
            stderr=sandbox_result.stderr,
            feedback=feedback,
        )

    @staticmethod
    def _classify_test_case_result(
        sandbox_result: SandboxExecutionResult,
        tc: TestCase,
    ) -> TestCaseStatus:
        """
        Classify a sandbox result into a ``TestCaseStatus``.

        Priority (per execution/REQUIREMENTS.md §5):
        1. Timed out → TIMEOUT
        2. Memory exceeded → MEMORY_EXCEEDED
        3. Non-zero exit code → RUNTIME_ERROR
        4. Output mismatch → FAILED
        5. Otherwise → PASSED
        """
        if sandbox_result.timed_out:
            return TestCaseStatus.TIMEOUT

        if sandbox_result.memory_exceeded:
            return TestCaseStatus.MEMORY_EXCEEDED

        if sandbox_result.exit_code != 0:
            return TestCaseStatus.RUNTIME_ERROR

        if not compare_outputs(tc.expected_output, sandbox_result.stdout):
            return TestCaseStatus.FAILED

        return TestCaseStatus.PASSED

    @staticmethod
    def _determine_final_status(
        test_results: List[TestCaseExecutionResult],
    ) -> ExecutionStatus:
        """
        Determine the overall submission status from individual test results.

        Priority (per execution/REQUIREMENTS.md §5):
        1. All passed → PASSED
        2. Any timeout → TIMEOUT
        3. Any memory exceeded → MEMORY_EXCEEDED
        4. Any runtime error → ERROR
        5. Otherwise → FAILED
        """
        if not test_results:
            return ExecutionStatus.ERROR

        if all(r.passed for r in test_results):
            return ExecutionStatus.PASSED

        if any(r.status == TestCaseStatus.TIMEOUT for r in test_results):
            return ExecutionStatus.TIMEOUT

        if any(r.status == TestCaseStatus.MEMORY_EXCEEDED for r in test_results):
            return ExecutionStatus.MEMORY_EXCEEDED

        if any(r.status == TestCaseStatus.RUNTIME_ERROR for r in test_results):
            return ExecutionStatus.ERROR

        return ExecutionStatus.FAILED

    def _finalize_submission(
        self,
        submission_id: int,
        final_status: ExecutionStatus,
        *,
        score: float,
        execution_time_ms: int,
        memory_kb: int,
        compiler_output: Optional[str],
        ctx_logger: ContextLogger,
    ) -> None:
        """
        Persist the final execution result to the submissions table.

        Validates the transition running → terminal before writing.
        """
        # Re-read current status under lock
        submission = self._submission_repo.get_for_update(submission_id)
        if submission is None:
            ctx_logger.warning(
                "Submission vanished during finalization",
                event_type="execution_submission_vanished",
                metadata={"submission_id": submission_id},
            )
            return

        current = ExecutionStatus(submission.execution_status)

        if is_terminal_state(current):
            ctx_logger.warning(
                "Submission already finalized by another worker",
                event_type="execution_already_finalized",
                metadata={
                    "submission_id": submission_id,
                    "current_status": current.value,
                },
            )
            return

        if not is_valid_transition(current, final_status):
            ctx_logger.warning(
                "Invalid finalization transition",
                event_type="execution_invalid_finalization",
                metadata={
                    "submission_id": submission_id,
                    "current": current.value,
                    "target": final_status.value,
                },
            )
            return

        self._submission_repo.update_status(
            submission_id,
            final_status.value,
            score=score,
            execution_time_ms=execution_time_ms,
            memory_kb=memory_kb,
            compiler_output=compiler_output,
            executed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _extract_compiler_output(
        test_results: List[TestCaseExecutionResult],
    ) -> Optional[str]:
        """Extract compilation error output from test results if present."""
        for r in test_results:
            if r.feedback == "Compilation Error" and r.stderr:
                return r.stderr
        return None

    @staticmethod
    def _error_result(
        submission_id: int,
        error_message: str,
    ) -> ExecutionResult:
        """Build an ``ExecutionResult`` for early-exit error cases."""
        return ExecutionResult(
            submission_id=submission_id,
            execution_status=ExecutionStatus.ERROR,
            score=0.0,
            total_execution_time_ms=0,
            peak_memory_kb=0,
            compiler_output=None,
            test_results=[],
        )
