"""
Coding Repository Implementations — SQLAlchemy concrete repositories

Each class:
- Accepts a SQLAlchemy ``Session`` via constructor
- Implements the corresponding Protocol from ``persistence.protocols``
- Maps between ORM models and domain entities via ``mappers``
- Contains ZERO business logic

Session lifecycle (commit/rollback) is managed by the caller.
Repositories call ``session.flush()`` after mutations (not ``commit``).

Follows the pattern established by admin/persistence/repositories.py.

References:
- persistence/REQUIREMENTS.md §5 (Functional Requirements)
- persistence/REQUIREMENTS.md §6 (Invariants & Constraints)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.coding.persistence.entities import CodeExecutionResult, CodeSubmission
from app.coding.persistence.mappers import (
    result_model_to_entity,
    submission_model_to_entity,
)
from app.coding.persistence.models import (
    CodeExecutionResultModel,
    CodeSubmissionModel,
)

logger = logging.getLogger(__name__)


class SqlCodeSubmissionRepository:
    """
    Concrete SQLAlchemy implementation of ``CodeSubmissionRepository``.

    Manages the ``code_submissions`` table.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        interview_exchange_id: int,
        coding_problem_id: int,
        language: str,
        source_code: str,
    ) -> CodeSubmission:
        """
        Insert a new code submission with ``execution_status='pending'``.

        Raises ``sqlalchemy.exc.IntegrityError`` if the UNIQUE constraint
        on ``interview_exchange_id`` is violated (duplicate submission).
        """
        model = CodeSubmissionModel()
        model.interview_exchange_id = interview_exchange_id
        model.coding_problem_id = coding_problem_id
        model.language = language
        model.source_code = source_code
        model.execution_status = "pending"

        self._session.add(model)
        self._session.flush()

        logger.info(
            "Code submission created",
            extra={
                "submission_id": model.id,
                "exchange_id": interview_exchange_id,
                "language": language,
            },
        )
        return submission_model_to_entity(model)

    def get_by_id(self, submission_id: int) -> Optional[CodeSubmission]:
        """Get a submission by primary key.  Returns ``None`` if not found."""
        model = self._session.get(CodeSubmissionModel, submission_id)
        return submission_model_to_entity(model) if model else None

    def get_by_exchange_id(self, exchange_id: int) -> Optional[CodeSubmission]:
        """
        Get the (at most one) submission for an exchange.

        Leverages the UNIQUE constraint on ``interview_exchange_id``.
        """
        model = (
            self._session.query(CodeSubmissionModel)
            .filter(CodeSubmissionModel.interview_exchange_id == exchange_id)
            .first()
        )
        return submission_model_to_entity(model) if model else None

    def get_for_update(self, submission_id: int) -> Optional[CodeSubmission]:
        """
        Acquire a row-level lock (``SELECT ... FOR UPDATE``) on the submission.

        The lock is held until the enclosing transaction commits or rolls back.
        Used to prevent concurrent execution of the same submission.
        """
        model = (
            self._session.query(CodeSubmissionModel)
            .filter(CodeSubmissionModel.id == submission_id)
            .with_for_update()
            .first()
        )
        return submission_model_to_entity(model) if model else None

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
        """
        Atomically update execution status and optional result fields.

        Only modifies the fields that are explicitly provided.
        """
        model = self._session.get(CodeSubmissionModel, submission_id)
        if model is None:
            logger.warning(
                "Submission not found for status update",
                extra={"submission_id": submission_id},
            )
            return

        model.execution_status = execution_status

        if score is not None:
            model.score = score
        if execution_time_ms is not None:
            model.execution_time_ms = execution_time_ms
        if memory_kb is not None:
            model.memory_kb = memory_kb
        if executed_at is not None:
            model.executed_at = executed_at

        self._session.flush()

        logger.info(
            "Submission status updated",
            extra={
                "submission_id": submission_id,
                "execution_status": execution_status,
                "score": score,
            },
        )

    def list_pending(self, limit: int = 100) -> List[CodeSubmission]:
        """
        List submissions with ``execution_status='pending'``.

        Ordered by ``submitted_at ASC`` (FIFO).
        """
        models = (
            self._session.query(CodeSubmissionModel)
            .filter(CodeSubmissionModel.execution_status == "pending")
            .order_by(CodeSubmissionModel.submitted_at.asc())
            .limit(limit)
            .all()
        )
        return [submission_model_to_entity(m) for m in models]

    def count_submissions_since(
        self,
        interview_exchange_id: int,
        since: datetime,
    ) -> int:
        """Count submissions for an exchange since a timestamp."""
        return (
            self._session.query(func.count(CodeSubmissionModel.id))
            .filter(
                CodeSubmissionModel.interview_exchange_id == interview_exchange_id,
                CodeSubmissionModel.submitted_at >= since,
            )
            .scalar()
            or 0
        )


class SqlCodeExecutionResultRepository:
    """
    Concrete SQLAlchemy implementation of ``CodeExecutionResultRepository``.

    Manages the ``code_execution_results`` table.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

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
        """
        Insert a test case execution result.

        Raises ``sqlalchemy.exc.IntegrityError`` if the UNIQUE constraint
        on ``(code_submission_id, test_case_id)`` is violated.
        """
        model = CodeExecutionResultModel()
        model.code_submission_id = code_submission_id
        model.test_case_id = test_case_id
        model.passed = passed
        model.actual_output = actual_output
        model.runtime_ms = runtime_ms
        model.memory_kb = memory_kb
        model.exit_code = exit_code
        model.runtime_output = runtime_output
        model.feedback = feedback

        self._session.add(model)
        self._session.flush()

        logger.info(
            "Execution result created",
            extra={
                "result_id": model.id,
                "submission_id": code_submission_id,
                "test_case_id": test_case_id,
                "passed": passed,
            },
        )
        return result_model_to_entity(model)

    def get_by_submission(
        self, submission_id: int
    ) -> List[CodeExecutionResult]:
        """Get all test case results for a submission, ordered by ``test_case_id``."""
        models = (
            self._session.query(CodeExecutionResultModel)
            .filter(CodeExecutionResultModel.code_submission_id == submission_id)
            .order_by(CodeExecutionResultModel.test_case_id.asc())
            .all()
        )
        return [result_model_to_entity(m) for m in models]

    def get_by_submission_and_test(
        self, submission_id: int, test_case_id: int
    ) -> Optional[CodeExecutionResult]:
        """Get a specific test case result (for idempotency checks)."""
        model = (
            self._session.query(CodeExecutionResultModel)
            .filter(
                CodeExecutionResultModel.code_submission_id == submission_id,
                CodeExecutionResultModel.test_case_id == test_case_id,
            )
            .first()
        )
        return result_model_to_entity(model) if model else None

    def exists(self, submission_id: int, test_case_id: int) -> bool:
        """Check whether a result already exists for the given pair (efficient)."""
        count = (
            self._session.query(func.count(CodeExecutionResultModel.id))
            .filter(
                CodeExecutionResultModel.code_submission_id == submission_id,
                CodeExecutionResultModel.test_case_id == test_case_id,
            )
            .scalar()
        )
        return (count or 0) > 0
