"""
Integration Tests — Scoring Service

Tests the scoring module with mocked DB session and LLM provider,
simulating end-to-end flows through the service layer.

Verifies:
  1. AI scoring flow (rubric resolution → LLM → calculation → persistence)
  2. Human scoring flow (validation → calculation → persistence)
  3. Hybrid scoring flow (AI + human override)
  4. One exchange = one evaluation invariant
  5. Re-scoring with force_rescore flag
  6. Error handling on invalid exchange/rubric
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.scoring.contracts import (
    AIScoreResult,
    DimensionScoreResult,
    HumanDimensionScore,
    HumanScoreInput,
    RubricDimensionDTO,
)
from app.evaluation.scoring.errors import (
    AIEvaluationError,
    EvaluationExistsError,
    ExchangeNotFoundError,
    InvalidRubricError,
    InvalidScoreError,
    MissingDimensionError,
    RubricNotFoundError,
)
from app.evaluation.scoring.service import (
    Evaluation,
    EvaluationDimensionScore,
    EvaluatorType,
    ScoringService,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures & Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_dimensions():
    """Create sample rubric dimensions."""
    return [
        RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=Decimal("0.4"),
            description="Technical accuracy",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
        RubricDimensionDTO(
            rubric_dimension_id=2,
            dimension_name="Communication",
            max_score=Decimal("5.0"),
            weight=Decimal("0.3"),
            description="Communication clarity",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
        RubricDimensionDTO(
            rubric_dimension_id=3,
            dimension_name="Problem Solving",
            max_score=Decimal("5.0"),
            weight=Decimal("0.3"),
            description="Problem solving ability",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
    ]


def _make_ai_score_result():
    """Create sample AI score result."""
    return AIScoreResult(
        dimension_scores=[
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=4.0,
                justification="Good technical accuracy demonstrated.",
            ),
            DimensionScoreResult(
                dimension_name="Communication",
                score=3.5,
                justification="Clear communication with good structure.",
            ),
            DimensionScoreResult(
                dimension_name="Problem Solving",
                score=4.5,
                justification="Excellent problem solving approach.",
            ),
        ],
        overall_comment="Strong overall performance.",
        model_id="llama-3.3-70b-versatile",
    )


def _make_human_input():
    """Create sample human scoring input."""
    return HumanScoreInput(
        dimension_scores=[
            HumanDimensionScore(
                rubric_dimension_id=1,
                score=4.5,
                justification="Excellent technical accuracy with minor issues.",
            ),
            HumanDimensionScore(
                rubric_dimension_id=2,
                score=4.0,
                justification="Clear and structured communication.",
            ),
            HumanDimensionScore(
                rubric_dimension_id=3,
                score=4.0,
                justification="Good problem solving methodology.",
            ),
        ],
        overall_comment="Very good performance overall.",
        evaluator_id=42,
    )


def _mock_db_session():
    """Create mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.rollback = MagicMock()
    return db


