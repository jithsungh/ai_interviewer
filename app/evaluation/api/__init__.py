"""
Evaluation API — Public API

Exports the FastAPI router and request/response contracts.
"""

from app.evaluation.api.contracts import (
    DimensionScoreOverride,
    DimensionScoreResponse,
    EvaluateExchangeRequest,
    EvaluationOverrideResponse,
    EvaluationResponse,
    ExchangeEvaluationsResponse,
    FinalizeInterviewRequest,
    HumanOverrideRequest,
    InterviewResultResponse,
    SubmissionReportsResponse,
    SubmissionResultsResponse,
    SupplementaryReportResponse,
)
from app.evaluation.api.routes import router

__all__ = [
    "router",
    # Request models
    "EvaluateExchangeRequest",
    "HumanOverrideRequest",
    "FinalizeInterviewRequest",
    "DimensionScoreOverride",
    # Response models
    "EvaluationResponse",
    "EvaluationOverrideResponse",
    "InterviewResultResponse",
    "DimensionScoreResponse",
    "ExchangeEvaluationsResponse",
    "SubmissionResultsResponse",
    "SubmissionReportsResponse",
    "SupplementaryReportResponse",
]
