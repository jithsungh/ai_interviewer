"""
Summary Generator

Generates AI-powered interview summaries (strengths, weaknesses, notes).

Design:
- Uses LLM structured output for consistent format
- Enriched with per-exchange Q&A data for evidence-based insights
- Attempts to load prompt from DB via PromptService, falls back to inline
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
    from sqlalchemy.orm import Session

logger = get_context_logger(__name__)


# ── Data class for exchange-level details ──────────────────────────────

class ExchangeDetail:
    """Per-exchange data passed to the summary generator for evidence-based report."""

    def __init__(
        self,
        sequence_order: int,
        section_name: str,
        question_text: str,
        response_text: Optional[str] = None,
        difficulty: Optional[str] = None,
        total_score: Optional[float] = None,
        dimension_scores: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.sequence_order = sequence_order
        self.section_name = section_name
        self.question_text = question_text
        self.response_text = response_text
        self.difficulty = difficulty
        self.total_score = total_score
        self.dimension_scores = dimension_scores or []


# ── Prompt Templates ───────────────────────────────────────────────────

REPORT_SYSTEM_PROMPT = (
    "You are an interview report evaluator. Treat each request as stateless and only use provided data. "
    "Do not invent facts. Return valid JSON only with strengths, weaknesses, and summary_notes."
)

REPORT_USER_PROMPT_TEMPLATE = """Generate a concise interview report from this data.

SCORE: {normalized_score}/100
RECOMMENDATION: {recommendation}
EXCHANGES: {total_exchanges}

SECTIONS:
{section_breakdown}

EXCHANGE DETAILS:
{exchange_details}

