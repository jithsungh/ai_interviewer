"""
Unit Tests — Summary Generator

Tests AI-powered summary generation and fallback behavior.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.aggregation.config import AggregationConfig
from app.evaluation.aggregation.schemas import SectionScore, SummaryData
from app.evaluation.aggregation.summary_generator import SummaryGenerator


@pytest.fixture
def config():
    return AggregationConfig(
        summary_model="test-model",
        summary_temperature=0.5,
        summary_max_tokens=500,
        summary_timeout_seconds=10,
    )


@pytest.fixture
def section_scores():
    return [
        SectionScore(section_name="coding", score=Decimal("263"), weight=60, exchanges_evaluated=3),
        SectionScore(section_name="behavioral", score=Decimal("145"), weight=30, exchanges_evaluated=2),
        SectionScore(section_name="resume", score=Decimal("85"), weight=10, exchanges_evaluated=1),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Fallback Summary Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryGeneratorFallback:
    @pytest.mark.asyncio
    async def test_no_provider_returns_fallback(self, config, section_scores):
        generator = SummaryGenerator(llm_provider=None, config=config)
        result = await generator.generate(
            section_scores=section_scores,
            normalized_score=Decimal("83.72"),
            recommendation="hire",
        )
        assert isinstance(result, SummaryData)
        assert result.strengths == []
        assert result.weaknesses == []
        assert "83.72" in result.summary_notes
        assert "hire" in result.summary_notes
        assert "unavailable" in result.summary_notes.lower()

    @pytest.mark.asyncio
    async def test_provider_error_returns_fallback(self, config, section_scores):
        mock_provider = MagicMock()
        mock_provider.generate_structured = AsyncMock(side_effect=Exception("LLM down"))
        mock_provider.get_provider_name = MagicMock(return_value="test")

        generator = SummaryGenerator(llm_provider=mock_provider, config=config)
        result = await generator.generate(
            section_scores=section_scores,
            normalized_score=Decimal("70.00"),
            recommendation="hire",
        )
        assert isinstance(result, SummaryData)
        assert result.strengths == []
        assert "70.00" in result.summary_notes


# ═══════════════════════════════════════════════════════════════════════════
# AI Summary Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryGeneratorAI:
    @pytest.mark.asyncio
    async def test_successful_ai_summary(self, config, section_scores):
        ai_response = {
            "strengths": ["Strong coding skills", "Good communication"],
            "weaknesses": ["Needs more practice with system design"],
            "summary_notes": "The candidate demonstrated solid technical abilities.",
        }

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps(ai_response)

        mock_provider = MagicMock()
        mock_provider.generate_structured = AsyncMock(return_value=mock_response)
        mock_provider.get_provider_name = MagicMock(return_value="test")

        generator = SummaryGenerator(llm_provider=mock_provider, config=config)
        result = await generator.generate(
            section_scores=section_scores,
            normalized_score=Decimal("83.72"),
            recommendation="hire",
        )

        assert isinstance(result, SummaryData)
        assert len(result.strengths) == 2
        assert result.strengths[0] == "Strong coding skills"
        assert len(result.weaknesses) == 1
        assert "solid technical" in result.summary_notes

    @pytest.mark.asyncio
    async def test_unsuccessful_response_falls_back(self, config, section_scores):
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = MagicMock()
        mock_response.error.message = "Model overloaded"

        mock_provider = MagicMock()
        mock_provider.generate_structured = AsyncMock(return_value=mock_response)
        mock_provider.get_provider_name = MagicMock(return_value="test")

        generator = SummaryGenerator(llm_provider=mock_provider, config=config)
        result = await generator.generate(
            section_scores=section_scores,
            normalized_score=Decimal("50.00"),
            recommendation="review",
        )

        # Should fall back due to LLMProviderError
        assert isinstance(result, SummaryData)
        assert "50.00" in result.summary_notes

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back(self, config, section_scores):
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "not valid json"

        mock_provider = MagicMock()
        mock_provider.generate_structured = AsyncMock(return_value=mock_response)
        mock_provider.get_provider_name = MagicMock(return_value="test")

        generator = SummaryGenerator(llm_provider=mock_provider, config=config)
        result = await generator.generate(
            section_scores=section_scores,
            normalized_score=Decimal("75.00"),
            recommendation="hire",
        )

        assert isinstance(result, SummaryData)
        assert result.strengths == []
