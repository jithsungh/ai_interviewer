"""
Integration Tests — Aggregation Service

Tests the aggregation pipeline with mocked DB session and LLM provider,
simulating end-to-end flows through the service layer.

Verifies:
  1. Complete aggregation pipeline (section aggregation → normalization → recommendation → persist)
  2. Incomplete evaluations raise error
  3. Versioning (old result marked non-current)
  4. Proctoring adjustment (feature-flagged)
  5. AI summary generation with fallback
  6. Section with 0 exchanges handled
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.evaluation.aggregation.config import AggregationConfig
from app.evaluation.aggregation.errors import (
    AggregationAlreadyExistsError,
    IncompleteEvaluationError,
    InterviewNotFoundError,
    NoExchangesError,
    TemplateWeightsNotFoundError,
)
from app.evaluation.aggregation.schemas import InterviewResultData
from app.evaluation.aggregation.service import (
    AggregationService,
    InterviewResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures & Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _config(**overrides):
    """Create AggregationConfig with optional overrides."""
    defaults = dict(
        strong_hire_threshold=85.0,
        hire_threshold=70.0,
        review_threshold=50.0,
        enable_proctoring_influence=False,
        max_exchange_score=100.0,
        score_decimal_places=2,
        scoring_version="1.0.0",
    )
    defaults.update(overrides)
    return AggregationConfig(**defaults)


def _mock_db():
    """Create mock database session with query and execute support."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.rollback = MagicMock()
    return db


def _submission_row(template_id=1, status="completed"):
    return SimpleNamespace(id=100, template_id=template_id, status=status)


def _exchange_rows():
    """3 exchanges across 2 sections."""
    return [
        SimpleNamespace(id=1, sequence_order=1, content_metadata={"section_name": "behavioral"}),
        SimpleNamespace(id=2, sequence_order=2, content_metadata={"section_name": "coding"}),
        SimpleNamespace(id=3, sequence_order=3, content_metadata={"section_name": "coding"}),
    ]


def _evaluation_rows():
    """Final evaluations for all 3 exchanges."""
    return [
        SimpleNamespace(evaluation_id=10, interview_exchange_id=1, total_score=Decimal("80"), evaluator_type="ai"),
        SimpleNamespace(evaluation_id=11, interview_exchange_id=2, total_score=Decimal("90"), evaluator_type="ai"),
        SimpleNamespace(evaluation_id=12, interview_exchange_id=3, total_score=Decimal("85"), evaluator_type="ai"),
    ]


def _template_row():
    return SimpleNamespace(
        template_structure={
            "scoring_configuration": {
                "section_weights": {"behavioral": 30, "coding": 60}
            },
            "sections": [
                {"section_name": "behavioral"},
                {"section_name": "coding"},
            ],
        }
    )


def _rubric_rows():
    return [
        SimpleNamespace(
            rubric_id=1, rubric_name="Test Rubric",
            dimension_id=1, dimension_name="accuracy", weight=Decimal("0.5"), max_score=Decimal("5"),
        ),
        SimpleNamespace(
            rubric_id=1, rubric_name="Test Rubric",
            dimension_id=2, dimension_name="communication", weight=Decimal("0.5"), max_score=Decimal("5"),
        ),
    ]


def _setup_db_execute(db, submission=None, exchanges=None, evaluations=None,
                       template=None, rubrics=None, proctoring=None):
    """Configure db.execute to return different results per query."""
    submission = submission or _submission_row()
    exchanges = exchanges if exchanges is not None else _exchange_rows()
    evaluations = evaluations if evaluations is not None else _evaluation_rows()
    template = template or _template_row()
    rubrics = rubrics if rubrics is not None else _rubric_rows()
    proctoring = proctoring if proctoring is not None else []

    def execute_side_effect(query, params=None):
        q = str(query)
        result = MagicMock()

        if "FROM interview_submissions" in q:
            result.first.return_value = submission
        elif "FROM interview_exchanges" in q:
            result.fetchall.return_value = exchanges
        elif "FROM evaluations" in q:
            result.fetchall.return_value = evaluations
        elif "FROM interview_templates" in q:
            result.first.return_value = template
        elif "interview_template_rubrics" in q:
            result.fetchall.return_value = rubrics
        elif "proctoring_events" in q:
            result.fetchall.return_value = proctoring
        else:
            result.first.return_value = None
            result.fetchall.return_value = []

        return result

    db.execute.side_effect = execute_side_effect


