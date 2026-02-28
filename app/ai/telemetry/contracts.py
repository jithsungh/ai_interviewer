"""
AI Telemetry Contracts

Data structures for telemetry operations.
Reuses TelemetryData from ai/llm/contracts for per-call telemetry.
Defines additional structures for cost estimation and aggregation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class OperationType(str, Enum):
    """
    AI operation types tracked by telemetry.

    Maps to the operation_type field in telemetry records.
    """
    QUESTION_GENERATION = "question_generation"
    EVALUATION = "evaluation"
    RESUME_PARSING = "resume_parsing"
    JD_PARSING = "jd_parsing"
    REPORT_GENERATION = "report_generation"
    EMBEDDING = "embedding"
    TRANSCRIPTION = "transcription"
    TEXT_GENERATION = "text_generation"
    CLARIFICATION = "clarification"


class AIErrorType(str, Enum):
    """
    Classified AI error types for telemetry.

    Used by classify_error() to normalize provider-specific errors.
    """
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    SCHEMA_VALIDATION = "schema_validation"
    CONTENT_FILTER = "content_filter"
    CONTEXT_LENGTH = "context_length"
    MODEL_NOT_FOUND = "model_not_found"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class CostEstimate:
    """
    Cost estimation result for an AI operation.

    Returned by CostEstimator.estimate_cost().
    All monetary values in USD.
    """
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    total_cost_usd: float
    currency: str = "USD"

    def __post_init__(self):
        """Validate cost estimate"""
        if self.total_cost_usd < 0:
            raise ValueError("total_cost_usd cannot be negative")
        if self.prompt_tokens < 0:
            raise ValueError("prompt_tokens cannot be negative")
        if self.completion_tokens < 0:
            raise ValueError("completion_tokens cannot be negative")


@dataclass
class AggregatedMetrics:
    """
    Aggregated telemetry metrics for a time period.

    Used for reporting and cost tracking.
    """
    time_period: str  # "hour" | "day" | "month"
    organization_id: Optional[int] = None
    model_id: Optional[str] = None  # None = all models

    # Aggregated values
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Latency percentiles (milliseconds)
    p50_latency_ms: int = 0
    p95_latency_ms: int = 0
    p99_latency_ms: int = 0

    # Error breakdown
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Validate aggregated metrics"""
        valid_periods = {"hour", "day", "month"}
        if self.time_period not in valid_periods:
            raise ValueError(
                f"time_period must be one of {valid_periods}, got '{self.time_period}'"
            )
        if self.total_requests < 0:
            raise ValueError("total_requests cannot be negative")
        if self.total_cost_usd < 0:
            raise ValueError("total_cost_usd cannot be negative")


@dataclass
class OrganizationQuota:
    """
    Organization-level AI usage quota.

    Used for cost allocation and limit enforcement.
    """
    organization_id: int
    monthly_cost_limit_usd: float
    monthly_token_limit: int
    daily_request_limit: int

    # Current usage (updated periodically)
    current_month_cost_usd: float = 0.0
    current_month_tokens: int = 0
    current_day_requests: int = 0

    def is_cost_exceeded(self) -> bool:
        """Check if monthly cost limit is exceeded"""
        return self.current_month_cost_usd >= self.monthly_cost_limit_usd

    def is_token_limit_exceeded(self) -> bool:
        """Check if monthly token limit is exceeded"""
        return self.current_month_tokens >= self.monthly_token_limit

    def is_daily_request_limit_exceeded(self) -> bool:
        """Check if daily request limit is exceeded"""
        return self.current_day_requests >= self.daily_request_limit

    def is_any_limit_exceeded(self) -> bool:
        """Check if any quota limit is exceeded"""
        return (
            self.is_cost_exceeded()
            or self.is_token_limit_exceeded()
            or self.is_daily_request_limit_exceeded()
        )
