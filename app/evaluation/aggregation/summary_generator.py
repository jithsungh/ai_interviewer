"""
Summary Generator

Generates AI-powered interview summaries (strengths, weaknesses, notes).

Design:
- Uses LLM structured output for consistent format
- Graceful fallback when AI is unavailable or times out
- No persistence — returns SummaryData for the service to store
- Follows same retry/provider pattern as ai_scorer.py
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.ai.llm.contracts import LLMRequest
from app.ai.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.evaluation.aggregation.config import AggregationConfig, get_aggregation_config
from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    SectionScore,
    SummaryData,
    SummaryResponseSchema,
)
from app.shared.observability import get_context_logger

if TYPE_CHECKING:
    from app.ai.llm import BaseLLMProvider

logger = get_context_logger(__name__)


# ── Prompt Templates ───────────────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = (
    "You are an expert technical interviewer writing a post-interview summary. "
    "Be concise, factual, and actionable. Focus on observable evidence from "
    "the scoring data provided."
)

SUMMARY_USER_PROMPT_TEMPLATE = """Generate a summary for the following interview results.

**Section Performance:**
{section_breakdown}

**Overall Statistics:**
- Total exchanges evaluated: {total_exchanges}
- Normalized score: {normalized_score}/100
- Recommendation: {recommendation}

**Instructions:**
1. Identify 3–5 key strengths based on section scores
2. Identify 3–5 areas for improvement / weaknesses
3. Write a 2–3 paragraph narrative summary

**Output Format (JSON):**
{{"strengths": ["...", "..."], "weaknesses": ["...", "..."], "summary_notes": "..."}}"""


class SummaryGenerator:
    """
    Generates AI-powered interview summaries.

    Falls back to a generic summary when the LLM is unavailable.
    """

    def __init__(
        self,
        llm_provider: Optional["BaseLLMProvider"] = None,
        config: Optional[AggregationConfig] = None,
    ) -> None:
        self._provider = llm_provider
        self._config = config or get_aggregation_config()

    async def generate(
        self,
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
    ) -> SummaryData:
        """
        Generate interview summary.

        Args:
            section_scores: Per-section score breakdown.
            normalized_score: Normalized 0–100 score.
            recommendation: Recommendation string.

        Returns:
            SummaryData with strengths, weaknesses, and narrative notes.
            Falls back to generic summary on AI failure.
        """
        if self._provider is None:
            logger.info("No LLM provider configured — using fallback summary")
            return self._fallback_summary(normalized_score, recommendation)

        try:
            return await self._generate_with_ai(
                section_scores, normalized_score, recommendation
            )
        except Exception as e:
            logger.warning(
                "AI summary generation failed — using fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return self._fallback_summary(normalized_score, recommendation)

    async def _generate_with_ai(
        self,
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
    ) -> SummaryData:
        """Call LLM for summary generation."""
        prompt = self._build_prompt(section_scores, normalized_score, recommendation)

        request = LLMRequest(
            prompt=prompt,
            model=self._config.summary_model,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            temperature=self._config.summary_temperature,
            max_tokens=self._config.summary_max_tokens,
            timeout_seconds=self._config.summary_timeout_seconds,
            json_mode=True,
            schema=SummaryResponseSchema.get_json_schema(),
            deterministic=False,
        )

        response = await self._provider.generate_structured(request)

        if not response.success:
            error_msg = response.error.message if response.error else "Unknown error"
            raise LLMProviderError(
                provider=self._provider.get_provider_name(),
                message=error_msg,
            )

        # Parse and validate response
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(
                provider=self._provider.get_provider_name(),
                message=f"Invalid JSON in summary response: {e}",
            )

        schema = SummaryResponseSchema(**parsed)
        return schema.to_summary_data()

    def _build_prompt(
        self,
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
    ) -> str:
        """Build the summary generation prompt."""
        lines = []
        for section in section_scores:
            avg = (
                section.score / Decimal(section.exchanges_evaluated)
                if section.exchanges_evaluated > 0
                else Decimal("0")
            )
            lines.append(
                f"- {section.section_name}: total={section.score}, "
                f"avg={avg:.1f}, weight={section.weight}, "
                f"exchanges={section.exchanges_evaluated}"
            )

        section_breakdown = "\n".join(lines) if lines else "No section data available."
        total_exchanges = sum(s.exchanges_evaluated for s in section_scores)

        return SUMMARY_USER_PROMPT_TEMPLATE.format(
            section_breakdown=section_breakdown,
            total_exchanges=total_exchanges,
            normalized_score=normalized_score,
            recommendation=recommendation,
        )

    @staticmethod
    def _fallback_summary(
        normalized_score: Decimal,
        recommendation: str,
    ) -> SummaryData:
        """
        Generate fallback summary when AI is unavailable.

        Returns generic summary with score and recommendation.
        """
        return SummaryData(
            strengths=[],
            weaknesses=[],
            summary_notes=(
                f"Interview completed with normalized score {normalized_score}/100. "
                f"Recommendation: {recommendation}. "
                f"Detailed AI summary unavailable."
            ),
        )
