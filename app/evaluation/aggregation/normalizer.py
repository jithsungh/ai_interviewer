"""
Score Normalizer

Normalizes the weighted final score to a 0–100 scale.

Design:
- Pure computation — no database access
- Uses Decimal for precision (avoids floating-point edge cases)
- Clamps result to [0, 100]
- Configurable decimal places
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from app.evaluation.aggregation.config import AggregationConfig, get_aggregation_config
from app.evaluation.aggregation.schemas import SectionScore
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class ScoreNormalizer:
    """
    Normalizes final score to 0–100 scale.

    Formula:
        normalized = (final_score / max_possible_score) × 100

    Where:
        max_possible_score = Σ(max_per_exchange × exchanges_in_section × section_weight)
        max_per_exchange   = configured maximum total_score per exchange (default 100)
    """

    def __init__(self, config: Optional[AggregationConfig] = None) -> None:
        self._config = config or get_aggregation_config()

    def normalize(
        self,
        final_score: Decimal,
        section_scores: List[SectionScore],
    ) -> Decimal:
        """
        Normalize final score to 0–100 scale.

        Args:
            final_score: Weighted sum of section scores
                         (Σ section_score × section_weight).
            section_scores: Section breakdown used to derive max possible.

        Returns:
            Decimal clamped to [0, 100], rounded to configured decimal places.
        """
        max_per_exchange = Decimal(str(self._config.max_exchange_score))
        precision = self._config.score_decimal_places
        quantize_str = "0." + "0" * precision if precision > 0 else "1"

        # Calculate max possible score
        max_possible = Decimal("0")
        for section in section_scores:
            section_max = max_per_exchange * Decimal(section.exchanges_evaluated)
            weighted_section_max = section_max * Decimal(section.weight)
            max_possible += weighted_section_max

        if max_possible == 0:
            logger.warning(
                "Max possible score is 0 — returning normalized score of 0",
                extra={"final_score": str(final_score)},
            )
            return Decimal("0").quantize(Decimal(quantize_str))

        # Normalize
        normalized = (final_score / max_possible) * Decimal("100")

        # Clamp to [0, 100]
        if normalized > Decimal("100"):
            logger.warning(
                "Final score exceeds max possible — clamping to 100",
                extra={
                    "final_score": str(final_score),
                    "max_possible": str(max_possible),
                    "raw_normalized": str(normalized),
                },
            )
            normalized = Decimal("100")
        elif normalized < Decimal("0"):
            normalized = Decimal("0")

        return normalized.quantize(Decimal(quantize_str))


def calculate_final_score(
    section_scores: List[SectionScore],
    decimal_places: int = 2,
) -> Decimal:
    """
    Calculate weighted final score from section scores.

    Formula: Σ (section_score × section_weight)

    This is a standalone convenience function used by the aggregation service.

    Args:
        section_scores: List of section score breakdowns.
        decimal_places: Rounding precision.

    Returns:
        Decimal rounded to specified places.
    """
    quantize_str = "0." + "0" * decimal_places if decimal_places > 0 else "1"

    total = Decimal("0")
    for section in section_scores:
        weighted = section.score * Decimal(section.weight)
        total += weighted

    return total.quantize(Decimal(quantize_str))
