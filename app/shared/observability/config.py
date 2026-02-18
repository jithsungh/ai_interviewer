"""
Observability Configuration

Pydantic-based configuration for logging, tracing, metrics, and telemetry.
Follows the same pattern as DatabaseSettings, RedisSettings, etc.
"""

from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


# Helper to determine if .env file should be used
_ENV_FILE = None if os.getenv("TESTING") else ".env"


class ObservabilityConfig(BaseSettings):
    """
    Observability configuration for logging, tracing, metrics, and telemetry.
    
    Load from environment variables with defaults.
    """
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        env="LOG_LEVEL"
    )
    enable_structured_logging: bool = Field(
        default=True,
        env="ENABLE_STRUCTURED_LOGGING"
    )
    enable_console_logging: bool = Field(
        default=True,
        env="ENABLE_CONSOLE_LOGGING"
    )
    enable_file_logging: bool = Field(
        default=False,
        env="ENABLE_FILE_LOGGING"
    )
    log_file_path: str = Field(
        default="/var/log/app/app.log",
        env="LOG_FILE_PATH"
    )
    
    # Redaction
    enable_sensitive_redaction: bool = Field(
        default=True,
        env="ENABLE_SENSITIVE_REDACTION"
    )
    redact_candidate_answers: bool = Field(
        default=False,
        env="REDACT_CANDIDATE_ANSWERS"
    )
    redact_test_case_outputs: bool = Field(
        default=True,
        env="REDACT_TEST_CASE_OUTPUTS"
    )
    
    # Tracing
    enable_distributed_tracing: bool = Field(
        default=True,
        env="ENABLE_DISTRIBUTED_TRACING"
    )
    trace_sample_rate: float = Field(
        default=1.0,
        env="TRACE_SAMPLE_RATE",
        ge=0.0,
        le=1.0
    )
    
    # Metrics
    enable_metrics: bool = Field(
        default=True,
        env="ENABLE_METRICS"
    )
    metrics_port: int = Field(
        default=9090,
        env="METRICS_PORT",
        ge=1024,
        le=65535
    )
    
    # AI Telemetry
    enable_ai_telemetry: bool = Field(
        default=True,
        env="ENABLE_AI_TELEMETRY"
    )
    log_ai_prompts_in_dev: bool = Field(
        default=True,
        env="LOG_AI_PROMPTS_IN_DEV"
    )
    log_ai_prompts_in_prod: bool = Field(
        default=False,
        env="LOG_AI_PROMPTS_IN_PROD"
    )
    
    @field_validator("trace_sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Ensure sample rate is between 0 and 1"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("trace_sample_rate must be between 0.0 and 1.0")
        return v
    
    @field_validator("metrics_port")
    @classmethod
    def validate_metrics_port(cls, v: int) -> int:
        """Ensure metrics port is in valid range"""
        if not 1024 <= v <= 65535:
            raise ValueError("metrics_port must be between 1024 and 65535")
        return v
    
    def should_log_ai_prompts(self, app_env: str) -> bool:
        """
        Determine if AI prompts should be logged based on environment.
        
        Args:
            app_env: Application environment ('dev', 'staging', 'prod')
            
        Returns:
            True if prompts should be logged
        """
        if app_env == "prod":
            return self.log_ai_prompts_in_prod
        return self.log_ai_prompts_in_dev
