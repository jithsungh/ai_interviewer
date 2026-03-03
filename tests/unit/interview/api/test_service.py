"""
Unit Tests — InterviewApiService

Tests the service layer with a **mocked** InterviewQueryRepository.
Verifies:
  1. list_exchanges delegates correctly to repository
  2. list_exchanges respects candidate_id scoping
  3. list_exchanges filters by section
  4. list_exchanges strips responses when include_responses=False
  5. get_progress returns section-level breakdown
  6. get_progress raises NotFoundError for missing submissions
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.interview.api.contracts import (
    ExchangeListResponse,
    SectionProgressResponse,
)
from app.interview.api.service import InterviewApiService
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_exchange(**overrides):
    defaults = dict(
        id=789,
        interview_submission_id=1,
        sequence_order=1,
        question_id=101,
        coding_problem_id=None,
        question_text="Test question?",
        expected_answer="Expected answer",
        difficulty_at_time="medium",
        response_text="My answer",
        response_code=None,
        response_time_ms=30000,
        ai_followup_message=None,
        content_metadata={"question_type": "text", "section_name": "resume"},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_submission(**overrides):
    defaults = dict(
        id=1,
        candidate_id=100,
        status="in_progress",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_service_with_mock_repo():
    db = MagicMock()
    svc = InterviewApiService(db=db)
    svc._repo = MagicMock()
    return svc, svc._repo


# ═══════════════════════════════════════════════════════════════════════════
# list_exchanges
# ═══════════════════════════════════════════════════════════════════════════


class TestListExchanges:
    def test_returns_exchange_list_admin(self):
        """Admin path: candidate_id=None, access any submission."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_by_id.return_value = _make_submission()
        repo.list_exchanges.return_value = [_make_exchange()]

        result = svc.list_exchanges(submission_id=1)

        assert isinstance(result, ExchangeListResponse)
        assert result.submission_id == 1
        assert result.total_exchanges == 1
        assert result.exchanges[0].exchange_id == 789
        repo.get_submission_by_id.assert_called_once_with(1)

    def test_returns_exchange_list_candidate(self):
        """Candidate path: candidate_id provided, scoped access."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_for_candidate.return_value = _make_submission()
        repo.list_exchanges.return_value = [_make_exchange()]

        result = svc.list_exchanges(submission_id=1, candidate_id=100)

        assert result.total_exchanges == 1
        repo.get_submission_for_candidate.assert_called_once_with(1, 100)

    def test_not_found_propagates(self):
        """NotFoundError from repo propagates to caller."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_by_id.side_effect = NotFoundError(
            resource_type="Submission", resource_id=999
        )

        with pytest.raises(NotFoundError):
            svc.list_exchanges(submission_id=999)

    def test_section_filter_passed(self):
        """Section filter forwarded to repository."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_by_id.return_value = _make_submission()
        repo.list_exchanges.return_value = []

        svc.list_exchanges(submission_id=1, section="coding")

        repo.list_exchanges.assert_called_once_with(
            submission_id=1,
            section="coding",
            include_responses=True,
        )

    def test_include_responses_false(self):
        """When include_responses=False, DTOs strip response data."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_by_id.return_value = _make_submission()
        repo.list_exchanges.return_value = [_make_exchange()]

        result = svc.list_exchanges(submission_id=1, include_responses=False)

        assert result.exchanges[0].response_text is None
        assert result.exchanges[0].response_time_ms is None

    def test_empty_exchanges(self):
        """No exchanges → empty list, total=0."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_by_id.return_value = _make_submission()
        repo.list_exchanges.return_value = []

        result = svc.list_exchanges(submission_id=1)
        assert result.total_exchanges == 0
        assert result.exchanges == []


# ═══════════════════════════════════════════════════════════════════════════
# get_progress
# ═══════════════════════════════════════════════════════════════════════════


class TestGetProgress:
    def test_returns_progress_admin(self):
        """Admin path: no candidate scoping."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_section_progress.return_value = {
            "submission_id": 1,
            "overall_progress": 50.0,
            "sections": [
                {
                    "section_name": "resume",
                    "questions_total": 2,
                    "questions_answered": 2,
                    "progress_percentage": 100.0,
                },
                {
                    "section_name": "coding",
                    "questions_total": 3,
                    "questions_answered": 0,
                    "progress_percentage": 0.0,
                },
            ],
        }

        result = svc.get_progress(submission_id=1)

        assert isinstance(result, SectionProgressResponse)
        assert result.submission_id == 1
        assert result.overall_progress == 50.0
        assert len(result.sections) == 2
        assert result.sections[0].section_name == "resume"
        assert result.sections[0].progress_percentage == 100.0

    def test_returns_progress_candidate(self):
        """Candidate path: validates ownership then returns progress."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_for_candidate.return_value = _make_submission()
        repo.get_section_progress.return_value = {
            "submission_id": 1,
            "overall_progress": 0.0,
            "sections": [],
        }

        result = svc.get_progress(submission_id=1, candidate_id=100)

        repo.get_submission_for_candidate.assert_called_once_with(1, 100)
        assert result.overall_progress == 0.0

    def test_not_found_propagates(self):
        """NotFoundError from repo propagates to caller."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_submission_for_candidate.side_effect = NotFoundError(
            resource_type="Submission", resource_id=999
        )

        with pytest.raises(NotFoundError):
            svc.get_progress(submission_id=999, candidate_id=100)

    def test_empty_sections(self):
        """No template snapshot → empty sections."""
        svc, repo = _make_service_with_mock_repo()
        repo.get_section_progress.return_value = {
            "submission_id": 1,
            "overall_progress": 0.0,
            "sections": [],
        }

        result = svc.get_progress(submission_id=1)
        assert result.sections == []
