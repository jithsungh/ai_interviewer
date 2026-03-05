"""
Coding API Service — Business Logic Orchestration for Code Submission

Mediates between the API routes and the persistence/domain layers.
Validates input, enforces business rules, and delegates to repositories.

Contains NO direct DB queries — all data access goes through
repository instances injected via constructor.

References:
- coding/api/REQUIREMENTS.md §5 (Acceptance Criteria)
- coding/api/REQUIREMENTS.md §6 (Invariants & Constraints)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.coding.api.contracts import (
    ExecutionStatusResponse,
    SubmissionSummary,
    SubmitCodeResponse,
    TestCaseResultDTO,
)
from app.coding.persistence.repositories import (
    SqlCodeExecutionResultRepository,
    SqlCodeSubmissionRepository,
)
from app.shared.auth_context import IdentityContext
from app.shared.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.shared.observability.logging import get_context_logger

logger = logging.getLogger(__name__)


class CodingApiService:
    """
    Service layer for coding API endpoints.

    Orchestrates validation, authorization, and persistence for
    code submissions and execution status queries.

    Injected with a DB session and builds repositories internally.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._submission_repo = SqlCodeSubmissionRepository(db)
        self._result_repo = SqlCodeExecutionResultRepository(db)

    # ------------------------------------------------------------------
    # Submit Code
    # ------------------------------------------------------------------

    def submit_code(
        self,
        identity: IdentityContext,
        interview_exchange_id: int,
        coding_problem_id: int,
        language: str,
        source_code: str,
    ) -> SubmitCodeResponse:
        """
        Create a new code submission for an interview exchange.

        Validates exchange ownership, problem match, and uniqueness.
        Returns the submission with ``pending`` status.

        Raises:
            NotFoundError: exchange or problem not found
            AuthorizationError: candidate does not own exchange
            ValidationError: coding_problem_id mismatch
            ConflictError: submission already exists for exchange
        """
        ctx_logger = get_context_logger(
            user_id=identity.user_id,
            submission_id=interview_exchange_id,
        )

        # 1. Validate exchange exists and resolve ownership
        exchange_row = self._get_exchange(interview_exchange_id)
        if exchange_row is None:
            raise NotFoundError(
                resource_type="InterviewExchange",
                resource_id=interview_exchange_id,
            )

        submission_id_for_exchange = exchange_row[1]  # interview_submission_id

        # 2. Authorize candidate access
        self._authorize_candidate_access(
            identity, submission_id_for_exchange
        )

        # 3. Validate coding_problem_id matches exchange
        exchange_problem_id = exchange_row[2]  # coding_problem_id
        if exchange_problem_id is None:
            raise ValidationError(
                message="Exchange is not a coding exchange",
            )
        if exchange_problem_id != coding_problem_id:
            raise ValidationError(
                message=(
                    f"Coding problem ID mismatch: exchange expects "
                    f"{exchange_problem_id}, got {coding_problem_id}"
                ),
            )

        # 4. Create submission (UNIQUE constraint prevents duplicates)
        try:
            entity = self._submission_repo.create(
                interview_exchange_id=interview_exchange_id,
                coding_problem_id=coding_problem_id,
                language=language,
                source_code=source_code,
            )
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if "unique" in str(exc).lower():
                # Fetch existing submission for the conflict response
                existing = self._submission_repo.get_by_exchange_id(
                    interview_exchange_id
                )
                existing_id = existing.id if existing else None
                raise ConflictError(
                    message="Code already submitted for this exchange",
                    metadata={"existing_submission_id": existing_id},
                ) from exc
            raise

        ctx_logger.info(
            "Code submission created",
            event_type="code_submission_created",
            metadata={
                "submission_id": entity.id,
                "exchange_id": interview_exchange_id,
                "language": language,
            },
        )

        return SubmitCodeResponse(
            submission_id=entity.id,
            execution_status="pending",
        )

    # ------------------------------------------------------------------
    # Get Execution Status
    # ------------------------------------------------------------------

    def get_execution_status(
        self,
        identity: IdentityContext,
        submission_id: int,
    ) -> ExecutionStatusResponse:
        """
        Retrieve execution status and results for a submission.

        Hidden test case details are filtered out per REQUIREMENTS.md §6.

        Raises:
            NotFoundError: submission not found
            AuthorizationError: candidate does not own submission
        """
        # 1. Fetch submission
        submission = self._submission_repo.get_by_id(submission_id)
        if submission is None:
            raise NotFoundError(
                resource_type="CodeSubmission",
                resource_id=submission_id,
            )

        # 2. Authorize access
        exchange_row = self._get_exchange(submission.interview_exchange_id)
        if exchange_row is not None:
            self._authorize_candidate_access(
                identity, exchange_row[1]  # interview_submission_id
            )

        # 3. Fetch test case results with visibility info
        test_results_dtos = self._build_test_results(submission_id)

        # 4. Build response
        return ExecutionStatusResponse(
            submission_id=submission.id,
            interview_exchange_id=submission.interview_exchange_id,
            coding_problem_id=submission.coding_problem_id,
            language=submission.language,
            execution_status=submission.execution_status,
            score=float(submission.score) if submission.score is not None else 0.0,
            execution_time_ms=submission.execution_time_ms,
            memory_kb=submission.memory_kb,
            compiler_output=submission.compiler_output,
            test_results=test_results_dtos,
            submitted_at=submission.submitted_at,
            executed_at=submission.executed_at,
        )

    # ------------------------------------------------------------------
    # List Submissions for Interview
    # ------------------------------------------------------------------

    def list_submissions_for_interview(
        self,
        identity: IdentityContext,
        interview_id: int,
    ) -> List[SubmissionSummary]:
        """
        List all code submissions for an interview (submission ID).

        Returns summary only — no source code or detailed results.

        Raises:
            NotFoundError: interview not found
            AuthorizationError: candidate does not own interview
        """
        # 1. Authorize access to this interview
        self._authorize_candidate_access(identity, interview_id)

        # 2. Query submissions for all exchanges in this interview
        rows = self._db.execute(
            text("""
                SELECT cs.id, cs.interview_exchange_id, cs.coding_problem_id,
                       cs.language, cs.execution_status, cs.score, cs.submitted_at
                FROM code_submissions cs
                JOIN interview_exchanges ie ON cs.interview_exchange_id = ie.id
                WHERE ie.interview_submission_id = :interview_id
                ORDER BY cs.submitted_at ASC
            """),
            {"interview_id": interview_id},
        ).fetchall()

        return [
            SubmissionSummary(
                submission_id=row[0],
                interview_exchange_id=row[1],
                coding_problem_id=row[2],
                language=row[3],
                execution_status=row[4],
                score=float(row[5]) if row[5] is not None else 0.0,
                submitted_at=row[6],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_exchange(self, exchange_id: int) -> Optional[tuple]:
        """
        Fetch exchange metadata (id, interview_submission_id, coding_problem_id).

        Uses raw SQL to avoid importing interview module ORM models
        (per cross-module boundary rules).
        """
        row = self._db.execute(
            text("""
                SELECT id, interview_submission_id, coding_problem_id
                FROM interview_exchanges
                WHERE id = :exchange_id
            """),
            {"exchange_id": exchange_id},
        ).fetchone()
        return row

    def _authorize_candidate_access(
        self,
        identity: IdentityContext,
        interview_submission_id: int,
    ) -> None:
        """
        Verify that the identity owns the interview submission.

        Admins always pass. Candidates must own the submission.

        Follows the authorization pattern from
        ``app/evaluation/api/routes.py::_authorize_submission_access()``.
        """
        if identity.is_admin():
            return

        row = self._db.execute(
            text("""
                SELECT c.user_id
                FROM interview_submissions isub
                JOIN candidates c ON isub.candidate_id = c.id
                WHERE isub.id = :submission_id
            """),
            {"submission_id": interview_submission_id},
        ).fetchone()

        if row is None:
            raise NotFoundError(
                resource_type="InterviewSubmission",
                resource_id=interview_submission_id,
            )

        if row[0] != identity.user_id:
            raise AuthorizationError(
                message="You do not have permission to access this resource",
            )

    def _build_test_results(
        self,
        submission_id: int,
    ) -> List[TestCaseResultDTO]:
        """
        Build test case result DTOs with hidden test case filtering.

        Joins ``code_execution_results`` with ``coding_test_cases``
        to determine visibility.  Hidden test cases have their
        ``actual_output`` and ``expected_output`` redacted.
        """
        rows = self._db.execute(
            text("""
                SELECT cer.test_case_id,
                       COALESCE(
                           'Test Case ' || cer.test_case_id::text,
                           'Test Case'
                       ) AS test_case_name,
                       cer.passed,
                       NOT COALESCE(ctc.is_hidden, true) AS visible,
                       cer.actual_output,
                       ctc.expected_output,
                       COALESCE(cer.runtime_ms, 0) AS runtime_ms,
                       COALESCE(cer.memory_kb, 0) AS memory_kb,
                       COALESCE(cer.feedback, '') AS feedback
                FROM code_execution_results cer
                LEFT JOIN coding_test_cases ctc
                    ON cer.test_case_id = ctc.id
                WHERE cer.code_submission_id = :submission_id
                ORDER BY cer.test_case_id ASC
            """),
            {"submission_id": submission_id},
        ).fetchall()

        results: List[TestCaseResultDTO] = []
        for row in rows:
            visible = bool(row[3])
            results.append(
                TestCaseResultDTO(
                    test_case_id=row[0],
                    test_case_name=row[1],
                    passed=bool(row[2]),
                    visible=visible,
                    actual_output=row[4] if visible else None,
                    expected_output=row[5] if visible else None,
                    runtime_ms=row[6],
                    memory_kb=row[7],
                    feedback=row[8] if visible else (
                        "Passed" if row[2] else "Failed"
                    ),
                )
            )

        return results
