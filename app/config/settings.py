"""
Application Configuration Settings

Loads configuration from environment variables with sensible defaults.
Supports multiple environments (dev, staging, production).
"""

from typing import Optional, List, Literal
from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
import os

logger = logging.getLogger(__name__)

# Helper to determine if .env file should be used
_ENV_FILE = None if os.getenv("TESTING") else ".env"


# ====================
# Application Settings
# ====================
class AppSettings(BaseSettings):
    """Core application configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    app_env: Literal["dev", "staging", "prod"] = Field(default="dev", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    app_name: str = Field(default="AI Interviewer API", env="APP_NAME")
    api_version: str = Field(default="1.0.0", env="API_VERSION")
    base_url: str = Field(default="http://localhost:8000", env="BASE_URL")
    
    @model_validator(mode='after')
    def validate_production_settings(self):
        if self.app_env == "prod":
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if not self.base_url.startswith("https://"):
                logger.warning("BASE_URL should use HTTPS in production")
        return self


# ====================
# Database Settings
# ====================
class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    database_url: str = Field(..., env="DATABASE_URL")
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    db_echo: bool = Field(default=False, env="DB_ECHO")
    
    @model_validator(mode='after')
    def validate_pool_settings(self):
        if self.db_pool_size <= 0:
            raise ValueError("DB_POOL_SIZE must be > 0")
        if self.db_pool_timeout <= 0:
            raise ValueError("DB_POOL_TIMEOUT must be > 0")
        return self


# ====================
# Redis Settings
# ====================
class RedisSettings(BaseSettings):
    """Redis configuration for sessions and caching"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    redis_url: str = Field(..., env="REDIS_URL")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_session_ttl: int = Field(default=3600, env="REDIS_SESSION_TTL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")


