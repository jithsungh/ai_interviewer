"""
Evaluation Scoring Configuration

Centralized configuration for the scoring module.
Values can be overridden via environment variables.

Design:
- Pydantic BaseSettings for env var loading
- Sensible defaults for development
- Explicit validation rules
- No business logic
"""

from typing import Optional
import os

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is loaded so os.getenv() can read LLM_MODEL_* vars
load_dotenv()


class ScoringConfig(BaseSettings):
    """
    Scoring module configuration.
    
    Loads from environment variables with SCORING_ prefix.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="SCORING_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # AI Evaluation Settings
    evaluation_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Default LLM model for evaluation"
    )
    evaluation_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Low temperature for consistent scoring"
    )
    evaluation_max_tokens: int = Field(
        default=1000,
        gt=0,
        description="Max tokens for evaluation response"
    )
    evaluation_timeout_seconds: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Timeout for evaluation LLM call"
    )
    max_evaluation_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Max retries on evaluation failure"
    )

    # Prompt Size Controls (to keep requests compact/stateless)
    evaluation_include_transcript: bool = Field(
        default=False,
        description="Include transcript excerpt in scoring prompt"
    )
    evaluation_max_question_chars: int = Field(
        default=550,
        gt=0,
        description="Max question characters sent to LLM"
    )
    evaluation_max_answer_chars: int = Field(
        default=1800,
        gt=0,
        description="Max answer characters sent to LLM"
    )
    evaluation_max_transcript_chars: int = Field(
        default=900,
        gt=0,
        description="Max transcript characters sent to LLM"
    )
    evaluation_max_dimension_description_chars: int = Field(
        default=250,
        gt=0,
        description="Max description chars per dimension"
    )
    evaluation_max_dimension_criteria_chars: int = Field(
        default=220,
        gt=0,
        description="Max criteria chars per dimension"
    )
    
    # Retry Settings
    retry_base_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        description="Base delay for exponential backoff"
    )
    retry_max_delay_seconds: float = Field(
        default=8.0,
        gt=0,
        description="Maximum delay between retries"
    )
    
    # Score Precision
    score_decimal_places: int = Field(
        default=2,
        ge=0,
        le=4,
        description="Decimal places for score rounding"
    )
    
    # Score Normalization
    normalized_scale: int = Field(
        default=100,
        ge=1,
        description="Scale to normalize scores to (default 100-point scale)"
    )
    
    # Validation Settings
    require_justification: bool = Field(
        default=True,
        description="Require justification for all scores"
    )
    min_justification_length: int = Field(
        default=10,
        ge=0,
        description="Minimum characters for justification"
    )
    max_justification_length: int = Field(
        default=5000,
        gt=0,
        description="Maximum characters for justification"
    )
    
    # Prompt Template Settings
    evaluation_prompt_type: str = Field(
        default="evaluation_scoring",
        description="Prompt template type for evaluation"
    )
    
    # Scoring Version (for audit trail)
    scoring_version: str = Field(
        default="1.0.0",
        description="Scoring algorithm version"
    )

    @field_validator("retry_max_delay_seconds")
    @classmethod
    def validate_max_delay(cls, v: float, info) -> float:
        """Ensure max delay is greater than base delay."""
        base_delay = info.data.get("retry_base_delay_seconds", 1.0)
        if v < base_delay:
            raise ValueError("retry_max_delay_seconds must be >= retry_base_delay_seconds")
        return v


# Singleton instance
_config: Optional[ScoringConfig] = None


def get_scoring_config() -> ScoringConfig:
    """
    Get scoring configuration.
    
    Returns cached singleton but always applies fresh LLM_MODEL_EVALUATION override.
    This allows .env changes to take effect without app restart.
    """
    from app.shared.observability import get_context_logger
    logger = get_context_logger(__name__)
    
    global _config
    if _config is None:
        _config = ScoringConfig()
    
    # Always check for env var override (allows dynamic config changes)
    load_dotenv(override=True)  # Re-read .env on each call
    llm_model_eval = os.getenv("LLM_MODEL_EVALUATION")
    if llm_model_eval and llm_model_eval != _config.evaluation_model:
        logger.info(
            "Updating evaluation model from env var",
            extra={
                "old_model": _config.evaluation_model,
                "new_model": llm_model_eval,
            },
        )
        _config.evaluation_model = llm_model_eval
    
    return _config


def reset_config() -> None:
    """
    Reset configuration singleton.
    
    Used for testing with different configurations.
    """
    global _config
    _config = None
