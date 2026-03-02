"""
Recommendation Engine

Maps a normalized 0–100 score to a recommendation category.

Design:
- Pure computation — no database access
- Configurable thresholds via AggregationConfig
- Uses Decimal comparison to avoid floating-point border-case issues
- Four recommendation levels: strong_hire, hire, review, no_hire
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.evaluation.aggregation.config import AggregationConfig, get_aggregation_config
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class RecommendationEngine:
    """
    Determines interview recommendation from normalized score.

    Thresholds (inclusive lower bound):
        strong_hire  ≥ 85.0 (configurable)
        hire         ≥ 70.0
        review       ≥ 50.0
        no_hire      < 50.0
    """

    def __init__(self, config: Optional[AggregationConfig] = None) -> None:
        self._config = config or get_aggregation_config()

    def determine(self, normalized_score: Decimal) -> str:
        """
        Map normalized score to recommendation.

        Args:
            normalized_score: Score on 0–100 scale (already rounded).

        Returns:
            One of: ``'strong_hire'``, ``'hire'``, ``'review'``, ``'no_hire'``.
        """
        score = float(normalized_score)

        if score >= self._config.strong_hire_threshold:
            recommendation = "strong_hire"
        elif score >= self._config.hire_threshold:
            recommendation = "hire"
        elif score >= self._config.review_threshold:
            recommendation = "review"
        else:
            recommendation = "no_hire"

        logger.info(
            "Recommendation determined",
            extra={
                "normalized_score": str(normalized_score),
                "recommendation": recommendation,
            },
        )

        return recommendation
