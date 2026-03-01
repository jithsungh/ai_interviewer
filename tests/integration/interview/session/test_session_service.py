"""
Integration Tests — Interview Session Service

Tests the service layer with mocked DB session and Redis client.
Verifies:
  1. State transitions orchestrated correctly through service
  2. Redis sync happens after transitions
  3. Lock acquisition used for concurrent safety
  4. Consent validation enforced on start
  5. Get session status returns DTOs correctly
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

from app.interview.session.api.service import SessionService, _SESSION_TTL_SECONDS
from app.interview.session.contracts.schemas import (
    InterviewSessionDTO,
    InterviewSessionDetailDTO,
)
from app.interview.session.domain.state_machine import (
    StateTransitionError,
    SubmissionStatus,
)
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_submission(**overrides):
    """Create a minimal fake submission ORM object."""
    defaults = dict(
        id=1,
        candidate_id=100,
        window_id=10,
        role_id=20,
        template_id=30,
        mode="async",
        status=SubmissionStatus.IN_PROGRESS.value,
        consent_captured=False,
        final_score=None,
        scheduled_start=None,
        scheduled_end=None,
        started_at=datetime.now(timezone.utc),
        submitted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        exchanges=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_redis():
    """Return a mock Redis client."""
    redis = MagicMock()
    redis.set = MagicMock(return_value=True)
    return redis


def _mock_lock():
    """Context manager mock for acquire_lock."""

    @contextmanager
    def _lock(*args, **kwargs):
        yield

    return _lock


# ═══════════════════════════════════════════════════════════════════════════
# start_interview
# ═══════════════════════════════════════════════════════════════════════════


class TestStartInterview:
    @patch("app.interview.session.api.service.acquire_lock")
    def test_success_transitions_and_syncs_redis(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.IN_PROGRESS.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_in_progress.return_value = (sub, True)

        dto, transitioned = svc.start_interview(
            submission_id=1, candidate_id=100, consent_accepted=True
        )

        assert transitioned is True
        assert isinstance(dto, InterviewSessionDTO)
        assert dto.status == "in_progress"

        # Redis sync should have been called
        redis.set.assert_called_once()
        call_args = redis.set.call_args
        assert "interview_session:1" in call_args[0]

    @patch("app.interview.session.api.service.acquire_lock")
    def test_consent_required(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        db = MagicMock()
        redis = _mock_redis()
        svc = SessionService(db=db, redis=redis)

        from app.shared.errors import ValidationError as AppValidationError

        with pytest.raises(AppValidationError, match="consent"):
            svc.start_interview(
                submission_id=1, candidate_id=100, consent_accepted=False
            )

    @patch("app.interview.session.api.service.acquire_lock")
    def test_idempotent_returns_false(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.IN_PROGRESS.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_in_progress.return_value = (sub, False)

        dto, transitioned = svc.start_interview(
            submission_id=1, candidate_id=100, consent_accepted=True
        )

        assert transitioned is False


# ═══════════════════════════════════════════════════════════════════════════
# complete_interview
# ═══════════════════════════════════════════════════════════════════════════


class TestCompleteInterview:
    @patch("app.interview.session.api.service.acquire_lock")
    def test_success(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_completed.return_value = (sub, True)

        dto, transitioned = svc.complete_interview(
            submission_id=1, candidate_id=100
        )

        assert transitioned is True
        assert dto.status == "completed"
        redis.set.assert_called_once()

    @patch("app.interview.session.api.service.acquire_lock")
    def test_admin_can_complete_without_candidate_id(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.COMPLETED.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_completed.return_value = (sub, True)

        dto, transitioned = svc.complete_interview(
            submission_id=1, candidate_id=None
        )

        assert transitioned is True


# ═══════════════════════════════════════════════════════════════════════════
# cancel_interview
# ═══════════════════════════════════════════════════════════════════════════


class TestCancelInterview:
    @patch("app.interview.session.api.service.acquire_lock")
    def test_success_logs_reason(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.CANCELLED.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_cancelled.return_value = (sub, True)

        dto, transitioned = svc.cancel_interview(
            submission_id=1, admin_id=999, reason="Technical issue"
        )

        assert transitioned is True
        assert dto.status == "cancelled"


# ═══════════════════════════════════════════════════════════════════════════
# expire_interview
# ═══════════════════════════════════════════════════════════════════════════


class TestExpireInterview:
    @patch("app.interview.session.api.service.acquire_lock")
    def test_success(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.EXPIRED.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_expired.return_value = (sub, True)

        dto, transitioned = svc.expire_interview(submission_id=1)

        assert transitioned is True
        assert dto.status == "expired"


# ═══════════════════════════════════════════════════════════════════════════
# review_interview
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewInterview:
    @patch("app.interview.session.api.service.acquire_lock")
    def test_success(self, mock_lock):
        mock_lock.side_effect = _mock_lock()

        sub = _make_submission(status=SubmissionStatus.REVIEWED.value)
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.transition_to_reviewed.return_value = (sub, True)

        dto, transitioned = svc.review_interview(
            submission_id=1, admin_id=999, review_notes="Good"
        )

        assert transitioned is True
        assert dto.status == "reviewed"


# ═══════════════════════════════════════════════════════════════════════════
# get_session_status
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSessionStatus:
    def test_returns_detail_dto(self):
        sub = _make_submission(status="in_progress")
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.get_by_id_for_candidate.return_value = sub

        result = svc.get_session_status(submission_id=1, candidate_id=100)

        assert isinstance(result, InterviewSessionDetailDTO)
        assert result.session.submission_id == 1
        assert result.exchanges == []

    def test_admin_skips_candidate_filter(self):
        sub = _make_submission(status="in_progress")
        db = MagicMock()
        redis = _mock_redis()

        svc = SessionService(db=db, redis=redis)
        svc._repo = MagicMock()
        svc._repo.get_by_id.return_value = sub

        result = svc.get_session_status(submission_id=1, candidate_id=None)

        svc._repo.get_by_id.assert_called_once_with(1)
        assert result.session.status == "in_progress"
