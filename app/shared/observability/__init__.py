"""
Shared Observability Module

Provides structured logging, distributed tracing, metrics instrumentation,
and AI telemetry for the entire application.

This module is pure infrastructure - NO business logic, NO database operations.
"""

from .config import ObservabilityConfig
from .logging import (
    StructuredFormatter,
    ContextLogger,
    configure_structured_logging,
    get_context_logger,
)
from .redaction import (
    redact_sensitive_data,
    mask_token,
    SENSITIVE_FIELDS,
)
from .tracing import (
    TraceContext,
    generate_request_id,
    generate_connection_id,
    generate_session_id,
    extract_request_id,
    RequestIDMiddleware,
)
from .metrics import (
    track_latency,
    track_operation,
    MetricsRegistry,
)
from .telemetry import (
    AITelemetry,
    track_ai_call,
)

__all__ = [
    # Config
    "ObservabilityConfig",
    # Logging
    "StructuredFormatter",
    "ContextLogger",
    "configure_structured_logging",
    "get_context_logger",
    # Redaction
    "redact_sensitive_data",
    "mask_token",
    "SENSITIVE_FIELDS",
    # Tracing
    "TraceContext",
    "generate_request_id",
    "generate_connection_id",
    "generate_session_id",
    "extract_request_id",
    "RequestIDMiddleware",
    # Metrics
    "track_latency",
    "track_operation",
    "MetricsRegistry",
    # Telemetry
    "AITelemetry",
    "track_ai_call",
]