Return JSON only:
{{"strengths":["..."],"weaknesses":["..."],"summary_notes":"..."}}"""


class SummaryGenerator:
    """
    Generates AI-powered interview summaries.

    Enhanced to accept per-exchange Q&A data for evidence-based
    strengths/weaknesses/notes. Falls back to generic summary
    when LLM is unavailable.
    """

    def __init__(
        self,
        llm_provider: Optional["BaseLLMProvider"] = None,
        config: Optional[AggregationConfig] = None,
        db: Optional["Session"] = None,
    ) -> None:
        self._provider = llm_provider
        self._config = config or get_aggregation_config()
        self._db = db

    async def generate(
        self,
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
        exchange_details: Optional[List[ExchangeDetail]] = None,
    ) -> SummaryData:
        """
        Generate interview summary.

        Args:
            section_scores: Per-section score breakdown.
            normalized_score: Normalized 0–100 score.
            recommendation: Recommendation string.
            exchange_details: Optional per-exchange Q&A + evaluation data.

        Returns:
            SummaryData with strengths, weaknesses, and narrative notes.
            Falls back to generic summary on AI failure.
        """
        if self._provider is None:
            logger.info("No LLM provider configured — using fallback summary")
            return self._fallback_summary(
                section_scores, normalized_score, recommendation, exchange_details
            )

        try:
            return await self._generate_with_ai(
                section_scores, normalized_score, recommendation, exchange_details
            )
        except Exception as e:
            logger.warning(
                "AI summary generation failed — using fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return self._fallback_summary(
                section_scores, normalized_score, recommendation, exchange_details
            )

    async def _generate_with_ai(
        self,
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
        exchange_details: Optional[List[ExchangeDetail]] = None,
    ) -> SummaryData:
        """Call LLM for summary generation with rich exchange data."""

        # Try to load prompt template from DB
        system_prompt = REPORT_SYSTEM_PROMPT
        user_prompt_text = self._build_prompt(
            section_scores, normalized_score, recommendation, exchange_details
        )

        if self._db is not None:
            try:
                from app.ai.prompts.repository import SqlPromptTemplateRepository
                from app.ai.prompts.service import PromptService

                repo = SqlPromptTemplateRepository(self._db)
                prompt_service = PromptService(repository=repo)

                variables = {
                    "normalized_score": str(normalized_score),
                    "recommendation": recommendation,
                    "total_exchanges": str(
                        sum(s.exchanges_evaluated for s in section_scores)
                    ),
                    "section_breakdown": self._format_section_breakdown(section_scores),
                    "exchange_details": self._format_exchange_details(
                        exchange_details,
                        max_exchanges=self._config.summary_max_exchanges_in_prompt,
                        max_question_chars=self._config.summary_max_question_chars,
                        max_response_chars=self._config.summary_max_response_chars,
                        max_dimensions=self._config.summary_max_dimension_scores_per_exchange,
                    ),
                }

                rendered = prompt_service.get_rendered_prompt(
                    prompt_type="report_generation",
                    variables=variables,
                )
                system_prompt = rendered.system_prompt or REPORT_SYSTEM_PROMPT
                user_prompt_text = rendered.text
                logger.info("Using DB prompt template for report generation")
            except Exception as e:
                logger.info(
                    "DB prompt template not found, using inline template",
                    extra={"error": str(e)},
                )

        request = LLMRequest(
            prompt=user_prompt_text,
            model=self._config.summary_model,
            system_prompt=system_prompt,
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
        exchange_details: Optional[List[ExchangeDetail]] = None,
    ) -> str:
        """Build the enriched summary generation prompt."""
        section_breakdown = self._format_section_breakdown(section_scores)
        total_exchanges = sum(s.exchanges_evaluated for s in section_scores)
        exchange_details_text = self._format_exchange_details(
            exchange_details,
            max_exchanges=self._config.summary_max_exchanges_in_prompt,
            max_question_chars=self._config.summary_max_question_chars,
            max_response_chars=self._config.summary_max_response_chars,
            max_dimensions=self._config.summary_max_dimension_scores_per_exchange,
        )

        return REPORT_USER_PROMPT_TEMPLATE.format(
            section_breakdown=section_breakdown,
            total_exchanges=total_exchanges,
            normalized_score=normalized_score,
            recommendation=recommendation,
            exchange_details=exchange_details_text,
        )

    @staticmethod
    def _format_section_breakdown(section_scores: List[SectionScore]) -> str:
        """Format section scores for the prompt."""
        if not section_scores:
            return "No section data available."

        lines = []
        for section in section_scores:
            avg = (
                section.score / Decimal(section.exchanges_evaluated)
                if section.exchanges_evaluated > 0
                else Decimal("0")
            )
            lines.append(
                f"- **{section.section_name}**: total={section.score}, "
                f"avg={avg:.1f}, weight={section.weight}, "
                f"exchanges={section.exchanges_evaluated}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_exchange_details(
        exchange_details: Optional[List[ExchangeDetail]],
        max_exchanges: int = 12,
        max_question_chars: int = 180,
        max_response_chars: int = 320,
        max_dimensions: int = 4,
    ) -> str:
        """Format per-exchange Q&A data for the prompt."""
        if not exchange_details:
            return "No per-exchange detail available."

        lines = []
        limited_exchanges = exchange_details[:max_exchanges]
        for ex in limited_exchanges:
            dim_text = ""
            if ex.dimension_scores:
                dims = [
                    f"  - {d.get('dimension_name', '?')}: {d.get('score', 0)}/{d.get('max_score', 10)}"
                    for d in ex.dimension_scores[:max_dimensions]
                ]
                dim_text = "\n" + "\n".join(dims)

            response_preview = (ex.response_text or "No response")[:max_response_chars]
            if ex.response_text and len(ex.response_text) > max_response_chars:
                response_preview += "... [truncated]"

            lines.append(
                f"Q{ex.sequence_order} [{ex.section_name}] diff={ex.difficulty or 'N/A'}\n"
                f"Question: {ex.question_text[:max_question_chars]}\n"
                f"Response: {response_preview}\n"
                f"Score: {ex.total_score or 'N/A'}%"
                f"{dim_text}"
            )

        if len(exchange_details) > max_exchanges:
            lines.append(
                f"... {len(exchange_details) - max_exchanges} more exchanges omitted for prompt size control"
            )

        return "\n\n".join(lines)

    @staticmethod
    def _fallback_summary(
        section_scores: List[SectionScore],
        normalized_score: Decimal,
        recommendation: str,
        exchange_details: Optional[List[ExchangeDetail]] = None,
    ) -> SummaryData:
        """
        Generate evidence-based fallback summary when AI is unavailable.

        Uses section scores and exchange data to derive basic insights.
        """
        strengths: List[str] = []
        weaknesses: List[str] = []

        # Derive strengths/weaknesses from section scores
        for section in sorted(section_scores, key=lambda s: float(s.score), reverse=True):
            avg = (
                float(section.score) / section.exchanges_evaluated
                if section.exchanges_evaluated > 0
                else 0
            )
            if avg >= 7.0:
                strengths.append(
                    f"Strong performance in {section.section_name} "
                    f"(avg score: {avg:.1f})"
                )
            elif avg < 5.0:
                weaknesses.append(
                    f"Needs improvement in {section.section_name} "
                    f"(avg score: {avg:.1f})"
                )

        # Derive from exchange-level data if available
        if exchange_details:
            high_scorers = [
                ex for ex in exchange_details
                if ex.total_score is not None and ex.total_score >= 80
            ]
            low_scorers = [
                ex for ex in exchange_details
                if ex.total_score is not None and ex.total_score < 50
            ]

            for ex in high_scorers[:2]:
                strengths.append(
                    f"Excelled on Q{ex.sequence_order} ({ex.section_name}): "
                    f"scored {ex.total_score:.0f}%"
                )

            for ex in low_scorers[:2]:
                weaknesses.append(
                    f"Struggled with Q{ex.sequence_order} ({ex.section_name}): "
                    f"scored {ex.total_score:.0f}%"
                )

        # Ensure at least one item
        if not strengths:
            strengths.append("Completed the interview successfully.")
        if not weaknesses:
            weaknesses.append("Consider deepening knowledge in assessed areas.")

        summary = (
            f"Interview completed with normalized score {normalized_score}/100. "
            f"Recommendation: {recommendation}. "
        )

        if section_scores:
            best = max(section_scores, key=lambda s: float(s.score))
            summary += f"Strongest section: {best.section_name}. "

        summary += "Detailed AI analysis was unavailable at the time of report generation."

        return SummaryData(
            strengths=strengths[:5],
            weaknesses=weaknesses[:5],
            summary_notes=summary,
        )
