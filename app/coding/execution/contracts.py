"""
Execution Contracts — Command and result data structures

Defines the input command for triggering execution and the
structured result returned after all test cases are processed.

These are internal contracts between the execution orchestrator
and its callers (e.g. Celery worker). NOT directly exposed via API.

References:
- execution/REQUIREMENTS.md §3 (Input Contracts)
- execution/REQUIREMENTS.md §4 (Output Contracts)
"""

from dataclasses import dataclass
from typing import List, Optional

from app.coding.enums import ExecutionStatus, TestCaseStatus


@dataclass(frozen=True)
class SubmissionData:
    """Immutable snapshot of the code submission to execute."""

    language: str          # cpp | java | python3
    source_code: str
    coding_problem_id: int


@dataclass(frozen=True)
class TestCase:
    """Single test case to execute against the submission."""

    test_case_id: int
    input_data: str
    expected_output: str
    weight: float
    time_limit_ms: int
    memory_limit_kb: int
    is_hidden: bool


@dataclass(frozen=True)
class ExecuteSubmissionCommand:
    """
    Command to execute a code submission against a set of test cases.

    Constructed by the caller (Celery worker or direct invocation)
    from database records. Passed to ``ExecutionService.execute()``.
    """

    submission_id: int
    submission_data: SubmissionData
    test_cases: List[TestCase]


@dataclass(frozen=True)
class TestCaseExecutionResult:
    """Result of executing a single test case."""

    test_case_id: int
    status: TestCaseStatus
    passed: bool
    actual_output: str
    runtime_ms: int
    memory_kb: int
    exit_code: int
    stderr: str
    feedback: str


@dataclass(frozen=True)
class ExecutionResult:
    """
    Complete result of executing a submission against all test cases.

    Returned by ``ExecutionService.execute()`` to the caller.
    Contains the final status, score, and per-test-case outcomes.
    """

    submission_id: int
    execution_status: ExecutionStatus
    score: float
    total_execution_time_ms: int
    peak_memory_kb: int
    compiler_output: Optional[str]
    test_results: List[TestCaseExecutionResult]
