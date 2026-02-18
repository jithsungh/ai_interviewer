"""
Unit tests for Settings validation

Tests configuration loading, validation, and error handling.
"""

import pytest
import os
from pydantic import ValidationError
from unittest.mock import patch

from app.config.settings import (
    AppSettings,
    DatabaseSettings,
    RedisSettings,
    QdrantSettings,
    LLMSettings,
    SandboxSettings,
    SecuritySettings,
    AudioSettings,
    RateLimitSettings,
    FeatureFlagsSettings,
    Settings
)


class TestAppSettings:
    """Test application settings validation"""
    
    def test_app_settings_defaults(self):
        """Test app settings load with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            settings = AppSettings()
            assert settings.app_env == "dev"
            assert settings.debug is False
            assert settings.app_name == "AI Interviewer API"
    
    def test_app_settings_from_env(self):
        """Test app settings load from environment"""
        with patch.dict(os.environ, {
            "APP_ENV": "prod",
            "DEBUG": "false",
            "BASE_URL": "https://api.example.com"
        }, clear=True):
            settings = AppSettings()
            assert settings.app_env == "prod"
            assert settings.debug is False
            assert settings.base_url == "https://api.example.com"
    
    def test_production_requires_no_debug(self):
        """Test that DEBUG must be False in production"""
        with patch.dict(os.environ, {
            "APP_ENV": "prod",
            "DEBUG": "true",
            "BASE_URL": "https://api.example.com"
        }, clear=True):
            with pytest.raises(ValidationError, match="DEBUG must be False"):
                AppSettings()
    
    def test_production_warns_http(self):
        """Test that production should use HTTPS"""
        with patch.dict(os.environ, {
            "APP_ENV": "prod",
            "DEBUG": "false",
            "BASE_URL": "http://api.example.com"
        }, clear=True):
            # Should warn but not fail
            settings = AppSettings()
            assert settings.base_url == "http://api.example.com"


class TestDatabaseSettings:
    """Test database settings validation"""
    
    def test_database_settings_required(self):
        """Test that DATABASE_URL is required"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                DatabaseSettings()
    
    def test_database_settings_valid(self):
        """Test valid database configuration"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"
        }, clear=True):
            settings = DatabaseSettings()
            assert "postgresql" in settings.database_url
            assert settings.db_pool_size == 20
    
    def test_database_pool_size_validation(self):
        """Test pool size must be positive"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
            "DB_POOL_SIZE": "0"
        }, clear=True):
            with pytest.raises(ValidationError, match="DB_POOL_SIZE must be > 0"):
                DatabaseSettings()
    
    def test_database_timeout_validation(self):
        """Test timeout must be positive"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
            "DB_POOL_TIMEOUT": "-1"
        }, clear=True):
            with pytest.raises(ValidationError, match="DB_POOL_TIMEOUT must be > 0"):
                DatabaseSettings()


class TestRedisSettings:
    """Test Redis settings validation"""
    
    def test_redis_settings_required(self):
        """Test that REDIS_URL is required"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                RedisSettings()
    
    def test_redis_settings_valid(self):
        """Test valid Redis configuration"""
        with patch.dict(os.environ, {
            "REDIS_URL": "redis://localhost:6379/0"
        }, clear=True):
            settings = RedisSettings()
            assert "redis" in settings.redis_url
            assert settings.redis_db == 0
            assert settings.redis_session_ttl == 3600


