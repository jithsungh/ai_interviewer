"""
AI Telemetry Module

Provides observability and cost tracking for all AI operations.

Core components:
- TelemetryTracker: Span-based telemetry tracking with non-blocking guarantees
- TelemetrySpan: Records individual AI operation metrics
- CostEstimator: Model pricing lookup and cost calculation
- MetricsAggregator: Aggregates telemetry records for reporting
- classify_error: Maps exceptions to telemetry error types

Reuses:
- TelemetryData from ai/llm/contracts (per-call telemetry DTO)
- metrics from shared/observability/metrics (Prometheus counters)
- Logging from shared/observability/logging (structured logging)

Design principle:
    Telemetry must be non-blocking and MUST be recorded even on failure.
    Telemetry failure MUST NOT propagate to calling code.
"""

from .tracker import TelemetryTracker, TelemetrySpan
from .cost import CostEstimator, MODEL_PRICING
from .errors import classify_error
from .aggregation import MetricsAggregator
from .contracts import (
    OperationType,
    AIErrorType,
    CostEstimate,
    AggregatedMetrics,
    OrganizationQuota,
)

# Re-export TelemetryData from ai/llm/contracts for convenience
from app.ai.llm.contracts import TelemetryData

__all__ = [
    # Core tracker
    "TelemetryTracker",
    "TelemetrySpan",
    # Cost estimation
    "CostEstimator",
    "MODEL_PRICING",
    # Error classification
    "classify_error",
    # Aggregation
    "MetricsAggregator",
    # Contracts
    "OperationType",
    "AIErrorType",
    "CostEstimate",
    "AggregatedMetrics",
    "OrganizationQuota",
    # Re-exported
    "TelemetryData",
]
