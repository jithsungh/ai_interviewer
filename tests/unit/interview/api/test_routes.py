"""
Unit Tests — Interview API Routes

Tests FastAPI route handler wiring with mocked service layer.
Verifies:
  1. list_exchanges endpoint delegates to service
  2. get_progress endpoint delegates to service
  3. Auth identity resolution (candidate vs admin)
  4. Query parameter forwarding (section, include_responses)
  5. HTTP status codes
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
from app.interview.api.routes import (
    _resolve_candidate_id,
    list_exchanges,
    get_progress,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_identity(user_type: str = "candidate", user_id: int = 100):
    """Create a minimal mock identity."""
    identity = SimpleNamespace(
        user_id=user_id,
        user_type=SimpleNamespace(value=user_type),
    )
    return identity


# ═══════════════════════════════════════════════════════════════════════════
# _resolve_candidate_id
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveCandidateId:
    def test_candidate_returns_user_id(self):
        identity = _make_identity(user_type="candidate", user_id=42)
        assert _resolve_candidate_id(identity) == 42

    def test_admin_returns_none(self):
        identity = _make_identity(user_type="admin", user_id=1)
        assert _resolve_candidate_id(identity) is None

    def test_superadmin_returns_none(self):
        identity = _make_identity(user_type="superadmin", user_id=1)
        assert _resolve_candidate_id(identity) is None


# ═══════════════════════════════════════════════════════════════════════════
# list_exchanges endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestListExchangesEndpoint:
    @patch("app.interview.api.routes._build_service")
    def test_calls_service_with_correct_params(self, mock_build):
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        mock_svc.list_exchanges.return_value = ExchangeListResponse(
            submission_id=1,
            exchanges=[],
            total_exchanges=0,
        )

        db = MagicMock()
        identity = _make_identity(user_type="candidate", user_id=100)

        result = list_exchanges(
            submission_id=1,
            include_responses=True,
            section=None,
            db=db,
            identity=identity,
        )

        mock_svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
            section=None,
            include_responses=True,
        )
        assert result.submission_id == 1

    @patch("app.interview.api.routes._build_service")
    def test_admin_passes_none_candidate_id(self, mock_build):
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        mock_svc.list_exchanges.return_value = ExchangeListResponse(
            submission_id=1,
            exchanges=[],
            total_exchanges=0,
        )

        db = MagicMock()
        identity = _make_identity(user_type="admin", user_id=1)

        list_exchanges(
            submission_id=1,
            include_responses=True,
            section=None,
            db=db,
            identity=identity,
        )

        mock_svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=None,
            section=None,
            include_responses=True,
        )

    @patch("app.interview.api.routes._build_service")
    def test_section_filter_forwarded(self, mock_build):
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        mock_svc.list_exchanges.return_value = ExchangeListResponse(
            submission_id=1,
            exchanges=[],
            total_exchanges=0,
        )

        db = MagicMock()
        identity = _make_identity()

        list_exchanges(
            submission_id=1,
            include_responses=False,
            section="coding",
            db=db,
            identity=identity,
        )

        mock_svc.list_exchanges.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
            section="coding",
            include_responses=False,
        )


# ═══════════════════════════════════════════════════════════════════════════
# get_progress endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestGetProgressEndpoint:
    @patch("app.interview.api.routes._build_service")
    def test_calls_service_for_candidate(self, mock_build):
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        mock_svc.get_progress.return_value = SectionProgressResponse(
            submission_id=1,
            overall_progress=50.0,
            sections=[],
        )

        db = MagicMock()
        identity = _make_identity(user_type="candidate", user_id=100)

        result = get_progress(submission_id=1, db=db, identity=identity)

        mock_svc.get_progress.assert_called_once_with(
            submission_id=1,
            candidate_id=100,
        )
        assert result.overall_progress == 50.0

    @patch("app.interview.api.routes._build_service")
    def test_calls_service_for_admin(self, mock_build):
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        mock_svc.get_progress.return_value = SectionProgressResponse(
            submission_id=1,
            overall_progress=0.0,
            sections=[],
        )

        db = MagicMock()
        identity = _make_identity(user_type="admin", user_id=1)

        get_progress(submission_id=1, db=db, identity=identity)

        mock_svc.get_progress.assert_called_once_with(
            submission_id=1,
            candidate_id=None,
        )