# ═══════════════════════════════════════════════════════════════════════════
# End-to-End Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAggregationPipeline:
    @pytest.mark.asyncio
    async def test_complete_aggregation(self):
        """Full pipeline: aggregate → normalize → recommend → persist."""
        db = _mock_db()
        config = _config()
        _setup_db_execute(db)

        service = AggregationService(db=db, config=config, llm_provider=None)
        result = await service.aggregate_interview_result(
            submission_id=100, generated_by="ai"
        )

        assert isinstance(result, InterviewResultData)
        assert result.interview_submission_id == 100
        assert result.result_status == "completed"
        assert result.generated_by == "ai"
        assert result.scoring_version == "1.0.0"

        # Verify scores are calculated
        assert result.final_score > Decimal("0")
        assert Decimal("0") <= result.normalized_score <= Decimal("100")

        # Verify recommendation is valid
        assert result.recommendation in ("strong_hire", "hire", "review", "no_hire")

        # Verify persistence calls
        db.add.assert_called()
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_normalized_score_calculation(self):
        """Verify correct normalized score for known inputs."""
        db = _mock_db()
        config = _config()
        _setup_db_execute(db)

        service = AggregationService(db=db, config=config, llm_provider=None)
        result = await service.aggregate_interview_result(submission_id=100)

        # behavioral: score=80, weight=30; coding: score=175 (90+85), weight=60
        # final = 80*30 + 175*60 = 2400 + 10500 = 12900
        # max_possible = (100*1)*30 + (100*2)*60 = 3000 + 12000 = 15000
        # normalized = 12900/15000 * 100 = 86.00
        assert result.normalized_score == Decimal("86.00")

    @pytest.mark.asyncio
    async def test_recommendation_from_normalized_score(self):
        """Score 86 → strong_hire (threshold=85)."""
        db = _mock_db()
        config = _config()
        _setup_db_execute(db)

        service = AggregationService(db=db, config=config, llm_provider=None)
        result = await service.aggregate_interview_result(submission_id=100)

        assert result.recommendation == "strong_hire"


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAggregationErrors:
    @pytest.mark.asyncio
    async def test_interview_not_found(self):
        db = _mock_db()
        _setup_db_execute(db, submission=None)
        # Patch to return None for submission
        def execute_not_found(query, params=None):
            result = MagicMock()
            result.first.return_value = None
            result.fetchall.return_value = []
            return result
        db.execute.side_effect = execute_not_found

        service = AggregationService(db=db, config=_config())
        with pytest.raises(InterviewNotFoundError):
            await service.aggregate_interview_result(submission_id=999)

    @pytest.mark.asyncio
    async def test_no_exchanges(self):
        db = _mock_db()
        _setup_db_execute(db, exchanges=[])

        service = AggregationService(db=db, config=_config())
        with pytest.raises(NoExchangesError):
            await service.aggregate_interview_result(submission_id=100)

    @pytest.mark.asyncio
    async def test_incomplete_evaluations(self):
        """Not all exchanges have evaluations → error with pending IDs."""
        db = _mock_db()
        # 3 exchanges but only 2 evaluations
        partial_evals = _evaluation_rows()[:2]
        _setup_db_execute(db, evaluations=partial_evals)

        service = AggregationService(db=db, config=_config())
        with pytest.raises(IncompleteEvaluationError) as exc_info:
            await service.aggregate_interview_result(submission_id=100)

        assert 3 in exc_info.value.pending_exchange_ids

    @pytest.mark.asyncio
    async def test_existing_result_without_force(self):
        """Current result exists and force=False → error."""
        db = _mock_db()
        existing = MagicMock()
        existing.id = 42
        existing.is_current = True
        db.query.return_value.filter.return_value.first.return_value = existing

        _setup_db_execute(db)

        service = AggregationService(db=db, config=_config())
        with pytest.raises(AggregationAlreadyExistsError) as exc_info:
            await service.aggregate_interview_result(submission_id=100)

        assert exc_info.value.existing_result_id == 42


