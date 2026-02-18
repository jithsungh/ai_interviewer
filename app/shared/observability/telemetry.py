"""
AI Telemetry

Provides telemetry tracking for AI provider calls (OpenAI, Anthropic, etc.).
Tracks tokens, latency, costs, and errors for observability.
"""

from dataclasses import dataclass, field
from contextlib import contextmanager
from time import time
from typing import Optional

from .logging import ContextLogger
from .metrics import metrics


@dataclass
class AITelemetry:
    """
    Telemetry data for AI provider call.
    
    Tracks:
    - Provider and model
    - Token usage (prompt + completion)
    - Latency
    - Success/failure
    - Cost estimate
    
    Usage:
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=50,
            latency_seconds=2.5,
            success=True,
            cost_estimate_usd=0.0065
        )
        
        telemetry.log(logger)
        telemetry.emit_metrics()
    """
    provider: str           # 'openai', 'anthropic', 'azure', etc.
    model: str              # 'gpt-4', 'claude-3-opus', etc.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_seconds: float = 0.0
    success: bool = False
    error_type: Optional[str] = None
    cost_estimate_usd: float = 0.0
    
    # Optional metadata
    metadata: dict = field(default_factory=dict)

    def total_tokens(self) -> int:
        """Calculate total tokens used"""
        return self.prompt_tokens + self.completion_tokens

    def log(self, logger: ContextLogger):
        """
        Log AI telemetry to structured logs.
        
        Args:
            logger: ContextLogger for structured logging
        """
        logger.info(
            f"AI call: {self.provider}/{self.model}",
            event_type="ai_call",
            latency_ms=self.latency_seconds * 1000,
            metadata={
                "provider": self.provider,
                "model": self.model,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens(),
                "success": self.success,
                "error_type": self.error_type,
                "cost_estimate_usd": self.cost_estimate_usd,
                **self.metadata,
            }
        )

    def emit_metrics(self):
        """
        Emit Prometheus metrics for AI telemetry.
        
        Records:
        - Total calls (counter)
        - Latency (histogram)
        - Token usage (counter)
        - Cost (counter)
        """
        # Increment call counter
        metrics.ai_provider_calls_total.labels(
            provider=self.provider,
            model=self.model
        ).inc()

        # Record latency
        metrics.ai_provider_latency_seconds.labels(
            provider=self.provider
        ).observe(self.latency_seconds)

        # Record tokens (only on success)
        if self.success:
            metrics.ai_provider_tokens_total.labels(
                provider=self.provider,
                type="prompt"
            ).inc(self.prompt_tokens)

            metrics.ai_provider_tokens_total.labels(
                provider=self.provider,
                type="completion"
            ).inc(self.completion_tokens)

            # Record cost
            metrics.ai_provider_cost_usd_total.labels(
                provider=self.provider
            ).inc(self.cost_estimate_usd)


@contextmanager
def track_ai_call(
    provider: str,
    model: str,
    logger: ContextLogger
):
    """
    Context manager to track AI provider call.
    
    Automatically:
    - Measures latency
    - Logs telemetry
    - Emits metrics
    - Handles errors
    
    Args:
        provider: AI provider name ('openai', 'anthropic', etc.)
        model: Model name ('gpt-4', 'claude-3-opus', etc.)
        logger: ContextLogger for structured logging
        
    Yields:
        AITelemetry object to populate with token counts and cost
        
    Example:
        async def call_openai(prompt: str, logger: ContextLogger):
            with track_ai_call("openai", "gpt-4", logger) as telemetry:
                response = await openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Populate telemetry
                telemetry.prompt_tokens = response.usage.prompt_tokens
                telemetry.completion_tokens = response.usage.completion_tokens
                telemetry.cost_estimate_usd = calculate_cost(
                    model="gpt-4",
                    prompt_tokens=telemetry.prompt_tokens,
                    completion_tokens=telemetry.completion_tokens
                )
                
                return response
    """
    start = time()
    telemetry = AITelemetry(
        provider=provider,
        model=model,
        prompt_tokens=0,
        completion_tokens=0,
        latency_seconds=0,
        success=False,
        error_type=None,
        cost_estimate_usd=0
    )

    try:
        yield telemetry
        telemetry.success = True
    except Exception as e:
        telemetry.error_type = type(e).__name__
        raise
    finally:
        telemetry.latency_seconds = time() - start
        telemetry.log(logger)
        telemetry.emit_metrics()


def calculate_openai_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """
    Calculate estimated cost for OpenAI API call.
    
    Pricing as of 2024 (subject to change):
    - GPT-4: $30/1M input, $60/1M output
    - GPT-4-turbo: $10/1M input, $30/1M output
    - GPT-3.5-turbo: $0.50/1M input, $1.50/1M output
    
    Args:
        model: OpenAI model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        
    Returns:
        Estimated cost in USD
        
    Note:
        This is an ESTIMATE. Actual costs should be tracked from OpenAI billing.
    """
    pricing = {
        "gpt-4": (30.0 / 1_000_000, 60.0 / 1_000_000),
        "gpt-4-turbo": (10.0 / 1_000_000, 30.0 / 1_000_000),
        "gpt-4-turbo-preview": (10.0 / 1_000_000, 30.0 / 1_000_000),
        "gpt-3.5-turbo": (0.50 / 1_000_000, 1.50 / 1_000_000),
    }
    
    # Default to GPT-4 pricing if model not found
    input_cost_per_token, output_cost_per_token = pricing.get(
        model,
        pricing["gpt-4"]
    )
    
    return (prompt_tokens * input_cost_per_token) + (completion_tokens * output_cost_per_token)


def calculate_anthropic_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """
    Calculate estimated cost for Anthropic API call.
    
    Pricing as of 2024 (subject to change):
    - Claude 3 Opus: $15/1M input, $75/1M output
    - Claude 3 Sonnet: $3/1M input, $15/1M output
    - Claude 3 Haiku: $0.25/1M input, $1.25/1M output
    
    Args:
        model: Anthropic model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        
    Returns:
        Estimated cost in USD
        
    Note:
        This is an ESTIMATE. Actual costs should be tracked from Anthropic billing.
    """
    pricing = {
        "claude-3-opus": (15.0 / 1_000_000, 75.0 / 1_000_000),
        "claude-3-sonnet": (3.0 / 1_000_000, 15.0 / 1_000_000),
        "claude-3-haiku": (0.25 / 1_000_000, 1.25 / 1_000_000),
    }
    
    # Default to Opus pricing if model not found
    input_cost_per_token, output_cost_per_token = pricing.get(
        model,
        pricing["claude-3-opus"]
    )
    
    return (prompt_tokens * input_cost_per_token) + (completion_tokens * output_cost_per_token)
