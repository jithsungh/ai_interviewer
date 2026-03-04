"""
Unit Tests — Evaluation API Dependencies

Tests factory functions that build repositories from a DB session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.evaluation.api.dependencies import (
    build_dimension_score_repository,
    build_evaluation_repository,
    build_report_repository,
    build_result_repository,
)
from app.evaluation.persistence.repositories import (
    DimensionScoreRepository,
    EvaluationRepository,
    InterviewResultRepository,
    SupplementaryReportRepository,
)


# ═══════════════════════════════════════════════════════════════════════════
# Dependency Factory Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDependencyFactories:
    def setup_method(self):
        self.session = MagicMock(spec=Session)

    def test_build_evaluation_repository(self):
        """Should return EvaluationRepository with session."""
        repo = build_evaluation_repository(self.session)
        assert isinstance(repo, EvaluationRepository)

    def test_build_dimension_score_repository(self):
        """Should return DimensionScoreRepository with session."""
        repo = build_dimension_score_repository(self.session)
        assert isinstance(repo, DimensionScoreRepository)

    def test_build_result_repository(self):
        """Should return InterviewResultRepository with session."""
        repo = build_result_repository(self.session)
        assert isinstance(repo, InterviewResultRepository)

    def test_build_report_repository(self):
        """Should return SupplementaryReportRepository with session."""
        repo = build_report_repository(self.session)
        assert isinstance(repo, SupplementaryReportRepository)
