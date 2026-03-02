"""
Proctoring Risk Adjuster

Adjusts the interview recommendation based on proctoring risk level.

Design:
- Feature-flagged: no-op when ENABLE_PROCTORING_INFLUENCE is false
- Downgrades recommendation by one level for high/critical risk
- Pure computation — proctoring risk data is passed in
- Graceful when proctoring module is not yet implemented
"""

from __future__ import annotations

from typing import Optional

from app.evaluation.aggregation.config import AggregationConfig, get_aggregation_config
from app.evaluation.aggregation.schemas import ProctoringRiskDTO
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)

# Recommendation downgrade path
_DOWNGRADE_MAP = {
    "strong_hire": "hire",
    "hire": "review",
    "review": "no_hire",
    "no_hire": "no_hire",  # Cannot downgrade further
}


class ProctoringAdjuster:
    """
    Adjusts recommendation based on proctoring risk.

    When enabled and risk is ``high`` or ``critical``,
    the recommendation is downgraded by one level.
    """

    def __init__(self, config: Optional[AggregationConfig] = None) -> None:
        self._config = config or get_aggregation_config()

    def adjust(
        self,
        recommendation: str,
        proctoring_risk: Optional[ProctoringRiskDTO],
    ) -> str:
        """
        Adjust recommendation for proctoring risk.

        Args:
            recommendation: Initial recommendation from score mapping.
            proctoring_risk: Proctoring risk assessment (None if unavailable).

        Returns:
            Adjusted recommendation (may be same as input).
        """
        if not self._config.enable_proctoring_influence:
            return recommendation

        if proctoring_risk is None:
            logger.debug("No proctoring risk data available — skipping adjustment")
            return recommendation

        if (
            proctoring_risk.overall_risk in ("high", "critical")
            and self._config.high_risk_downgrade
        ):
            adjusted = _DOWNGRADE_MAP.get(recommendation, recommendation)
            logger.info(
                "Proctoring risk adjustment applied",
                extra={
                    "original_recommendation": recommendation,
                    "adjusted_recommendation": adjusted,
                    "risk_level": proctoring_risk.overall_risk,
                    "total_events": proctoring_risk.total_events,
                    "high_severity_count": proctoring_risk.high_severity_count,
                },
            )
            return adjusted

        return recommendation
