"""
AI Telemetry Metrics Aggregation

Aggregates telemetry records into summary metrics for reporting.
Used for cost tracking, usage analytics, and SLA monitoring.

Design decisions:
- Pure computation (no DB access, no side effects)
- Accepts lists of TelemetryData — caller handles data retrieval
- Percentile calculation uses sorted-list interpolation
- Thread-safe (stateless functions)
"""

import math
from typing import List, Optional, Dict

from app.ai.llm.contracts import TelemetryData
from .contracts import AggregatedMetrics


class MetricsAggregator:
    """
    Aggregates lists of TelemetryData into summary metrics.

    Pure computation — no database queries, no side effects.
    Caller is responsible for filtering and providing data.

    Usage:
        aggregator = MetricsAggregator()

        # Get telemetry records from some source
        records = [...]

        hourly = aggregator.aggregate(records, time_period="hour")
        daily = aggregator.aggregate(records, time_period="day")
    """

    def aggregate(
        self,
        records: List[TelemetryData],
        time_period: str,
        organization_id: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> AggregatedMetrics:
        """
        Aggregate telemetry records into summary metrics.

        Args:
            records: List of TelemetryData to aggregate.
            time_period: Aggregation period ("hour", "day", "month").
            organization_id: Optional filter for organization-level reporting.
            model_id: Optional filter for model-level reporting.

        Returns:
            AggregatedMetrics with summary statistics.
        """
        if not records:
            return AggregatedMetrics(
                time_period=time_period,
                organization_id=organization_id,
                model_id=model_id,
            )

        # Filter if criteria provided
        filtered = records
        if organization_id is not None:
            filtered = [
                r for r in filtered if r.organization_id == organization_id
            ]
        if model_id is not None:
            filtered = [r for r in filtered if r.model_id == model_id]

        if not filtered:
            return AggregatedMetrics(
                time_period=time_period,
                organization_id=organization_id,
                model_id=model_id,
            )

        # Count requests
        total = len(filtered)
        successful = sum(1 for r in filtered if r.success)
        failed = total - successful

        # Sum tokens
        total_tokens = sum(r.total_tokens for r in filtered)

        # Sum cost
        total_cost = sum(
            r.estimated_cost_usd for r in filtered
            if r.estimated_cost_usd is not None
        )

        # Latency percentiles
        latencies = sorted(r.latency_ms for r in filtered)
        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        p99 = _percentile(latencies, 99)

        # Error breakdown
        errors_by_type: Dict[str, int] = {}
        for r in filtered:
            if not r.success and r.error_type:
                errors_by_type[r.error_type] = (
                    errors_by_type.get(r.error_type, 0) + 1
                )

        return AggregatedMetrics(
            time_period=time_period,
            organization_id=organization_id,
            model_id=model_id,
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            errors_by_type=errors_by_type,
        )

    def aggregate_hourly(
        self,
        records: List[TelemetryData],
        organization_id: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> AggregatedMetrics:
        """Convenience: aggregate with time_period='hour'."""
        return self.aggregate(
            records, time_period="hour",
            organization_id=organization_id,
            model_id=model_id,
        )

    def aggregate_daily(
        self,
        records: List[TelemetryData],
        organization_id: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> AggregatedMetrics:
        """Convenience: aggregate with time_period='day'."""
        return self.aggregate(
            records, time_period="day",
            organization_id=organization_id,
            model_id=model_id,
        )

    def aggregate_monthly(
        self,
        records: List[TelemetryData],
        organization_id: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> AggregatedMetrics:
        """Convenience: aggregate with time_period='month'."""
        return self.aggregate(
            records, time_period="month",
            organization_id=organization_id,
            model_id=model_id,
        )


def _percentile(sorted_values: List[int], pct: int) -> int:
    """
    Calculate percentile from a sorted list of integers.

    Uses linear interpolation between adjacent values.

    Args:
        sorted_values: Pre-sorted list of integer values.
        pct: Percentile to calculate (0-100).

    Returns:
        Percentile value as integer.
    """
    if not sorted_values:
        return 0

    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    # Calculate index using percentile rank
    rank = (pct / 100.0) * (n - 1)
    lower = int(math.floor(rank))
    upper = min(lower + 1, n - 1)
    fraction = rank - lower

    # Linear interpolation
    result = sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )
    return int(round(result))
