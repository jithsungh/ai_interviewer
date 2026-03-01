"""
Unit Tests — SubmissionRepository

Tests the repository layer with a **mocked** SQLAlchemy session.
Verifies that:
  1. Successful transitions return (model, True)
  2. Idempotent hits return (model, False)
  3. Invalid states raise StateTransitionError
  4. Missing rows raise NotFoundError
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.interview.session.domain.state_machine import (
    StateTransitionError,
    SubmissionStatus,
)
from app.interview.session.persistence.repository import SubmissionRepository
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_submission(**overrides):
    """Create a minimal fake submission object."""
    defaults = dict(
        id=1,
        candidate_id=100,
        window_id=10,
        role_id=20,
        template_id=30,
        mode="async",
        status=SubmissionStatus.PENDING.value,
        consent_captured=False,
        final_score=None,
        scheduled_start=None,
        scheduled_end=None,
        started_at=None,
        submitted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        exchanges=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_db_session(execute_returns_row: bool, query_returns=None):
    """
    Build a mock SQLAlchemy session.

    Args:
        execute_returns_row: if True, the UPDATE RETURNING yields a row.
        query_returns: what ``query(...).filter(...).first()`` returns.
    """
    db = MagicMock()

    # execute().fetchone()
    result = MagicMock()
    if execute_returns_row:
        result.fetchone.return_value = SimpleNamespace(id=1)
    else:
        result.fetchone.return_value = None
    db.execute.return_value = result

    # query(...).filter(...).first()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = query_returns
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock

    return db


# ═══════════════════════════════════════════════════════════════════════════
# transition_to_in_progress
# ═══════════════════════════════════════════════════════════════════════════


class TestTransitionToInProgress:
    def test_success(self):
        """Pending → in_progress updates the row and returns (sub, True)."""
        sub = _make_submission(status=SubmissionStatus.IN_PROGRESS.value)
        db = _mock_db_session(execute_returns_row=True, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_in_progress(1, 100)
        assert transitioned is True
        assert result.status == SubmissionStatus.IN_PROGRESS.value
        db.execute.assert_called_once()
        db.expire_all.assert_called_once()

    def test_idempotent(self):
        """If already in_progress, return (sub, False)."""
        sub = _make_submission(status=SubmissionStatus.IN_PROGRESS.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_in_progress(1, 100)
        assert transitioned is False
        assert result.status == SubmissionStatus.IN_PROGRESS.value

    def test_invalid_state(self):
        """If status is 'completed', raise StateTransitionError."""
        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        with pytest.raises(StateTransitionError):
            repo.transition_to_in_progress(1, 100)

    def test_not_found(self):
        """If submission does not exist, raise NotFoundError."""
        db = _mock_db_session(execute_returns_row=False, query_returns=None)
        repo = SubmissionRepository(db)

        with pytest.raises(NotFoundError):
            repo.transition_to_in_progress(1, 100)


# ═══════════════════════════════════════════════════════════════════════════
# transition_to_completed
# ═══════════════════════════════════════════════════════════════════════════


class TestTransitionToCompleted:
    def test_success(self):
        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = _mock_db_session(execute_returns_row=True, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_completed(1, 100)
        assert transitioned is True

    def test_idempotent(self):
        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_completed(1, 100)
        assert transitioned is False

    def test_invalid_state(self):
        sub = _make_submission(status=SubmissionStatus.PENDING.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        with pytest.raises(StateTransitionError):
            repo.transition_to_completed(1, 100)


# ═══════════════════════════════════════════════════════════════════════════
# transition_to_expired
# ═══════════════════════════════════════════════════════════════════════════


class TestTransitionToExpired:
    def test_success(self):
        sub = _make_submission(status=SubmissionStatus.EXPIRED.value)
        db = _mock_db_session(execute_returns_row=True, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_expired(1)
        assert transitioned is True

    def test_idempotent(self):
        sub = _make_submission(status=SubmissionStatus.EXPIRED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_expired(1)
        assert transitioned is False

    def test_invalid_state(self):
        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        with pytest.raises(StateTransitionError):
            repo.transition_to_expired(1)


# ═══════════════════════════════════════════════════════════════════════════
# transition_to_cancelled
# ═══════════════════════════════════════════════════════════════════════════


class TestTransitionToCancelled:
    def test_success(self):
        sub = _make_submission(status=SubmissionStatus.CANCELLED.value)
        db = _mock_db_session(execute_returns_row=True, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_cancelled(1)
        assert transitioned is True

    def test_idempotent(self):
        sub = _make_submission(status=SubmissionStatus.CANCELLED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_cancelled(1)
        assert transitioned is False

    def test_invalid_state(self):
        sub = _make_submission(status=SubmissionStatus.REVIEWED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        with pytest.raises(StateTransitionError):
            repo.transition_to_cancelled(1)


# ═══════════════════════════════════════════════════════════════════════════
# transition_to_reviewed
# ═══════════════════════════════════════════════════════════════════════════


class TestTransitionToReviewed:
    def test_success_from_completed(self):
        sub = _make_submission(status=SubmissionStatus.REVIEWED.value)
        db = _mock_db_session(execute_returns_row=True, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_reviewed(1)
        assert transitioned is True

    def test_idempotent(self):
        sub = _make_submission(status=SubmissionStatus.REVIEWED.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        result, transitioned = repo.transition_to_reviewed(1)
        assert transitioned is False

    def test_invalid_from_pending(self):
        sub = _make_submission(status=SubmissionStatus.PENDING.value)
        db = _mock_db_session(execute_returns_row=False, query_returns=sub)
        repo = SubmissionRepository(db)

        with pytest.raises(StateTransitionError):
            repo.transition_to_reviewed(1)
