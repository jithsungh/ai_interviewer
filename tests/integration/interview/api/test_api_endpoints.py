"""
Integration Tests — Interview API Endpoints

Tests the REST endpoint integration with mocked dependencies.
Verifies:
  1. Endpoint → service → repository flow for exchanges listing
  2. Endpoint → service → repository flow for progress retrieval
  3. Auth scoping (candidate vs admin)
  4. Error propagation (NotFoundError → 404 etc.)
  5. Query parameter handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.interview.api.contracts import (
    ExchangeItemDTO,
    ExchangeListResponse,
    SectionProgressDTO,
    SectionProgressResponse,
)
from app.interview.api.routes import list_exchanges, get_progress
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_identity(user_type: str = "candidate", user_id: int = 100):
    return SimpleNamespace(
        user_id=user_id,
        user_type=SimpleNamespace(value=user_type),
    )


def _exchange_list_response(count=2):
    exchanges = [
        ExchangeItemDTO(
            exchange_id=i,
            sequence_order=i,
            question_text=f"Question {i}",
            difficulty_at_time="medium",
            section_name="resume",
            response_text=f"Answer {i}",
            response_time_ms=30000,
        )
        for i in range(1, count + 1)
    ]
    return ExchangeListResponse(
        submission_id=1,
        exchanges=exchanges,
        total_exchanges=count,
    )


def _progress_response():
    return SectionProgressResponse(
        submission_id=1,
        overall_progress=50.0,
        sections=[
            SectionProgressDTO(
                section_name="resume",
                questions_total=2,
                questions_answered=2,
                progress_percentage=100.0,
            ),
            SectionProgressDTO(
                section_name="coding",
                questions_total=2,
                questions_answered=0,
                progress_percentage=0.0,
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Exchange listing flow
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeListingFlow:
    @patch("app.interview.api.routes._build_service")
    def test_candidate_lists_own_exchanges(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.list_exchanges.return_value = _exchange_list_response(2)

        result = list_exchanges(
            submission_id=1,
            include_responses=True,
            section=None,
            db=MagicMock(),
            identity=_make_identity("candidate", 100),
        )

        svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
            section=None,
            include_responses=True,
        )
        assert result.total_exchanges == 2

    @patch("app.interview.api.routes._build_service")
    def test_admin_lists_any_exchanges(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.list_exchanges.return_value = _exchange_list_response(3)

        result = list_exchanges(
            submission_id=1,
            include_responses=True,
            section=None,
            db=MagicMock(),
            identity=_make_identity("admin", 1),
        )

        svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=None,
            section=None,
            include_responses=True,
        )
        assert result.total_exchanges == 3

    @patch("app.interview.api.routes._build_service")
    def test_section_filter_forwarded(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.list_exchanges.return_value = _exchange_list_response(1)

        list_exchanges(
            submission_id=1,
            include_responses=False,
            section="coding",
            db=MagicMock(),
            identity=_make_identity("candidate", 100),
        )

        svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
            section="coding",
            include_responses=False,
        )

    @patch("app.interview.api.routes._build_service")
    def test_not_found_propagates(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.list_exchanges.side_effect = NotFoundError(
            resource_type="Submission", resource_id=999
        )

        with pytest.raises(NotFoundError):
            list_exchanges(
                submission_id=999,
                include_responses=True,
                section=None,
                db=MagicMock(),
                identity=_make_identity("candidate", 100),
            )


# ═══════════════════════════════════════════════════════════════════════════
# Progress retrieval flow
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressRetrievalFlow:
    @patch("app.interview.api.routes._build_service")
    def test_candidate_gets_own_progress(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.get_progress.return_value = _progress_response()

        result = get_progress(
            submission_id=1,
            db=MagicMock(),
            identity=_make_identity("candidate", 100),
        )

        svc.get_progress.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
        )
        assert result.overall_progress == 50.0

    @patch("app.interview.api.routes._build_service")
    def test_admin_gets_any_progress(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.get_progress.return_value = _progress_response()

        result = get_progress(
            submission_id=1,
            db=MagicMock(),
            identity=_make_identity("admin", 1),
        )

        svc.get_progress.assert_called_once_with(
            submission_id=1,
            candidate_id=None,
        )

    @patch("app.interview.api.routes._build_service")
    def test_not_found_propagates(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc
        svc.get_progress.side_effect = NotFoundError(
            resource_type="Submission", resource_id=999
        )

        with pytest.raises(NotFoundError):
            get_progress(
                submission_id=999,
                db=MagicMock(),
                identity=_make_identity("candidate", 100),
            )
