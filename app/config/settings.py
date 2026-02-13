"""
Application Configuration Settings

Loads configuration from environment variables with sensible defaults.
Supports multiple environments (dev, staging, production).
"""

from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, RedisDsn


class Settings(BaseSettings):
    """Main application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = "AI Interviewer"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # API
    api_v1_prefix: str = "/api/v1"
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000"],
        env="ALLOWED_ORIGINS"
    )
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Database
    postgres_dsn: PostgresDsn = Field(..., env="DATABASE_URL")
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_echo: bool = False
    
    # Redis
    redis_dsn: RedisDsn = Field(..., env="REDIS_URL")
    redis_session_ttl: int = 3600  # 1 hour
    
    # Qdrant (Vector DB)
    qdrant_host: str = Field(default="localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, env="QDRANT_PORT")
    qdrant_grpc_port: int = Field(default=6334, env="QDRANT_GRPC_PORT")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    
    # AI/LLM Provider
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = "gpt-4"
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    llm_timeout: int = 30  # seconds
    llm_fallback_enabled: bool = True
    
    # Performance (NFR-1, NFR-2)
    response_timeout_ms: int = 300  # 300ms for non-media interactions
    ai_response_timeout_s: int = 5  # 5s for AI responses
    ai_fallback_timeout_s: int = 4  # Fallback trigger at 4s
    
    # Code Execution (FR-7.3, NFR-3)
    sandbox_init_timeout_s: int = 2
    sandbox_exec_timeout_s: int = 5
    sandbox_memory_limit_mb: int = 512
    sandbox_cpu_limit: float = 1.0
    
    # Proctoring (FR-9)
    proctoring_enabled: bool = True
    media_retention_days: int = 30
    
    # Observability
    log_level: str = "INFO"
    log_format: str = "json"
    enable_tracing: bool = False
    enable_metrics: bool = True
    
    # Multi-tenancy (NFR-7.1)
    enable_tenant_isolation: bool = True
    
    # Feature Flags
    enable_voice_interviews: bool = True
    enable_video_interviews: bool = False
    enable_code_quality_metrics: bool = False
    enable_adaptive_difficulty: bool = True


settings = Settings()
