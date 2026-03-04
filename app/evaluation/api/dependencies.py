"""
Evaluation API — Dependency Injection

Factory functions for constructing evaluation services with their
required repository dependencies.  Follows the pattern established
by ``app/admin/api/dependencies.py``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.evaluation.persistence.repositories import (
    DimensionScoreRepository,
    EvaluationRepository,
    InterviewResultRepository,
    SupplementaryReportRepository,
)


def build_evaluation_repository(session: Session) -> EvaluationRepository:
    """Create an EvaluationRepository bound to the given DB session."""
    return EvaluationRepository(session)


def build_dimension_score_repository(
    session: Session,
) -> DimensionScoreRepository:
    """Create a DimensionScoreRepository bound to the given DB session."""
    return DimensionScoreRepository(session)


def build_result_repository(session: Session) -> InterviewResultRepository:
    """Create an InterviewResultRepository bound to the given DB session."""
    return InterviewResultRepository(session)


def build_report_repository(
    session: Session,
) -> SupplementaryReportRepository:
    """Create a SupplementaryReportRepository bound to the given DB session."""
    return SupplementaryReportRepository(session)
