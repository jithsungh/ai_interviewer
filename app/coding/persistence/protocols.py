"""
Coding Repository Protocols — Abstract interfaces for data access

Domain services depend on these protocols, never on concrete
SQLAlchemy repository classes.  Uses ``typing.Protocol`` for
structural subtyping (consistent with admin/domain/protocols.py).

References:
- persistence/REQUIREMENTS.md §3 (Repository Methods)
- admin/domain/protocols.py (pattern reference)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable

from app.coding.persistence.entities import CodeExecutionResult, CodeSubmission


@runtime_checkable
class CodeSubmissionRepository(Protocol):
    """CRUD operations for the ``code_submissions`` table."""

    def create(
        self,
        interview_exchange_id: int,
        coding_problem_id: int,
        language: str,
        source_code: str,
    ) -> CodeSubmission:
        """Create a new code submission with ``execution_status='pending'``."""
        ...

    def get_by_id(self, submission_id: int) -> Optional[CodeSubmission]:
        """Get a submission by primary key."""
        ...

    def get_by_exchange_id(self, exchange_id: int) -> Optional[CodeSubmission]:
        """Get the (at most one) submission for an exchange."""
        ...

    def get_for_update(self, submission_id: int) -> Optional[CodeSubmission]:
        """Get a submission with ``SELECT ... FOR UPDATE`` (row-level lock)."""
        ...

    def update_status(
        self,
        submission_id: int,
        execution_status: str,
        *,
        score: Optional[float] = None,
        execution_time_ms: Optional[int] = None,
        memory_kb: Optional[int] = None,
        compiler_output: Optional[str] = None,
        executed_at: Optional[datetime] = None,
    ) -> None:
        """Update execution status and optional result fields."""
        ...

    def list_pending(self, limit: int = 100) -> List[CodeSubmission]:
        """List submissions with ``execution_status='pending'`` (FIFO)."""
        ...

    def count_submissions_since(
        self,
        interview_exchange_id: int,
        since: datetime,
    ) -> int:
        """Count submissions for an exchange since a timestamp."""
        ...


@runtime_checkable
class CodeExecutionResultRepository(Protocol):
    """CRUD operations for the ``code_execution_results`` table."""

    def create(
        self,
        code_submission_id: int,
        test_case_id: int,
        passed: bool,
        actual_output: str,
        runtime_ms: int,
        memory_kb: int,
        exit_code: int,
        runtime_output: str,
        feedback: str,
    ) -> CodeExecutionResult:
        """Create a test case execution result."""
        ...

    def get_by_submission(
        self, submission_id: int
    ) -> List[CodeExecutionResult]:
        """Get all test case results for a submission, ordered by test_case_id."""
        ...

    def get_by_submission_and_test(
        self, submission_id: int, test_case_id: int
    ) -> Optional[CodeExecutionResult]:
        """Get a specific test case result (for idempotency checks)."""
        ...

    def exists(self, submission_id: int, test_case_id: int) -> bool:
        """Check whether a result already exists for the given pair."""
        ...
