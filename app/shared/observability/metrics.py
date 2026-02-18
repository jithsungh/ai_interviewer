"""
Metrics Instrumentation

Provides Prometheus-compatible metrics for counters, histograms, and gauges.
Protocol-agnostic metric helpers for tracking operations.
"""

from contextlib import contextmanager
from time import time
from functools import wraps
from typing import Callable, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY


class MetricsRegistry:
    """
    Central registry for application metrics.
    
    Provides standardized metrics for:
    - Interview operations
    - Question generation and retrieval
    - Evaluation
    - Code execution
    - WebSocket connections
    - AI provider calls
    
    All metrics are Prometheus-compatible.
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics registry.
        
        Args:
            registry: Prometheus registry (defaults to global REGISTRY)
        """
        self.registry = registry or REGISTRY
        
        # Interview metrics
        self.interview_exchanges_total = Counter(
            name="interview_exchanges_total",
            documentation="Total interview exchanges created",
            registry=self.registry
        )
        
        self.interview_duration_seconds = Histogram(
            name="interview_duration_seconds",
            documentation="Total interview duration",
            buckets=[60, 300, 600, 1200, 1800, 3600, 7200],  # 1min to 2hrs
            registry=self.registry
        )
        
        self.interview_pauses_total = Counter(
            name="interview_pauses_total",
            documentation="Total interview pauses",
            registry=self.registry
        )
        
        # Question metrics
        self.question_generation_duration_seconds = Histogram(
            name="question_generation_duration_seconds",
            documentation="Question generation latency",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry
        )
        
        self.question_retrieval_duration_seconds = Histogram(
            name="question_retrieval_duration_seconds",
            documentation="Qdrant retrieval latency",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        self.question_selection_fallback_total = Counter(
            name="question_selection_fallback_total",
            documentation="Fallback strategies used",
            labelnames=["reason"],
            registry=self.registry
        )
        
        # Evaluation metrics
        self.evaluation_duration_seconds = Histogram(
            name="evaluation_duration_seconds",
            documentation="Evaluation latency",
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.evaluation_score_distribution = Histogram(
            name="evaluation_score_distribution",
            documentation="Score distribution",
            buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            registry=self.registry
        )
        
        # Sandbox metrics
        self.sandbox_execution_duration_seconds = Histogram(
            name="sandbox_execution_duration_seconds",
            documentation="Sandbox execution time",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.sandbox_timeout_total = Counter(
            name="sandbox_timeout_total",
            documentation="Sandbox timeouts",
            registry=self.registry
        )
        
        self.sandbox_error_total = Counter(
            name="sandbox_error_total",
            documentation="Sandbox errors",
            labelnames=["error_type"],
            registry=self.registry
        )
        
        # WebSocket metrics
        self.websocket_connections_active = Gauge(
            name="websocket_connections_active",
            documentation="Active WebSocket connections",
            registry=self.registry
        )
        
        self.websocket_reconnects_total = Counter(
            name="websocket_reconnects_total",
            documentation="WebSocket reconnects",
            registry=self.registry
        )
        
        self.websocket_disconnect_total = Counter(
            name="websocket_disconnect_total",
            documentation="WebSocket disconnects",
            labelnames=["reason"],
            registry=self.registry
        )
        
        # AI provider metrics
        self.ai_provider_calls_total = Counter(
            name="ai_provider_calls_total",
            documentation="AI provider calls",
            labelnames=["provider", "model"],
            registry=self.registry
        )
        
        self.ai_provider_latency_seconds = Histogram(
            name="ai_provider_latency_seconds",
            documentation="AI provider latency",
            labelnames=["provider"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.ai_provider_tokens_total = Counter(
            name="ai_provider_tokens_total",
            documentation="Token usage",
            labelnames=["provider", "type"],  # type: prompt, completion
            registry=self.registry
        )
        
        self.ai_provider_cost_usd_total = Counter(
            name="ai_provider_cost_usd_total",
            documentation="Estimated cost in USD",
            labelnames=["provider"],
            registry=self.registry
        )


# Global metrics registry instance
metrics = MetricsRegistry()


@contextmanager
def track_latency(histogram: Histogram):
    """
    Context manager to track operation latency.
    
    Args:
        histogram: Prometheus Histogram to record latency
        
    Yields:
        None
        
    Example:
        with track_latency(metrics.question_generation_duration_seconds):
            question = generate_question(...)
    """
    start = time()
    try:
        yield
    finally:
        duration = time() - start
        histogram.observe(duration)


def track_operation(
    counter: Counter,
    histogram: Histogram,
    operation_name: Optional[str] = None
):
    """
    Decorator to track operation count and latency.
    
    Args:
        counter: Prometheus Counter to increment
        histogram: Prometheus Histogram to record latency
        operation_name: Optional operation name for logging
        
    Returns:
        Decorator function
        
    Example:
        @track_operation(
            counter=metrics.question_generation_total,
            histogram=metrics.question_generation_duration_seconds,
            operation_name="generate_question"
        )
        async def generate_question(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            counter.inc()

            start = time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time() - start
                histogram.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            counter.inc()

            start = time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time() - start
                histogram.observe(duration)
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