# ====================
# Qdrant Settings
# ====================
class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    qdrant_url: str = Field(..., env="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="interview_questions", env="QDRANT_COLLECTION_NAME")
    qdrant_embedding_dim: int = Field(default=768, env="QDRANT_EMBEDDING_DIM")
    
    def get_collection_name_with_env(self, app_env: str) -> str:
        """Return collection name with environment suffix"""
        if app_env == "dev":
            return f"{self.qdrant_collection_name}_dev"
        elif app_env == "staging":
            return f"{self.qdrant_collection_name}_staging"
        return self.qdrant_collection_name


# ====================
# LLM Provider Settings
# ====================
class LLMSettings(BaseSettings):
    """LLM provider configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    default_llm_provider: Literal["openai", "anthropic", "groq"] = Field(default="groq", env="DEFAULT_LLM_PROVIDER")
    
    # API Keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, env="GROQ_API_KEY")
    
    # Model routing by use case
    llm_model_question_generation: str = Field(default="gpt-oss-120b", env="LLM_MODEL_QUESTION_GENERATION")
    llm_model_evaluation: str = Field(default="gpt-oss-120b", env="LLM_MODEL_EVALUATION")
    llm_model_resume_parsing: str = Field(default="gpt-oss-120b", env="LLM_MODEL_RESUME_PARSING")
    llm_model_report_generation: str = Field(default="gpt-oss-120b", env="LLM_MODEL_REPORT_GENERATION")
    
    # Model parameters
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    llm_timeout_seconds: int = Field(default=30, env="LLM_TIMEOUT_SECONDS")
    
    @model_validator(mode='after')
    def validate_api_keys(self):
        if self.default_llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required when DEFAULT_LLM_PROVIDER=openai")
        if self.default_llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required when DEFAULT_LLM_PROVIDER=anthropic")
        if self.default_llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY required when DEFAULT_LLM_PROVIDER=groq")
        return self


# ====================
# Sandbox Settings
# ====================
class SandboxSettings(BaseSettings):
    """Code execution sandbox configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Docker images
    sandbox_image_cpp: str = Field(default="code-sandbox-cpp:latest", env="SANDBOX_IMAGE_CPP")
    sandbox_image_java: str = Field(default="code-sandbox-java:latest", env="SANDBOX_IMAGE_JAVA")
    sandbox_image_python: str = Field(default="code-sandbox-python:latest", env="SANDBOX_IMAGE_PYTHON")
    
    # Resource limits
    sandbox_time_limit_ms: int = Field(default=2000, env="SANDBOX_TIME_LIMIT_MS")
    sandbox_memory_limit_kb: int = Field(default=262144, env="SANDBOX_MEMORY_LIMIT_KB")  # 256MB
    sandbox_process_limit: int = Field(default=1, env="SANDBOX_PROCESS_LIMIT")
    sandbox_max_output_size: int = Field(default=1048576, env="SANDBOX_MAX_OUTPUT_SIZE")  # 1MB
    
    # Security
    sandbox_network_disabled: bool = Field(default=True, env="SANDBOX_NETWORK_DISABLED")
    sandbox_seccomp_profile: Optional[str] = Field(default=None, env="SANDBOX_SECCOMP_PROFILE")
    
    @model_validator(mode='after')
    def validate_resource_limits(self):
        if self.sandbox_time_limit_ms < 100:
            raise ValueError("SANDBOX_TIME_LIMIT_MS must be >= 100ms")
        if self.sandbox_memory_limit_kb < 4096:
            raise ValueError("SANDBOX_MEMORY_LIMIT_KB must be >= 4MB")
        return self


# ====================
# Security Settings
# ====================
class SecuritySettings(BaseSettings):
    """Security and authentication configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # JWT
    jwt_algorithm: Literal["RS256", "HS256"] = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_public_key_path: Optional[str] = Field(default=None, env="JWT_PUBLIC_KEY_PATH")
    jwt_private_key_path: Optional[str] = Field(default=None, env="JWT_PRIVATE_KEY_PATH")
    jwt_secret_key: Optional[str] = Field(default=None, env="JWT_SECRET_KEY")
    
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Password hashing
    password_hash_algorithm: Literal["bcrypt", "argon2id"] = Field(default="bcrypt", env="PASSWORD_HASH_ALGORITHM")
    password_hash_rounds: int = Field(default=12, env="PASSWORD_HASH_ROUNDS")
    
    # Security headers
    enable_secure_headers: bool = Field(default=True, env="ENABLE_SECURE_HEADERS")
    allowed_hosts: List[str] = Field(default=["localhost"], env="ALLOWED_HOSTS")
    
    @model_validator(mode='after')
    def validate_jwt_config(self):
        if self.jwt_algorithm == "RS256":
            if not self.jwt_public_key_path or not self.jwt_private_key_path:
                raise ValueError("JWT key paths required for RS256")
        if self.jwt_algorithm == "HS256":
            if not self.jwt_secret_key:
                raise ValueError("JWT_SECRET_KEY required for HS256")
        return self


# ====================
# Audio Settings
# ====================
class AudioSettings(BaseSettings):
    """Audio processing configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Silence detection
    silence_threshold_ms: int = Field(default=3000, env="SILENCE_THRESHOLD_MS")
    silence_confidence_threshold: float = Field(default=0.8, env="SILENCE_CONFIDENCE_THRESHOLD")
    
    # Transcription
    audio_transcription_provider: Literal["whisper", "google", "azure"] = Field(default="whisper", env="AUDIO_TRANSCRIPTION_PROVIDER")
    audio_confidence_threshold: float = Field(default=0.7, env="AUDIO_CONFIDENCE_THRESHOLD")
    max_transcript_length: int = Field(default=10000, env="MAX_TRANSCRIPT_LENGTH")
    
    # Analysis
    enable_audio_analysis: bool = Field(default=True, env="ENABLE_AUDIO_ANALYSIS")
    audio_chunk_size_ms: int = Field(default=500, env="AUDIO_CHUNK_SIZE_MS")


# ====================
# Rate Limiting Settings
# ====================
class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Login rate limiting
    login_rate_limit: int = Field(default=5, env="LOGIN_RATE_LIMIT")
    login_rate_window_seconds: int = Field(default=900, env="LOGIN_RATE_WINDOW_SECONDS")
    
    # API rate limiting
    api_rate_limit: int = Field(default=100, env="API_RATE_LIMIT")
    api_rate_window_seconds: int = Field(default=60, env="API_RATE_WINDOW_SECONDS")
    
    # Resource limits
    max_concurrent_interviews_per_candidate: int = Field(default=1, env="MAX_CONCURRENT_INTERVIEWS_PER_CANDIDATE")
    max_code_submissions_per_minute: int = Field(default=5, env="MAX_CODE_SUBMISSIONS_PER_MINUTE")


# ====================
# Feature Flags Settings
# ====================
class FeatureFlagsSettings(BaseSettings):
    """Feature flags configuration"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core features
    enable_ai_evaluation: bool = Field(default=True, env="ENABLE_AI_EVALUATION")
    enable_proctoring: bool = Field(default=True, env="ENABLE_PROCTORING")
    enable_audio_analysis: bool = Field(default=True, env="ENABLE_AUDIO_ANALYSIS")
    enable_code_execution: bool = Field(default=True, env="ENABLE_CODE_EXECUTION")
    
    # Optional features
    enable_practice_mode: bool = Field(default=False, env="ENABLE_PRACTICE_MODE")
    enable_human_override: bool = Field(default=True, env="ENABLE_HUMAN_OVERRIDE")
    enable_resume_parsing: bool = Field(default=True, env="ENABLE_RESUME_PARSING")


# ====================
# Master Settings
# ====================
class Settings(BaseSettings):
    """Master settings object combining all configuration categories"""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    app: AppSettings
    database: DatabaseSettings
    redis: RedisSettings
    qdrant: QdrantSettings
    llm: LLMSettings
    sandbox: SandboxSettings
    security: SecuritySettings
    audio: AudioSettings
    rate_limit: RateLimitSettings
    feature_flags: FeatureFlagsSettings
    
    @classmethod
    def load(cls) -> "Settings":
        """Load and validate all settings at startup"""
        try:
            app_settings = AppSettings()
            settings = cls(
                app=app_settings,
                database=DatabaseSettings(),
                redis=RedisSettings(),
                qdrant=QdrantSettings(),
                llm=LLMSettings(),
                sandbox=SandboxSettings(),
                security=SecuritySettings(),
                audio=AudioSettings(),
                rate_limit=RateLimitSettings(),
                feature_flags=FeatureFlagsSettings()
            )
            logger.info(f"Configuration loaded successfully for {settings.app.app_env} environment")
            return settings
        except Exception as e:
            logger.critical(f"Configuration validation failed: {e}")
            # Re-raise original exception in test mode for proper pytest handling
            if os.getenv("TESTING"):
                raise
            raise SystemExit(1)
    
    def __repr__(self):
        """Mask secrets in repr"""
        return f"Settings(app_env={self.app.app_env})"


# Global singleton - skip in testing mode
settings = None if os.getenv("TESTING") else Settings.load()
