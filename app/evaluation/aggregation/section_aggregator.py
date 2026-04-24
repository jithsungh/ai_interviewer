"""
Section Aggregator

Groups exchange evaluations by template section and computes
per-section score totals.

Design:
- Pure computation — no database access
- Receives pre-fetched data as arguments
- Returns List[SectionScore] for downstream processing
- Handles sections with 0 exchanges gracefully
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Dict, List, Set

from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    ExchangeSummaryDTO,
    SectionScore,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


SECTION_NAME_ALIASES: Dict[str, str] = {
    "resume": "resume_analysis",
    "resume_experience": "resume_analysis",
    "resume_and_experience_analysis": "resume_analysis",
    "self_intro": "self_introduction",
    "selfintroduction": "self_introduction",
    "behavioral": "behavioral_assessment",
    "behavioral_round": "behavioral_assessment",
    "coding": "live_coding",
    "coding_round": "live_coding",
    "technical": "technical_concepts",
    "technical_depth": "technical_concepts",
    "complexity": "complexity_analysis",
}


class SectionAggregator:
    """
    Aggregates exchange evaluations into section-level scores.

    Groups evaluations by the template section each exchange belongs to,
    and sums total_scores within each section.
    """

    def aggregate(
        self,
        exchanges: List[ExchangeSummaryDTO],
        evaluations: List[EvaluationSummaryDTO],
        template_weights: Dict[str, int],
    ) -> List[SectionScore]:
        """
        Aggregate evaluations by template section.

        Args:
            exchanges: All exchanges for the interview with section assignments.
            evaluations: Final evaluations for each exchange.
            template_weights: Section weights from template (e.g., {"resume": 10, "coding": 60}).

        Returns:
            List of SectionScore, one per section defined in template_weights.
        """
        # Build evaluation lookup: exchange_id -> evaluation
        evaluation_by_exchange: Dict[int, EvaluationSummaryDTO] = {
            ev.interview_exchange_id: ev for ev in evaluations
        }

        def normalize(section_name: str) -> str:
            raw = (section_name or "unknown").strip().lower()
            normalized = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
            if not normalized:
                return "unknown"
            compact = normalized.replace("_", "")
            return (
                SECTION_NAME_ALIASES.get(normalized)
                or SECTION_NAME_ALIASES.get(compact)
                or normalized
            )

        normalized_template_weights = {
            normalize(section_name): weight for section_name, weight in template_weights.items()
        }

        # Group exchanges by section and accumulate scores
        section_data: Dict[str, Dict] = {}
        for exchange in exchanges:
            section = normalize(exchange.section_name)
            if section not in section_data:
                section_data[section] = {"score": Decimal("0"), "count": 0}

            evaluation = evaluation_by_exchange.get(exchange.exchange_id)
            if evaluation:
                section_data[section]["score"] += evaluation.total_score
                section_data[section]["count"] += 1

        # Warn about sections in exchanges but not in template weights
        exchange_sections: Set[str] = {normalize(ex.section_name) for ex in exchanges}
        unmapped_sections = exchange_sections - set(normalized_template_weights.keys())
        if unmapped_sections:
            logger.warning(
                "Exchange sections not in template weights — excluded from aggregation",
                extra={"unmapped_sections": sorted(unmapped_sections)},
            )

        # Build results for every section in template_weights
        results: List[SectionScore] = []
        for section_name, weight in normalized_template_weights.items():
            data = section_data.get(section_name, {"score": Decimal("0"), "count": 0})
            results.append(
                SectionScore(
                    section_name=section_name,
                    score=data["score"],
                    weight=weight,
                    exchanges_evaluated=data["count"],
                )
            )

        logger.info(
            "Section aggregation complete",
            extra={
                "sections": len(results),
                "total_exchanges": sum(s.exchanges_evaluated for s in results),
            },
        )

        return results
