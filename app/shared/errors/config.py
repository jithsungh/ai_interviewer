"""
Error Handling Configuration

Pydantic-based configuration for error handling behavior.
Controls logging, serialization, and WebSocket connection management.
"""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


# Helper to determine if .env file should be used
_ENV_FILE = None if os.getenv("TESTING") else ".env"


class ErrorConfig(BaseSettings):
    """
    Error handling configuration.
    
    Controls:
    - Logging behavior (client vs server errors)
    - Serialization (metadata inclusion, stack traces)
    - WebSocket connection management (fatal error behavior)
    """
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Logging
    log_client_errors: bool = Field(
        default=True,
        env="ERROR_LOG_CLIENT_ERRORS",
        description="Log 4xx errors (user errors)"
    )
    log_server_errors: bool = Field(
        default=True,
        env="ERROR_LOG_SERVER_ERRORS",
        description="Log 5xx errors (system errors)"
    )
    
    # Serialization
    include_error_metadata_in_response: bool = Field(
        default=True,
        env="ERROR_INCLUDE_METADATA",
        description="Include error metadata in API responses"
    )
    include_stack_trace_in_dev: bool = Field(
        default=True,
        env="ERROR_INCLUDE_STACK_TRACE_DEV",
        description="Include stack traces in development environment"
    )
    include_stack_trace_in_prod: bool = Field(
        default=False,
        env="ERROR_INCLUDE_STACK_TRACE_PROD",
        description="Include stack traces in production environment"
    )
    
    # WebSocket
    send_error_event_on_recoverable: bool = Field(
        default=True,
        env="ERROR_SEND_RECOVERABLE_EVENT",
        description="Send error event for recoverable errors (keep connection)"
    )
    close_connection_on_fatal: bool = Field(
        default=True,
        env="ERROR_CLOSE_ON_FATAL",
        description="Close WebSocket connection on fatal errors"
    )
    websocket_close_code_fatal: int = Field(
        default=1008,
        env="ERROR_WS_CLOSE_CODE_FATAL",
        description="WebSocket close code for fatal errors (1008 = Policy Violation)"
    )
    
    # Environment detection
    environment: Literal["dev", "staging", "prod"] = Field(
        default="dev",
        env="APP_ENV",
        description="Application environment"
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "prod"
    
    @property
    def include_stack_trace(self) -> bool:
        """Determine if stack traces should be included"""
        if self.is_production:
            return self.include_stack_trace_in_prod
        return self.include_stack_trace_in_dev


# Global configuration instance
# Can be imported and used throughout the application
error_config = ErrorConfig()
