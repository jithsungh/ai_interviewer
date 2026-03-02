"""
Evaluation Aggregation Module

Provides interview-level final scoring by aggregating all exchange evaluations
into a single interview result with recommendation.

Public API:
- AggregationService: Main orchestrator for interview aggregation
- aggregate_interview_result: Convenience function for one-shot aggregation
- SectionAggregator: Groups evaluations by template section
- ScoreNormalizer: Normalizes score to 0–100 scale
- RecommendationEngine: Maps normalized score to recommendation
- ProctoringAdjuster: Adjusts recommendation for proctoring risk
- SummaryGenerator: AI-powered summary generation

Usage:
    from app.evaluation.aggregation import AggregationService

    service = AggregationService(db_session, llm_provider=provider)
    result = await service.aggregate_interview_result(
        submission_id=123,
        generated_by="ai",
    )
"""

from app.evaluation.aggregation.config import (
    AggregationConfig,
    get_aggregation_config,
    reset_config,
)
from app.evaluation.aggregation.errors import (
    AggregationAlreadyExistsError,
    AggregationError,
    IncompleteEvaluationError,
    InterviewNotFoundError,
    NoExchangesError,
    SummaryGenerationError,
    TemplateWeightsNotFoundError,
)
from app.evaluation.aggregation.normalizer import ScoreNormalizer, calculate_final_score
from app.evaluation.aggregation.proctoring_adjuster import ProctoringAdjuster
from app.evaluation.aggregation.recommendation import RecommendationEngine
from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    ExchangeSummaryDTO,
    InterviewResultData,
    ProctoringRiskDTO,
    SectionScore,
    SummaryData,
    SummaryResponseSchema,
)
from app.evaluation.aggregation.section_aggregator import SectionAggregator
from app.evaluation.aggregation.service import (
    AggregationService,
    aggregate_interview_result,
)
from app.evaluation.aggregation.summary_generator import SummaryGenerator

__all__ = [
    # Service
    "AggregationService",
    "aggregate_interview_result",
    # Pipeline Components
    "SectionAggregator",
    "ScoreNormalizer",
    "RecommendationEngine",
    "ProctoringAdjuster",
    "SummaryGenerator",
    # Convenience
    "calculate_final_score",
    # Config
    "AggregationConfig",
    "get_aggregation_config",
    "reset_config",
    # Schemas / DTOs
    "SectionScore",
    "SummaryData",
    "SummaryResponseSchema",
    "InterviewResultData",
    "EvaluationSummaryDTO",
    "ExchangeSummaryDTO",
    "ProctoringRiskDTO",
    # Errors
    "AggregationError",
    "IncompleteEvaluationError",
    "InterviewNotFoundError",
    "AggregationAlreadyExistsError",
    "TemplateWeightsNotFoundError",
    "SummaryGenerationError",
    "NoExchangesError",
]
