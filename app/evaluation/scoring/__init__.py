"""
Evaluation Scoring Module

Provides deterministic scoring engine for interview exchanges.

Public API:
- ScoringService: Main orchestrator for exchange scoring
- resolve_rubric: Rubric resolution for exchanges
- score_with_ai: AI-based dimension scoring
- score_with_human: Human manual scoring validation
- calculate_total_score: Weighted total calculation

Usage:
    from app.evaluation.scoring import ScoringService, EvaluatorType
    
    service = ScoringService(db_session, llm_provider, prompt_service)
    result = await service.score_exchange(
        interview_exchange_id=123,
        evaluator_type=EvaluatorType.AI
    )
"""

from app.evaluation.scoring.contracts import (
    RubricDimensionDTO,
    DimensionScoreResult,
    AIScoreResult,
    HumanDimensionScore,
    HumanScoreInput,
    ExchangeDataDTO,
    ScoringResultDTO,
)
from app.evaluation.scoring.errors import (
    ScoringError,
    ExchangeNotFoundError,
    RubricNotFoundError,
    InvalidRubricError,
    AIEvaluationError,
    InvalidScoreError,
    MissingDimensionError,
    ScoreValidationError,
    EvaluationExistsError,
)
from app.evaluation.scoring.service import ScoringService, EvaluatorType

__all__ = [
    # Service
    "ScoringService",
    "EvaluatorType",
    # Contracts
    "RubricDimensionDTO",
    "DimensionScoreResult",
    "AIScoreResult",
    "HumanDimensionScore",
    "HumanScoreInput",
    "ExchangeDataDTO",
    "ScoringResultDTO",
    # Errors
    "ScoringError",
    "ExchangeNotFoundError",
    "RubricNotFoundError",
    "InvalidRubricError",
    "AIEvaluationError",
    "InvalidScoreError",
    "MissingDimensionError",
    "ScoreValidationError",
    "EvaluationExistsError",
]
