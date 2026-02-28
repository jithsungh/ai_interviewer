"""
AI Cost Estimator

Provides cost estimation for AI provider calls based on model pricing tables.
Pricing is per 1K tokens in USD.

Design decisions:
- Pricing table is static (loaded at module import, not from DB)
- Unknown models return None (no fallback estimation)
- Cost rounded to 6 decimal places for precision
- Thread-safe (immutable pricing data)
"""

from typing import Optional, Dict, Tuple

from .contracts import CostEstimate


# Pricing per 1K tokens (USD)
# Source: Provider pricing pages as of 2026-02
# Format: model_id -> (prompt_cost_per_1k, completion_cost_per_1k)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # Groq Models (Development - very cost effective)
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
    "llama-3.1-70b-versatile": (0.00059, 0.00079),
    "llama-3.1-8b-instant": (0.00005, 0.00008),
    "mixtral-8x7b-32768": (0.00024, 0.00024),
    "gemma2-9b-it": (0.00020, 0.00020),

    # Gemini Models
    "gemini-2.0-flash-exp": (0.0, 0.0),  # Free during preview
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-flash-8b": (0.0000375, 0.00015),
    "text-embedding-004": (0.00001, 0.0),

    # Self-Hosted Embedding
    "all-mpnet-base-v2": (0.0, 0.0),  # Self-hosted, no API cost

    # OpenAI Models
    "gpt-4o": (0.0025, 0.01),
    "gpt-4": (0.03, 0.06),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4-turbo-preview": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "text-embedding-3-large": (0.00013, 0.0),
    "text-embedding-3-small": (0.00002, 0.0),
    "text-embedding-ada-002": (0.0001, 0.0),

    # Anthropic Models
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-haiku-20241022": (0.001, 0.005),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-3-sonnet-20240229": (0.003, 0.015),
    "claude-3-haiku-20240307": (0.00025, 0.00125),
}


class CostEstimator:
    """
    Estimates AI operation costs based on model pricing.

    Thread-safe: uses immutable pricing data.

    Usage:
        estimator = CostEstimator()
        cost = estimator.estimate_cost("gpt-4", prompt_tokens=1000, completion_tokens=500)
        if cost is not None:
            print(f"Estimated cost: ${cost.total_cost_usd:.4f}")
    """

    def __init__(self, pricing: Optional[Dict[str, Tuple[float, float]]] = None):
        """
        Initialize cost estimator.

        Args:
            pricing: Optional custom pricing table. Defaults to MODEL_PRICING.
        """
        self._pricing = pricing if pricing is not None else MODEL_PRICING

    def estimate_cost(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Optional[CostEstimate]:
        """
        Estimate cost for an AI operation.

        Args:
            model_id: Provider-specific model identifier
            prompt_tokens: Number of prompt/input tokens
            completion_tokens: Number of completion/output tokens

        Returns:
            CostEstimate if model has known pricing, None otherwise.

        Invariant:
            IF model_id has known pricing:
                cost = (prompt_tokens * prompt_rate / 1000) + (completion_tokens * completion_rate / 1000)
            ELSE:
                return None
        """
        pricing = self._pricing.get(model_id)
        if pricing is None:
            return None

        prompt_rate, completion_rate = pricing

        prompt_cost = (prompt_tokens * prompt_rate) / 1000.0
        completion_cost = (completion_tokens * completion_rate) / 1000.0
        total_cost = round(prompt_cost + completion_cost, 6)

        return CostEstimate(
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prompt_cost_per_1k=prompt_rate,
            completion_cost_per_1k=completion_rate,
            total_cost_usd=total_cost,
        )

    def get_known_models(self) -> list[str]:
        """Return list of models with known pricing."""
        return list(self._pricing.keys())

    def has_pricing(self, model_id: str) -> bool:
        """Check if model has known pricing."""
        return model_id in self._pricing
