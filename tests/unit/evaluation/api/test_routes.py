"""
Unit Tests — Evaluation API Routes

Tests route functions with mocked services and repositories.
Follows the pattern from tests/unit/interview/api/test_routes.py —
direct function calls with mocked dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.evaluation.api.contracts import (
    DimensionScoreOverride,
    EvaluateExchangeRequest,
    EvaluationResponse,
    FinalizeInterviewRequest,
    HumanOverrideRequest,
    InterviewResultResponse,
)
from app.evaluation.api.routes import (
    _recalculate_total,
)
from app.evaluation.persistence.errors import (
    EvaluationNotFoundError,
)
from app.evaluation.persistence.models import EvaluationModel
from app.shared.errors import ValidationError


NOW = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# Helper — make mock identity
# ═══════════════════════════════════════════════════════════════════════════


def _make_admin_identity():
    """Create a mock admin IdentityContext."""
    identity = Mock()
    identity.user_id = 1
    identity.user_type = Mock()
    identity.user_type.value = "admin"
    identity.organization_id = 1
    identity.admin_role = "super_admin"
    return identity


def _make_candidate_identity(user_id: int = 10):
    """Create a mock candidate IdentityContext."""
    identity = Mock()
    identity.user_id = user_id
    identity.user_type = Mock()
    identity.user_type.value = "candidate"
    identity.organization_id = None
    identity.admin_role = None
    return identity


# ═══════════════════════════════════════════════════════════════════════════
# _recalculate_total Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRecalculateTotal:
    def test_empty_scores_returns_zero(self):
        """Empty scores list should return 0."""
        db = MagicMock(spec=Session)
        result = _recalculate_total(db, rubric_id=1, scores_data=[])
        assert result == Decimal("0")

    def test_simple_average_without_rubric(self):
        """When rubric_id is None, fallback to simple weighted calculation."""
        db = MagicMock(spec=Session)
        scores_data = [
            {"rubric_dimension_id": 1, "score": Decimal("4"), "max_score": Decimal("5")},
            {"rubric_dimension_id": 2, "score": Decimal("3"), "max_score": Decimal("5")},
        ]
        result = _recalculate_total(db, rubric_id=None, scores_data=scores_data)
        # (4/5*100 * 1 + 3/5*100 * 1) / 2 = (80 + 60) / 2 = 70
        assert result == Decimal("70.00")

    def test_weighted_calculation_with_rubric(self):
        """With rubric weights, should compute weighted normalized score."""
        db = MagicMock(spec=Session)

        # Mock rubric dimension weights
        weight_row_1 = Mock(id=1, weight=0.6)
        weight_row_2 = Mock(id=2, weight=0.4)
        db.execute.return_value.fetchall.return_value = [weight_row_1, weight_row_2]

        scores_data = [
            {"rubric_dimension_id": 1, "score": Decimal("5"), "max_score": Decimal("5")},
            {"rubric_dimension_id": 2, "score": Decimal("3"), "max_score": Decimal("5")},
        ]
        result = _recalculate_total(db, rubric_id=1, scores_data=scores_data)
        # (5/5*100 * 0.6 + 3/5*100 * 0.4) / (0.6 + 0.4) = (60.0 + 24.0) / 1.0 = 84.0
        assert result == Decimal("84.00")


# ═══════════════════════════════════════════════════════════════════════════
# GET /evaluations/{evaluation_id} Authorization Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGetEvaluationAuthorization:
    """Tests for _authorize_evaluation_access helper."""

    def test_admin_always_allowed(self):
        """Admin identity should always pass authorization."""
        from app.evaluation.api.routes import _authorize_evaluation_access

        db = MagicMock(spec=Session)
        identity = _make_admin_identity()
        mock_eval = Mock(spec=EvaluationModel, interview_exchange_id=1)

        # Should not raise
        _authorize_evaluation_access(db, identity, mock_eval)

    def test_candidate_own_interview_allowed(self):
        """Candidate should access evaluation of their own interview."""
        from app.evaluation.api.routes import _authorize_evaluation_access
        from app.shared.errors import AuthorizationError

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity(user_id=10)
        mock_eval = Mock(spec=EvaluationModel, interview_exchange_id=1)

        # Mock: the exchange belongs to a submission where candidate_id=10
        row = Mock(candidate_id=10)
        db.execute.return_value.first.return_value = row

        # Should not raise
        _authorize_evaluation_access(db, identity, mock_eval)

    def test_candidate_other_interview_blocked(self):
        """Candidate should NOT access evaluation of another's interview."""
        from app.evaluation.api.routes import _authorize_evaluation_access
        from app.shared.errors import NotFoundError

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity(user_id=10)
        mock_eval = Mock(spec=EvaluationModel, interview_exchange_id=1, id=123)

        row = Mock(candidate_id=99)  # Different candidate
        db.execute.return_value.first.return_value = row

        with pytest.raises(NotFoundError):
            _authorize_evaluation_access(db, identity, mock_eval)


# ═══════════════════════════════════════════════════════════════════════════
# Authorization Helpers Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthorizeExchangeAccess:
    """Tests for _authorize_exchange_access."""

    def test_admin_allowed(self):
        """Admin passes without DB check."""
        from app.evaluation.api.routes import _authorize_exchange_access

        db = MagicMock(spec=Session)
        identity = _make_admin_identity()

        # Should not raise and not call DB
        _authorize_exchange_access(db, identity, exchange_id=1)
        db.execute.assert_not_called()

    def test_candidate_exchange_not_found(self):
        """Should raise NotFoundError if exchange doesn't exist."""
        from app.evaluation.api.routes import _authorize_exchange_access
        from app.shared.errors import NotFoundError

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity()
        db.execute.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            _authorize_exchange_access(db, identity, exchange_id=999)


class TestAuthorizeSubmissionAccess:
    """Tests for _authorize_submission_access."""

    def test_admin_allowed(self):
        """Admin passes without DB check."""
        from app.evaluation.api.routes import _authorize_submission_access

        db = MagicMock(spec=Session)
        identity = _make_admin_identity()

        _authorize_submission_access(db, identity, submission_id=1)
        db.execute.assert_not_called()

    def test_candidate_own_submission_allowed(self):
        """Candidate should access own submission."""
        from app.evaluation.api.routes import _authorize_submission_access

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity(user_id=10)
        row = Mock(candidate_id=10)
        db.execute.return_value.first.return_value = row

        # Should not raise
        _authorize_submission_access(db, identity, submission_id=1)

    def test_candidate_other_submission_blocked(self):
        """Candidate should NOT access another's submission."""
        from app.evaluation.api.routes import _authorize_submission_access
        from app.shared.errors import NotFoundError

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity(user_id=10)
        row = Mock(candidate_id=99)
        db.execute.return_value.first.return_value = row

        with pytest.raises(NotFoundError):
            _authorize_submission_access(db, identity, submission_id=1)

    def test_submission_not_found(self):
        """Should raise NotFoundError if submission doesn't exist."""
        from app.evaluation.api.routes import _authorize_submission_access
        from app.shared.errors import NotFoundError

        db = MagicMock(spec=Session)
        identity = _make_candidate_identity()
        db.execute.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            _authorize_submission_access(db, identity, submission_id=999)