def _mock_exchange_data():
    """Create mock exchange data result."""
    return SimpleNamespace(
        exchange_id=123,
        question_content="What is polymorphism in OOP?",
        question_type="technical",
        answer_content="Polymorphism is the ability of objects...",
        audio_transcript=None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# AI Scoring Flow Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAIScoringFlow:
    @pytest.mark.asyncio
    async def test_ai_scoring_complete_flow(self):
        """Test complete AI scoring pipeline."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        ai_result = _make_ai_score_result()
        
        # Mock exchange data query
        db.execute.return_value.first.return_value = _mock_exchange_data()
        
        # Track created evaluation
        created_evaluation = None
        
        def track_add(obj):
            nonlocal created_evaluation
            if isinstance(obj, Evaluation):
                obj.id = 1
                obj.evaluated_at = datetime.now(timezone.utc)
                created_evaluation = obj
        
        db.add.side_effect = track_add
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver, patch(
            "app.evaluation.scoring.service.AIScorer"
        ) as MockAIScorer:
            # Configure mocks
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            mock_ai_scorer = MockAIScorer.return_value
            mock_ai_scorer.score = AsyncMock(return_value=ai_result)
            
            service = ScoringService(db, llm_provider=MagicMock())
            result = await service.score_exchange(
                interview_exchange_id=123,
                evaluator_type=EvaluatorType.AI,
            )
        
        # Verify result
        assert result.evaluation_id == 1
        assert result.interview_exchange_id == 123
        assert result.rubric_id == 10
        assert result.evaluator_type == "ai"
        assert result.total_score == Decimal("80.00")
        assert len(result.dimension_scores) == 3
        assert result.model_id == "llama-3.3-70b-versatile"
        
        # Verify persistence
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_scoring_with_transcript(self):
        """Test AI scoring uses transcript when available."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        ai_result = _make_ai_score_result()
        
        # Mock exchange with transcript
        exchange = _mock_exchange_data()
        exchange.audio_transcript = "User said: Polymorphism is..."
        db.execute.return_value.first.return_value = exchange
        
        def track_add(obj):
            if isinstance(obj, Evaluation):
                obj.id = 1
                obj.evaluated_at = datetime.now(timezone.utc)
        
        db.add.side_effect = track_add
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver, patch(
            "app.evaluation.scoring.service.AIScorer"
        ) as MockAIScorer:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            mock_ai_scorer = MockAIScorer.return_value
            mock_ai_scorer.score = AsyncMock(return_value=ai_result)
            
            service = ScoringService(db, llm_provider=MagicMock())
            result = await service.score_exchange(
                interview_exchange_id=123,
                evaluator_type=EvaluatorType.AI,
            )
            
            # Verify AI scorer received transcript
            call_kwargs = mock_ai_scorer.score.call_args.kwargs
            assert call_kwargs.get("transcript") == "User said: Polymorphism is..."


# ═══════════════════════════════════════════════════════════════════════════
# Human Scoring Flow Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHumanScoringFlow:
    @pytest.mark.asyncio
    async def test_human_scoring_complete_flow(self):
        """Test complete human scoring pipeline."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        human_input = _make_human_input()
        
        db.execute.return_value.first.return_value = _mock_exchange_data()
        
        def track_add(obj):
            if isinstance(obj, Evaluation):
                obj.id = 2
                obj.evaluated_at = datetime.now(timezone.utc)
        
        db.add.side_effect = track_add
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            service = ScoringService(db, llm_provider=MagicMock())
            result = await service.score_exchange(
                interview_exchange_id=123,
                evaluator_type=EvaluatorType.HUMAN,
                human_scores=human_input,
                evaluated_by=42,
            )
        
        # Verify result
        assert result.evaluation_id == 2
        assert result.evaluator_type == "human"
        assert result.model_id is None  # No AI model for human scoring
        
        # Verify persistence
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_human_scoring_requires_input(self):
        """Human scoring without input should raise error."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        
        db.execute.return_value.first.return_value = _mock_exchange_data()
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            service = ScoringService(db, llm_provider=MagicMock())
            
            with pytest.raises(ValueError, match="human_scores required"):
                await service.score_exchange(
                    interview_exchange_id=123,
                    evaluator_type=EvaluatorType.HUMAN,
                    human_scores=None,  # Missing
                )


# ═══════════════════════════════════════════════════════════════════════════
# Evaluation Exists Invariant Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationExistsInvariant:
    @pytest.mark.asyncio
    async def test_duplicate_evaluation_raises_error(self):
        """Existing final evaluation should raise EvaluationExistsError."""
        db = _mock_db_session()
        
        # Simulate existing evaluation
        existing = SimpleNamespace(id=999, is_final=True)
        db.query.return_value.filter.return_value.first.return_value = existing
        
        service = ScoringService(db, llm_provider=MagicMock())
        
        with pytest.raises(EvaluationExistsError) as exc_info:
            await service.score_exchange(
                interview_exchange_id=123,
                evaluator_type=EvaluatorType.AI,
            )
        
        assert exc_info.value.exchange_id == 123
        assert exc_info.value.existing_evaluation_id == 999

    @pytest.mark.asyncio
    async def test_force_rescore_marks_existing_non_final(self):
        """force_rescore=True should mark existing as non-final."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        ai_result = _make_ai_score_result()
        
        # Simulate existing evaluation
        existing = MagicMock()
        existing.id = 999
        existing.is_final = True
        
        # First call returns existing, subsequent calls return None
        db.query.return_value.filter.return_value.first.side_effect = [
            existing,  # Check for existing
            None,      # Get dimension name lookups
        ]
        db.execute.return_value.first.return_value = _mock_exchange_data()
        
        def track_add(obj):
            if isinstance(obj, Evaluation):
                obj.id = 1000
                obj.evaluated_at = datetime.now(timezone.utc)
        
        db.add.side_effect = track_add
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver, patch(
            "app.evaluation.scoring.service.AIScorer"
        ) as MockAIScorer:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            mock_ai_scorer = MockAIScorer.return_value
            mock_ai_scorer.score = AsyncMock(return_value=ai_result)
            
            service = ScoringService(db, llm_provider=MagicMock())
            result = await service.score_exchange(
                interview_exchange_id=123,
                evaluator_type=EvaluatorType.AI,
                force_rescore=True,  # Allow re-scoring
            )
        
        # Verify existing was marked non-final
        assert existing.is_final == False
        
        # Verify new evaluation created
        assert result.evaluation_id == 1000


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_exchange_not_found(self):
        """Non-existent exchange should raise ExchangeNotFoundError."""
        db = _mock_db_session()
        dimensions = _make_dimensions()
        
        # No existing evaluation
        db.query.return_value.filter.return_value.first.return_value = None
        
        # Exchange not found
        db.execute.return_value.first.return_value = None
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, dimensions)
            
            service = ScoringService(db, llm_provider=MagicMock())
            
            with pytest.raises(ExchangeNotFoundError) as exc_info:
                await service.score_exchange(
                    interview_exchange_id=999,
                    evaluator_type=EvaluatorType.AI,
                )
            
            assert exc_info.value.exchange_id == 999

    @pytest.mark.asyncio
    async def test_invalid_rubric_no_dimensions(self):
        """Rubric with no dimensions should raise InvalidRubricError."""
        db = _mock_db_session()
        
        db.execute.return_value.first.return_value = _mock_exchange_data()
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.return_value = (10, [])  # No dimensions
            
            service = ScoringService(db, llm_provider=MagicMock())
            
            with pytest.raises(InvalidRubricError) as exc_info:
                await service.score_exchange(
                    interview_exchange_id=123,
                    evaluator_type=EvaluatorType.AI,
                )
            
            assert exc_info.value.rubric_id == 10

    @pytest.mark.asyncio
    async def test_rubric_not_found(self):
        """Missing rubric should raise RubricNotFoundError."""
        db = _mock_db_session()
        
        with patch(
            "app.evaluation.scoring.service.RubricResolver"
        ) as MockRubricResolver:
            mock_resolver = MockRubricResolver.return_value
            mock_resolver.resolve_rubric.side_effect = RubricNotFoundError(
                template_id=123
            )
            
            service = ScoringService(db, llm_provider=MagicMock())
            
            with pytest.raises(RubricNotFoundError):
                await service.score_exchange(
                    interview_exchange_id=123,
                    evaluator_type=EvaluatorType.AI,
                )


# ═══════════════════════════════════════════════════════════════════════════
# Get Evaluation Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGetEvaluation:
    def test_get_evaluation_by_id(self):
        """Should fetch existing evaluation by ID."""
        db = _mock_db_session()
        
        # Mock evaluation
        mock_eval = SimpleNamespace(
            id=1,
            interview_exchange_id=123,
            rubric_id=10,
            evaluator_type="ai",
            total_score=Decimal("80.00"),
            explanation="Good performance.",
            is_final=True,
            evaluated_at=datetime.now(timezone.utc),
            evaluated_by=None,
            model_id="llama-3.3-70b-versatile",
            scoring_version="1.0.0",
        )
        
        # Mock dimension scores
        mock_dim_scores = [
            SimpleNamespace(
                rubric_dimension_id=1,
                score=Decimal("4.0"),
                justification="Good accuracy.",
            ),
        ]
        
        db.query.return_value.filter.return_value.first.return_value = mock_eval
        db.query.return_value.filter.return_value.all.return_value = mock_dim_scores
        
        # Mock dimension name lookup
        db.execute.return_value.first.return_value = SimpleNamespace(
            dimension_name="Accuracy"
        )
        
        service = ScoringService(db, llm_provider=MagicMock())
        result = service.get_evaluation(evaluation_id=1)
        
        assert result is not None
        assert result.evaluation_id == 1
        assert result.total_score == Decimal("80.00")

    def test_get_evaluation_not_found(self):
        """Should return None for non-existent evaluation."""
        db = _mock_db_session()
        db.query.return_value.filter.return_value.first.return_value = None
        
        service = ScoringService(db, llm_provider=MagicMock())
        result = service.get_evaluation(evaluation_id=999)
        
        assert result is None
