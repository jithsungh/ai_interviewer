"""
Scoring Service

Orchestrates the complete evaluation pipeline:
1. Resolve rubric for exchange
2. Fetch exchange data
3. Score with AI or validate human scores
4. Calculate total score
5. Persist evaluation and dimension scores
6. Return results

Design:
- Single entry point for all scoring operations
- Coordinates rubric_resolver, ai_scorer, human_scorer, score_calculator
- Handles persistence transactions
- Enforces "one exchange = one final evaluation" invariant
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.evaluation.persistence.models import (
    EvaluationModel as Evaluation,
    EvaluationDimensionScoreModel as EvaluationDimensionScore,
)
from app.evaluation.scoring.ai_scorer import AIScorer
from app.evaluation.scoring.config import ScoringConfig, get_scoring_config
from app.evaluation.scoring.contracts import (
    AIScoreResult,
    DimensionScoreResult,
    ExchangeDataDTO,
    HumanScoreInput,
    RubricDimensionDTO,
    ScoringResultDTO,
)
from app.evaluation.scoring.errors import (
    EvaluationExistsError,
    ExchangeNotFoundError,
    InvalidRubricError,
    ScoringError,
)
from app.evaluation.scoring.human_scorer import (
    HumanScorer,
    validate_dimension_scores_against_rubric,
)
from app.evaluation.scoring.rubric_resolver import RubricResolver
from app.evaluation.scoring.score_calculator import ScoreCalculator
from app.shared.observability import get_context_logger

if TYPE_CHECKING:
    from app.ai.llm import BaseLLMProvider

logger = get_context_logger(__name__)


class EvaluatorType(str, Enum):
    """Evaluation method type."""
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


# -----------------------------------------------------------------------------
# SQLAlchemy ORM Models (for persistence)
#
# These models map to existing database tables per schema.sql.
# Inline models migrated to app.evaluation.persistence.models (DEV-49).
# Imported above as Evaluation / EvaluationDimensionScore for compatibility.
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Scoring Service
# -----------------------------------------------------------------------------

class ScoringService:
    """
    Main orchestrator for evaluation scoring.
    
    Handles the complete scoring pipeline from rubric resolution 
    through persistence.
    """
    
    SCORING_VERSION = "1.0.0"
    
    def __init__(
        self,
        db: Session,
        config: Optional[ScoringConfig] = None,
        llm_provider: Optional["BaseLLMProvider"] = None
    ):
        """
        Initialize scoring service.
        
        Args:
            db: Database session for persistence.
            config: Scoring configuration (uses defaults if None).
            llm_provider: LLM provider for AI scoring.
        """
        self._db = db
        self._config = config or get_scoring_config()
        
        # Get default provider if none provided
        if llm_provider is None:
            from app.ai.llm import get_default_provider
            llm_provider = get_default_provider()
        
        # Initialize component scorers
        self._rubric_resolver = RubricResolver(db)
        self._ai_scorer = AIScorer(
            llm_provider=llm_provider,
            config=self._config
        )
        self._human_scorer = HumanScorer(config=self._config)
        self._score_calculator = ScoreCalculator(config=self._config)
    
    async def score_exchange(
        self,
        interview_exchange_id: int,
        evaluator_type: EvaluatorType,
        human_scores: Optional[HumanScoreInput] = None,
        evaluated_by: Optional[int] = None,
        force_rescore: bool = False
    ) -> ScoringResultDTO:
        """
        Complete scoring pipeline for an interview exchange.
        
        Steps:
        1. Validate exchange exists and check for existing evaluation
        2. Resolve rubric and dimensions for exchange
        3. Fetch exchange data (question, answer, transcript)
        4. Score with AI or validate human scores
        5. Calculate weighted total score
        6. Persist evaluation and dimension scores
        7. Return results
        
        Args:
            interview_exchange_id: Exchange to score.
            evaluator_type: AI, HUMAN, or HYBRID evaluation.
            human_scores: Required for HUMAN/HYBRID evaluator types.
            evaluated_by: User ID of human evaluator (for HUMAN type).
            force_rescore: If True, mark existing evaluation as non-final.
        
        Returns:
            ScoringResultDTO with evaluation details.
        
        Raises:
            ExchangeNotFoundError: Exchange doesn't exist.
            EvaluationExistsError: Final evaluation already exists.
            RubricNotFoundError: No rubric linked to template.
            InvalidRubricError: Rubric has no dimensions.
            AIEvaluationError: AI scoring failed.
            InvalidScoreError: Score validation failed.
        """
        logger.info(
            "Starting scoring pipeline",
            extra={
                "exchange_id": interview_exchange_id,
                "evaluator_type": evaluator_type.value
            }
        )
        
        # Step 1: Check for existing evaluation
        await self._check_existing_evaluation(
            interview_exchange_id, 
            force_rescore
        )
        
        # Step 2: Resolve rubric
        rubric_id, dimensions = self._rubric_resolver.resolve_rubric(
            interview_exchange_id
        )
        
        if not dimensions:
            raise InvalidRubricError(rubric_id=rubric_id, reason="No dimensions found")
        
        # Step 3: Fetch exchange data
        exchange_data = self._fetch_exchange_data(interview_exchange_id)

        logger.info(
            "Scoring exchange context prepared",
            extra={
                "exchange_id": interview_exchange_id,
                "question_type": exchange_data.question_type,
                "question_length": len(exchange_data.question_content or ""),
                "answer_length": len(exchange_data.answer_content or ""),
                "transcript_length": len(exchange_data.transcript or ""),
                "dimensions_count": len(dimensions),
            },
        )
        
        # Step 4: Score based on evaluator type
        score_result = await self._perform_scoring(
            evaluator_type=evaluator_type,
            exchange_data=exchange_data,
            dimensions=dimensions,
            human_scores=human_scores
        )
        
        # Step 5: Validate and calculate total score
        validate_dimension_scores_against_rubric(
            score_result.dimension_scores,
            dimensions
        )
        
        total_score = self._score_calculator.calculate_total_score(
            score_result.dimension_scores,
            dimensions
        )
        
        # Step 6: Persist evaluation
        evaluation = self._persist_evaluation(
            interview_exchange_id=interview_exchange_id,
            rubric_id=rubric_id,
            evaluator_type=evaluator_type,
            total_score=total_score,
            score_result=score_result,
            dimensions=dimensions,
            evaluated_by=evaluated_by
        )
        
        logger.info(
            "Scoring complete",
            extra={
                "evaluation_id": evaluation.id,
                "total_score": str(total_score),
                "dimension_count": len(score_result.dimension_scores)
            }
        )
        
        return ScoringResultDTO(
            evaluation_id=evaluation.id,
            interview_exchange_id=interview_exchange_id,
            rubric_id=rubric_id,
            evaluator_type=evaluator_type.value,
            total_score=total_score,
            dimension_scores=score_result.dimension_scores,
            overall_comment=score_result.overall_comment,
            model_id=score_result.model_id,
            scoring_version=self.SCORING_VERSION,
            evaluated_at=evaluation.evaluated_at
        )
    
    async def _check_existing_evaluation(
        self,
        interview_exchange_id: int,
        force_rescore: bool
    ) -> None:
        """Check for existing final evaluation."""
        existing = self._db.query(Evaluation).filter(
            and_(
                Evaluation.interview_exchange_id == interview_exchange_id,
                Evaluation.is_final == True
            )
        ).first()
        
        if existing:
            if force_rescore:
                # Mark existing as non-final
                existing.is_final = False
                self._db.flush()
                logger.info(
                    "Marked existing evaluation as non-final",
                    extra={"evaluation_id": existing.id}
                )
            else:
                raise EvaluationExistsError(
                    exchange_id=interview_exchange_id,
                    existing_evaluation_id=existing.id
                )
    
    def _fetch_exchange_data(self, exchange_id: int) -> ExchangeDataDTO:
        """Fetch exchange question, answer, and transcript."""
        # Query exchange with question and answer
        from sqlalchemy import text
        
        query = text("""
            SELECT 
                ie.id AS exchange_id,
                ie.question_text AS question_content,
                COALESCE(
                    ie.content_metadata->>'question_type',
                    CASE
                        WHEN ie.coding_problem_id IS NOT NULL THEN 'coding'
                        ELSE 'technical'
                    END
                ) AS question_type,
                COALESCE(NULLIF(ie.response_text, ''), NULLIF(ie.response_code, ''), '') AS answer_content,
                aa.transcript AS audio_transcript
            FROM interview_exchanges ie
            LEFT JOIN audio_analytics aa
                ON aa.interview_exchange_id = ie.id
            WHERE ie.id = :exchange_id
        """)
        
        result = self._db.execute(query, {"exchange_id": exchange_id}).first()
        
        if not result:
            raise ExchangeNotFoundError(exchange_id=exchange_id)
        
        exchange_data = ExchangeDataDTO(
            exchange_id=result.exchange_id,
            question_content=result.question_content or "",
            question_type=result.question_type,
            answer_content=(result.answer_content or "").strip() or (result.audio_transcript or "").strip(),
            transcript=result.audio_transcript
        )

        if len(exchange_data.answer_content.strip()) < 30:
            logger.warning(
                "Exchange answer content is very short; score may be near zero",
                extra={
                    "exchange_id": exchange_id,
                    "answer_length": len(exchange_data.answer_content),
                    "answer_preview": exchange_data.answer_content[:120],
                },
            )

        return exchange_data
    
    async def _perform_scoring(
        self,
        evaluator_type: EvaluatorType,
        exchange_data: ExchangeDataDTO,
        dimensions: List[RubricDimensionDTO],
        human_scores: Optional[HumanScoreInput]
    ) -> AIScoreResult:
        """Perform scoring based on evaluator type."""
        if evaluator_type == EvaluatorType.AI:
            return await self._ai_scorer.score(
                question_content=exchange_data.question_content,
                answer_content=exchange_data.answer_content,
                transcript=exchange_data.transcript,
                dimensions=dimensions
            )
        
        elif evaluator_type == EvaluatorType.HUMAN:
            if human_scores is None:
                raise ValueError("human_scores required for HUMAN evaluation")
            
            return self._human_scorer.validate_and_format(
                human_input=human_scores,
                dimensions=dimensions
            )
        
        elif evaluator_type == EvaluatorType.HYBRID:
            # Hybrid: Start with AI, then apply human overrides
            if human_scores is None:
                raise ValueError("human_scores required for HYBRID evaluation")
            
            # Get AI scores first
            ai_result = await self._ai_scorer.score(
                question_content=exchange_data.question_content,
                answer_content=exchange_data.answer_content,
                transcript=exchange_data.transcript,
                dimensions=dimensions
            )
            
            # Validate and apply human overrides
            human_result = self._human_scorer.validate_and_format(
                human_input=human_scores,
                dimensions=dimensions
            )
            
            # Merge: human scores take precedence
            merged_scores = self._merge_scores(
                ai_scores=ai_result.dimension_scores,
                human_scores=human_result.dimension_scores
            )
            
            return AIScoreResult(
                dimension_scores=merged_scores,
                overall_comment=human_result.overall_comment or ai_result.overall_comment,
                model_id=ai_result.model_id
            )
        
        raise ValueError(f"Unknown evaluator type: {evaluator_type}")
    
    def _merge_scores(
        self,
        ai_scores: List[DimensionScoreResult],
        human_scores: List[DimensionScoreResult]
    ) -> List[DimensionScoreResult]:
        """Merge AI and human scores (human takes precedence)."""
        ai_lookup = {s.dimension_name.lower(): s for s in ai_scores}
        
        merged = []
        for human_score in human_scores:
            # Human score takes precedence
            merged.append(human_score)
        
        return merged
    
    def _persist_evaluation(
        self,
        interview_exchange_id: int,
        rubric_id: int,
        evaluator_type: EvaluatorType,
        total_score: Decimal,
        score_result: AIScoreResult,
        dimensions: List[RubricDimensionDTO],
        evaluated_by: Optional[int]
    ) -> Evaluation:
        """Persist evaluation and dimension scores."""
        # Build dimension lookup by name
        dim_lookup = {d.dimension_name.lower(): d for d in dimensions}
        
        # Create evaluation
        evaluation = Evaluation(
            interview_exchange_id=interview_exchange_id,
            rubric_id=rubric_id,
            evaluator_type=evaluator_type.value,
            total_score=total_score,
            explanation=score_result.overall_comment,
            is_final=True,
            evaluated_by=evaluated_by,
            model_id=None,
            scoring_version=self.SCORING_VERSION
        )
        
        self._db.add(evaluation)
        
        try:
            self._db.flush()  # Get evaluation.id
        except IntegrityError as e:
            self._db.rollback()
            raise EvaluationExistsError(
                exchange_id=interview_exchange_id,
                existing_evaluation_id=None
            ) from e
        
        # Create dimension scores
        for score_data in score_result.dimension_scores:
            dim_key = score_data.dimension_name.lower()
            dimension = dim_lookup.get(dim_key)
            
            if dimension:
                dim_score = EvaluationDimensionScore(
                    evaluation_id=evaluation.id,
                    rubric_dimension_id=dimension.rubric_dimension_id,
                    score=score_data.score,
                    max_score=dimension.max_score,
                    justification=score_data.justification
                )
                self._db.add(dim_score)
        
        self._db.commit()
        self._db.refresh(evaluation)
        
        return evaluation
    
    def get_evaluation(self, evaluation_id: int) -> Optional[ScoringResultDTO]:
        """
        Fetch existing evaluation by ID.
        
        Args:
            evaluation_id: Evaluation to fetch.
        
        Returns:
            ScoringResultDTO or None if not found.
        """
        evaluation = self._db.query(Evaluation).filter(
            Evaluation.id == evaluation_id
        ).first()
        
        if not evaluation:
            return None
        
        # Fetch dimension scores
        dim_scores = self._db.query(EvaluationDimensionScore).filter(
            EvaluationDimensionScore.evaluation_id == evaluation_id
        ).all()
        
        # Convert to DTOs
        dimension_scores = [
            DimensionScoreResult(
                dimension_name=self._get_dimension_name(ds.rubric_dimension_id),
                score=float(ds.score),
                justification=ds.justification or ""
            )
            for ds in dim_scores
        ]
        
        return ScoringResultDTO(
            evaluation_id=evaluation.id,
            interview_exchange_id=evaluation.interview_exchange_id,
            rubric_id=evaluation.rubric_id,
            evaluator_type=evaluation.evaluator_type,
            total_score=evaluation.total_score,
            dimension_scores=dimension_scores,
            overall_comment=evaluation.explanation,
            model_id=evaluation.model_id,
            scoring_version=evaluation.scoring_version,
            evaluated_at=evaluation.evaluated_at
        )
    
    def _get_dimension_name(self, rubric_dimension_id: int) -> str:
        """Get dimension name from ID."""
        from sqlalchemy import text
        
        result = self._db.execute(
            text("SELECT dimension_name FROM rubric_dimensions WHERE id = :id"),
            {"id": rubric_dimension_id}
        ).first()
        
        return result.dimension_name if result else f"Dimension {rubric_dimension_id}"
    
    def get_evaluation_for_exchange(
        self,
        interview_exchange_id: int,
        is_final: bool = True
    ) -> Optional[ScoringResultDTO]:
        """
        Fetch evaluation for an exchange.
        
        Args:
            interview_exchange_id: Exchange to look up.
            is_final: Filter by is_final flag.
        
        Returns:
            ScoringResultDTO or None if not found.
        """
        evaluation = self._db.query(Evaluation).filter(
            and_(
                Evaluation.interview_exchange_id == interview_exchange_id,
                Evaluation.is_final == is_final
            )
        ).first()
        
        if not evaluation:
            return None
        
        return self.get_evaluation(evaluation.id)


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------

async def score_exchange(
    db: Session,
    interview_exchange_id: int,
    evaluator_type: EvaluatorType,
    human_scores: Optional[HumanScoreInput] = None,
    evaluated_by: Optional[int] = None,
    force_rescore: bool = False
) -> ScoringResultDTO:
    """
    Score an interview exchange.
    
    Convenience function wrapping ScoringService.
    
    Args:
        db: Database session.
        interview_exchange_id: Exchange to score.
        evaluator_type: AI, HUMAN, or HYBRID.
        human_scores: Required for HUMAN/HYBRID types.
        evaluated_by: Human evaluator user ID.
        force_rescore: Allow re-scoring existing evaluation.
    
    Returns:
        ScoringResultDTO with evaluation details.
    """
    service = ScoringService(db)
    return await service.score_exchange(
        interview_exchange_id=interview_exchange_id,
        evaluator_type=evaluator_type,
        human_scores=human_scores,
        evaluated_by=evaluated_by,
        force_rescore=force_rescore
    )