# ═══════════════════════════════════════════════════════════════════════════
# Versioning Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVersioning:
    @pytest.mark.asyncio
    async def test_force_reaggregate_marks_old_non_current(self):
        """force_reaggregate=True marks old result as non-current."""
        db = _mock_db()
        existing = MagicMock()
        existing.id = 42
        existing.is_current = True
        db.query.return_value.filter.return_value.first.return_value = existing

        _setup_db_execute(db)

        service = AggregationService(db=db, config=_config())
        result = await service.aggregate_interview_result(
            submission_id=100, force_reaggregate=True
        )

        # Old result should be marked non-current
        assert existing.is_current is False
        # New result should be created
        assert isinstance(result, InterviewResultData)
        db.add.assert_called()


# ═══════════════════════════════════════════════════════════════════════════
# Proctoring Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestProctoringIntegration:
    @pytest.mark.asyncio
    async def test_proctoring_disabled_no_adjustment(self):
        """Proctoring disabled → recommendation not changed."""
        db = _mock_db()
        config = _config(enable_proctoring_influence=False)
        proctoring_events = [
            SimpleNamespace(severity="high", event_type="tab_switch"),
        ]
        _setup_db_execute(db, proctoring=proctoring_events)

        service = AggregationService(db=db, config=config)
        result = await service.aggregate_interview_result(submission_id=100)

        # Score 86 → strong_hire, not affected by proctoring
        assert result.recommendation == "strong_hire"

    @pytest.mark.asyncio
    async def test_proctoring_high_risk_downgrades(self):
        """Proctoring enabled + high risk → downgrade recommendation."""
        db = _mock_db()
        config = _config(enable_proctoring_influence=True, high_risk_downgrade=True)
        proctoring_events = [
            SimpleNamespace(severity="high", event_type="tab_switch"),
            SimpleNamespace(severity="high", event_type="background_noise"),
        ]
        _setup_db_execute(db, proctoring=proctoring_events)

        service = AggregationService(db=db, config=config)
        result = await service.aggregate_interview_result(submission_id=100)

        # Score 86 → strong_hire → downgraded to hire
        assert result.recommendation == "hire"


# ═══════════════════════════════════════════════════════════════════════════
# Summary Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryIntegration:
    @pytest.mark.asyncio
    async def test_fallback_summary_without_provider(self):
        """No LLM provider → fallback summary."""
        db = _mock_db()
        _setup_db_execute(db)

        service = AggregationService(db=db, config=_config(), llm_provider=None)
        result = await service.aggregate_interview_result(submission_id=100)

        assert result.strengths == []
        assert result.weaknesses == []
        assert "unavailable" in result.summary_notes.lower()

    @pytest.mark.asyncio
    async def test_ai_summary_with_mock_provider(self):
        """Mock LLM provider → AI summary used."""
        db = _mock_db()
        _setup_db_execute(db)

        ai_response = {
            "strengths": ["Excellent coding"],
            "weaknesses": ["Could improve communication"],
            "summary_notes": "Strong technical candidate.",
        }
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps(ai_response)

        mock_provider = MagicMock()
        mock_provider.generate_structured = AsyncMock(return_value=mock_response)
        mock_provider.get_provider_name = MagicMock(return_value="test")

        service = AggregationService(db=db, config=_config(), llm_provider=mock_provider)
        result = await service.aggregate_interview_result(submission_id=100)

        assert result.strengths == ["Excellent coding"]
        assert result.weaknesses == ["Could improve communication"]
        assert "Strong technical candidate" in result.summary_notes
