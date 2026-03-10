"""
Unit Tests — Coding API Service

Tests the CodingApiService business logic with mocked dependencies.
Validates authorization, validation, error handling, and data flow.
"""

import pytest
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock

from app.coding.api.service import CodingApiService
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole
from app.shared.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_identity(
    user_id: int = 1,
    user_type: str = "candidate",
    organization_id: Optional[int] = None,
    admin_role: Optional[str] = None,
) -> IdentityContext:
    """Create an IdentityContext for testing."""
    return IdentityContext(
        user_id=user_id,
        user_type=UserType(user_type),
        candidate_id=user_id if user_type == "candidate" else None,
        organization_id=organization_id,
        admin_role=AdminRole(admin_role) if admin_role else None,
        token_version=1,
        issued_at=1700000000,
        expires_at=1800000000,
    )


def _make_candidate_identity(user_id: int = 1) -> IdentityContext:
    return _make_identity(user_id=user_id, user_type="candidate")


def _make_admin_identity(user_id: int = 100) -> IdentityContext:
    return _make_identity(
        user_id=user_id,
        user_type="admin",
        organization_id=1,
        admin_role="admin",
    )


@dataclass
class FakeSubmission:
    id: int = 1
    interview_exchange_id: int = 10
    coding_problem_id: int = 5
    language: str = "python3"
    source_code: str = "print('hello')"
    execution_status: str = "pending"
    score: Optional[Decimal] = Decimal("0")
    execution_time_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    compiler_output: Optional[str] = None
    submitted_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# submit_code tests
# ---------------------------------------------------------------------------


class TestSubmitCode:
    """Tests for CodingApiService.submit_code()."""

    def _build_service(self, db_mock) -> CodingApiService:
        """Build service with mocked DB."""
        return CodingApiService(db_mock)

    def test_exchange_not_found_raises(self):
        """Raises NotFoundError when exchange does not exist."""
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None

        service = self._build_service(db)
        identity = _make_candidate_identity()

        with pytest.raises(NotFoundError):
            service.submit_code(
                identity=identity,
                interview_exchange_id=999,
                coding_problem_id=1,
                language="python3",
                source_code="code",
            )

    def test_non_coding_exchange_raises_validation_error(self):
        """Raises ValidationError when exchange has no coding_problem_id."""
        db = MagicMock()
        # Exchange exists but coding_problem_id is None
        db.execute.return_value.fetchone.side_effect = [
            (10, 1, None),  # exchange: (id, submission_id, coding_problem_id=None)
        ]

        service = self._build_service(db)
        identity = _make_admin_identity()  # Admin to skip candidate auth

        with pytest.raises(ValidationError, match="not a coding exchange"):
            service.submit_code(
                identity=identity,
                interview_exchange_id=10,
                coding_problem_id=5,
                language="python3",
                source_code="code",
            )

    def test_problem_id_mismatch_raises_validation_error(self):
        """Raises ValidationError when problem_id doesn't match exchange."""
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            (10, 1, 7),  # exchange has coding_problem_id=7
        ]

        service = self._build_service(db)
        identity = _make_admin_identity()

        with pytest.raises(ValidationError, match="mismatch"):
            service.submit_code(
                identity=identity,
                interview_exchange_id=10,
                coding_problem_id=5,  # Doesn't match 7
                language="python3",
                source_code="code",
            )

    def test_candidate_cannot_access_other_submission(self):
        """Raises AuthorizationError when candidate doesn't own exchange."""
        db = MagicMock()
        # First call: get exchange → returns (id=10, submission_id=1, problem_id=5)
        # Second call: auth check → returns user_id=999 (different from identity user_id=1)
        db.execute.return_value.fetchone.side_effect = [
            (10, 1, 5),   # exchange
            (999,),        # candidate user_id != identity user_id
        ]

        service = self._build_service(db)
        identity = _make_candidate_identity(user_id=1)

        with pytest.raises(AuthorizationError):
            service.submit_code(
                identity=identity,
                interview_exchange_id=10,
                coding_problem_id=5,
                language="python3",
                source_code="code",
            )

    def test_admin_bypasses_ownership_check(self):
        """Admins can submit for any exchange."""
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            (10, 1, 5),  # exchange exists with correct problem
        ]

        fake_entity = FakeSubmission(id=42)
        service = self._build_service(db)

        # Mock the repo create
        service._submission_repo = MagicMock()
        service._submission_repo.create.return_value = fake_entity

        identity = _make_admin_identity()
        result = service.submit_code(
            identity=identity,
            interview_exchange_id=10,
            coding_problem_id=5,
            language="python3",
            source_code="print('hello')",
        )

        assert result.submission_id == 42
        assert result.execution_status == "pending"


# ---------------------------------------------------------------------------
# get_execution_status tests
# ---------------------------------------------------------------------------


class TestGetExecutionStatus:
    """Tests for CodingApiService.get_execution_status()."""

    def test_submission_not_found_raises(self):
        """Raises NotFoundError when submission does not exist."""
        db = MagicMock()
        service = CodingApiService(db)
        service._submission_repo = MagicMock()
        service._submission_repo.get_by_id.return_value = None

        identity = _make_candidate_identity()

        with pytest.raises(NotFoundError):
            service.get_execution_status(identity=identity, submission_id=999)

    def test_returns_status_for_pending_submission(self):
        """Returns status with empty test results for pending submission."""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        service = CodingApiService(db)
        service._submission_repo = MagicMock()
        service._submission_repo.get_by_id.return_value = FakeSubmission(
            id=1,
            interview_exchange_id=10,
            submitted_at=now,
        )

        # Exchange auth: admin bypasses
        db.execute.return_value.fetchone.side_effect = [
            (10, 1, 5),  # exchange lookup
            # test results query returns empty
        ]
        # Second execute call for test results
        mock_result_2 = MagicMock()
        mock_result_2.fetchall.return_value = []
        db.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(10, 1, 5))),
            mock_result_2,
        ]

        identity = _make_admin_identity()
        result = service.get_execution_status(identity=identity, submission_id=1)

        assert result.submission_id == 1
        assert result.execution_status == "pending"
        assert result.test_results == []


# ---------------------------------------------------------------------------
# list_submissions_for_interview tests
# ---------------------------------------------------------------------------


class TestListSubmissions:
    """Tests for CodingApiService.list_submissions_for_interview()."""

    def test_admin_can_list_any_interview(self):
        """Admins can list submissions for any interview."""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Auth check skipped for admin
        # Submissions query
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, 10, 5, "python3", "passed", Decimal("100.0"), now),
            (2, 11, 6, "cpp", "failed", Decimal("50.0"), now),
        ]
        db.execute.return_value = mock_result

        service = CodingApiService(db)
        identity = _make_admin_identity()

        results = service.list_submissions_for_interview(
            identity=identity, interview_id=1
        )

        assert len(results) == 2
        assert results[0].submission_id == 1
        assert results[0].language == "python3"
        assert results[1].submission_id == 2
        assert results[1].score == 50.0