class TestQdrantSettings:
    """Test Qdrant settings validation"""
    
    def test_qdrant_settings_required(self):
        """Test that QDRANT_URL is required"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                QdrantSettings()
    
    def test_qdrant_settings_valid(self):
        """Test valid Qdrant configuration"""
        with patch.dict(os.environ, {
            "QDRANT_URL": "http://localhost:6333"
        }, clear=True):
            settings = QdrantSettings()
            assert settings.qdrant_url == "http://localhost:6333"
            assert settings.qdrant_embedding_dim == 768
    
    def test_qdrant_collection_name_with_env(self):
        """Test collection name includes environment suffix"""
        with patch.dict(os.environ, {
            "QDRANT_URL": "http://localhost:6333",
            "QDRANT_COLLECTION_NAME": "questions"
        }, clear=True):
            settings = QdrantSettings()
            assert settings.get_collection_name_with_env("dev") == "questions_dev"
            assert settings.get_collection_name_with_env("staging") == "questions_staging"
            assert settings.get_collection_name_with_env("prod") == "questions"


class TestLLMSettings:
    """Test LLM provider settings validation"""
    
    def test_llm_settings_defaults(self):
        """Test LLM settings with defaults"""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test-key"
        }, clear=True):
            settings = LLMSettings()
            assert settings.default_llm_provider == "groq"
            assert settings.groq_api_key == "test-key"
    
    def test_openai_requires_api_key(self):
        """Test OpenAI provider requires API key"""
        with patch.dict(os.environ, {
            "DEFAULT_LLM_PROVIDER": "openai"
        }, clear=True):
            with pytest.raises(ValidationError, match="OPENAI_API_KEY required"):
                LLMSettings()
    
    def test_anthropic_requires_api_key(self):
        """Test Anthropic provider requires API key"""
        with patch.dict(os.environ, {
            "DEFAULT_LLM_PROVIDER": "anthropic"
        }, clear=True):
            with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY required"):
                LLMSettings()
    
    def test_groq_requires_api_key(self):
        """Test Groq provider requires API key"""
        with patch.dict(os.environ, {
            "DEFAULT_LLM_PROVIDER": "groq"
        }, clear=True):
            with pytest.raises(ValidationError, match="GROQ_API_KEY required"):
                LLMSettings()
    
    def test_llm_model_routing(self):
        """Test LLM model routing configuration"""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test-key",
            "LLM_MODEL_EVALUATION": "custom-model"
        }, clear=True):
            settings = LLMSettings()
            assert settings.llm_model_evaluation == "custom-model"
    
    def test_embedding_service_defaults(self):
        """Test embedding service configuration defaults"""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test-key"
        }, clear=True):
            settings = LLMSettings()
            assert settings.embedding_model_url == "http://localhost:8080"
            assert settings.default_embedding_model == "all-mpnet-base-v2"
            assert settings.embedding_timeout_seconds == 30
    
    def test_embedding_service_custom_url(self):
        """Test embedding service with custom URL"""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test-key",
            "EMBEDDING_MODEL_URL": "http://embedding-service:9000",
            "DEFAULT_EMBEDDING_MODEL": "custom-model"
        }, clear=True):
            settings = LLMSettings()
            assert settings.embedding_model_url == "http://embedding-service:9000"
            assert settings.default_embedding_model == "custom-model"


class TestSandboxSettings:
    """Test sandbox execution settings validation"""
    
    def test_sandbox_settings_defaults(self):
        """Test sandbox settings with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            settings = SandboxSettings()
            assert settings.sandbox_time_limit_ms == 2000
            assert settings.sandbox_memory_limit_kb == 262144
            assert settings.sandbox_network_disabled is True
    
    def test_sandbox_time_limit_minimum(self):
        """Test sandbox time limit must be >= 100ms"""
        with patch.dict(os.environ, {
            "SANDBOX_TIME_LIMIT_MS": "50"
        }, clear=True):
            with pytest.raises(ValidationError, match="SANDBOX_TIME_LIMIT_MS must be >= 100ms"):
                SandboxSettings()
    
    def test_sandbox_memory_limit_minimum(self):
        """Test sandbox memory limit must be >= 4MB"""
        with patch.dict(os.environ, {
            "SANDBOX_MEMORY_LIMIT_KB": "1024"
        }, clear=True):
            with pytest.raises(ValidationError, match="SANDBOX_MEMORY_LIMIT_KB must be >= 4MB"):
                SandboxSettings()


class TestSecuritySettings:
    """Test security settings validation"""
    
    def test_security_hs256_requires_secret(self):
        """Test HS256 algorithm requires JWT_SECRET_KEY"""
        with patch.dict(os.environ, {
            "JWT_ALGORITHM": "HS256"
        }, clear=True):
            with pytest.raises(ValidationError, match="JWT_SECRET_KEY required"):
                SecuritySettings()
    
    def test_security_rs256_requires_keys(self):
        """Test RS256 algorithm requires key paths"""
        with patch.dict(os.environ, {
            "JWT_ALGORITHM": "RS256"
        }, clear=True):
            with pytest.raises(ValidationError, match="JWT key paths required"):
                SecuritySettings()
    
    def test_security_valid_hs256(self):
        """Test valid HS256 configuration"""
        with patch.dict(os.environ, {
            "JWT_ALGORITHM": "HS256",
            "JWT_SECRET_KEY": "test-secret-key-must-be-long-enough"
        }, clear=True):
            settings = SecuritySettings()
            assert settings.jwt_algorithm == "HS256"
            assert settings.jwt_secret_key == "test-secret-key-must-be-long-enough"


class TestAudioSettings:
    """Test audio processing settings validation"""
    
    def test_audio_settings_defaults(self):
        """Test audio settings with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            settings = AudioSettings()
            assert settings.silence_threshold_ms == 3000
            assert settings.audio_transcription_provider == "whisper"
            assert settings.enable_audio_analysis is True


class TestRateLimitSettings:
    """Test rate limiting settings validation"""
    
    def test_rate_limit_defaults(self):
        """Test rate limit settings with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            settings = RateLimitSettings()
            assert settings.login_rate_limit == 5
            assert settings.login_rate_window_seconds == 900
            assert settings.max_concurrent_interviews_per_candidate == 1


class TestFeatureFlagsSettings:
    """Test feature flags settings validation"""
    
    def test_feature_flags_defaults(self):
        """Test feature flags with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            settings = FeatureFlagsSettings()
            assert settings.enable_ai_evaluation is True
            assert settings.enable_proctoring is True
            assert settings.enable_practice_mode is False
    
    def test_feature_flags_from_env(self):
        """Test feature flags from environment"""
        with patch.dict(os.environ, {
            "ENABLE_AI_EVALUATION": "false",
            "ENABLE_PRACTICE_MODE": "true"
        }, clear=True):
            settings = FeatureFlagsSettings()
            assert settings.enable_ai_evaluation is False
            assert settings.enable_practice_mode is True


# Run tests with pytest -v tests/unit/config/test_settings_validation.py
