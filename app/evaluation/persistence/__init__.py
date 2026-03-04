"""
Evaluation Persistence — Public API

Exports canonical ORM models, repositories, and persistence-specific errors.
"""

from app.evaluation.persistence.errors import (
    DuplicateEvaluationError,
    DuplicateResultError,
    EvaluationNotFoundError,
    InterviewResultNotFoundError,
    PersistenceError,
)
from app.evaluation.persistence.models import (
    EvaluationDimensionScoreModel,
    EvaluationModel,
    InterviewResultModel,
    SupplementaryReportModel,
)
from app.evaluation.persistence.repositories import (
    DimensionScoreRepository,
    EvaluationRepository,
    InterviewResultRepository,
    SupplementaryReportRepository,
)

__all__ = [
    # Models
    "EvaluationModel",
    "EvaluationDimensionScoreModel",
    "InterviewResultModel",
    "SupplementaryReportModel",
    # Repositories
    "EvaluationRepository",
    "DimensionScoreRepository",
    "InterviewResultRepository",
    "SupplementaryReportRepository",
    # Errors
    "PersistenceError",
    "EvaluationNotFoundError",
    "InterviewResultNotFoundError",
    "DuplicateEvaluationError",
    "DuplicateResultError",
]
