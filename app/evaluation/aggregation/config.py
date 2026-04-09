"""
Evaluation Aggregation Configuration

Centralized configuration for the aggregation module.
Values can be overridden via environment variables with AGGREGATION_ prefix.

Design:
- Pydantic BaseSettings for env var loading
- Sensible defaults for development
- Threshold validation to prevent misconfiguration
- No business logic
- LLM_MODEL_REPORT_GENERATION env var provides dynamic model override
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Ensure .env is loaded so os.getenv() can read LLM_MODEL_* vars
load_dotenv()


from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AggregationConfig(BaseSettings):
    """
    Aggregation module configuration.

    Loads from environment variables with AGGREGATION_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGGREGATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Recommendation Thresholds ──────────────────────────────────────
    strong_hire_threshold: float = Field(
        default=85.0,
        ge=0.0,
        le=100.0,
        description="Minimum normalized score for strong_hire",
    )
    hire_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum normalized score for hire",
    )
    review_threshold: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
        description="Minimum normalized score for review",
    )

    # ── Proctoring Influence ───────────────────────────────────────────
    enable_proctoring_influence: bool = Field(
        default=False,
        description="Apply proctoring risk to recommendation",
    )
    high_risk_downgrade: bool = Field(
        default=True,
        description="Downgrade recommendation by one level for high/critical risk",
    )

    # ── Summary Generation ─────────────────────────────────────────────
    summary_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="LLM model for summary generation",
    )
    summary_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Temperature for summary generation",
    )
    summary_max_tokens: int = Field(
        default=1300,
        gt=0,
        description="Max tokens for summary response",
    )
    summary_timeout_seconds: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Timeout for summary LLM call",
    )
    summary_max_exchanges_in_prompt: int = Field(
        default=12,
        gt=0,
        description="Maximum exchange rows included in summary prompt",
    )
    summary_max_question_chars: int = Field(
        default=180,
        gt=0,
        description="Max question chars per exchange in summary prompt",
    )
    summary_max_response_chars: int = Field(
        default=320,
        gt=0,
        description="Max response chars per exchange in summary prompt",
    )
    summary_max_dimension_scores_per_exchange: int = Field(
        default=4,
        gt=0,
        description="Maximum dimension score items per exchange in summary prompt",
    )

    # ── Score Precision ────────────────────────────────────────────────
    score_decimal_places: int = Field(
        default=2,
        ge=0,
        le=4,
        description="Decimal places for score rounding",
    )

    # ── Max Exchange Score ─────────────────────────────────────────────
    max_exchange_score: float = Field(
        default=100.0,
        gt=0.0,
        description="Maximum possible total_score per exchange (from scoring module normalization)",
    )

    # ── Scoring Version ────────────────────────────────────────────────
    scoring_version: str = Field(
        default="1.0.0",
        description="Aggregation algorithm version for audit trail",
    )

    # ── Validators ─────────────────────────────────────────────────────

    @field_validator("hire_threshold")
    @classmethod
    def validate_hire_below_strong_hire(cls, v: float, info) -> float:
        """Hire threshold must be strictly below strong_hire threshold."""
        strong_hire = info.data.get("strong_hire_threshold", 85.0)
        if v >= strong_hire:
            raise ValueError(
                f"hire_threshold ({v}) must be < strong_hire_threshold ({strong_hire})"
            )
        return v

    @field_validator("review_threshold")
    @classmethod
    def validate_review_below_hire(cls, v: float, info) -> float:
        """Review threshold must be strictly below hire threshold."""
        hire = info.data.get("hire_threshold", 70.0)
        if v >= hire:
            raise ValueError(
                f"review_threshold ({v}) must be < hire_threshold ({hire})"
            )
        return v


# ── Singleton ──────────────────────────────────────────────────────────

_config: Optional[AggregationConfig] = None


def get_aggregation_config() -> AggregationConfig:
    """
    Get aggregation configuration.

    Returns cached singleton but always applies fresh LLM_MODEL_REPORT_GENERATION override.
    This allows .env changes to take effect without app restart.
    """
    from app.shared.observability import get_context_logger
    logger = get_context_logger(__name__)
    
    global _config
    if _config is None:
        _config = AggregationConfig()
    
    # Always check for env var override (allows dynamic config changes)
    load_dotenv(override=True)  # Re-read .env on each call
    llm_model_report = os.getenv("LLM_MODEL_REPORT_GENERATION")
    if llm_model_report and llm_model_report != _config.summary_model:
        logger.info(
            "Updating summary model from env var",
            extra={
                "old_model": _config.summary_model,
                "new_model": llm_model_report,
            },
        )
        _config.summary_model = llm_model_report
    
    return _config


def reset_config() -> None:
    """
    Reset configuration singleton.

    Used for testing with different configurations.
    """
    global _config
    _config = None
