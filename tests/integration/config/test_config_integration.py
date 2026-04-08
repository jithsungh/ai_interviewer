"""
Integration tests for Config Module

Tests complete configuration loading and integration between components.
"""

import pytest
import os
from unittest.mock import patch


class TestConfigIntegration:
    """Test complete configuration integration"""
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DEBUG": "true",
        "BASE_URL": "http://localhost:8000",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-groq-key",
        "JWT_SECRET_KEY": "test-secret-key-long-enough-for-validation",
    }, clear=True)
    def test_settings_load_complete(self):
        """Test that all settings load successfully"""
        from app.config.settings import Settings
        
        settings = Settings.load()
        
        assert settings.app.app_env == "dev"
        assert settings.database.database_url
        assert settings.redis.redis_url
        assert settings.qdrant.qdrant_url
        assert settings.llm.groq_api_key == "test-groq-key"
        assert settings.security.jwt_secret_key
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_config_module_exports(self):
        """Test that config module exports all required objects"""
        from app.config import (
            settings,
            feature_flags,
            env_config,
            security_config,
            cors_config,
            password_policy,
            constants
        )
        
        assert settings is not None
        assert feature_flags is not None
        assert env_config is not None
        assert security_config is not None
        assert cors_config is not None
        assert password_policy is not None
        assert constants is not None
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
        "ENABLE_AI_EVALUATION": "true",
        "ENABLE_PROCTORING": "false",
    }, clear=True)
    def test_feature_flags_integration(self):
        """Test feature flags integrate with settings"""
        from app.config import settings, feature_flags
        
        assert feature_flags.ENABLE_AI_EVALUATION is True
        assert feature_flags.ENABLE_PROCTORING is False
    
    @patch.dict(os.environ, {
        "APP_ENV": "prod",
        "DEBUG": "false",
        "BASE_URL": "https://api.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db?ssl=require",
        "REDIS_URL": "redis://:password@host:6379/0",
        "QDRANT_URL": "https://qdrant.example.com",
        "GROQ_API_KEY": "prod-key",
        "JWT_SECRET_KEY": "production-secret-key-very-long",
    }, clear=True)
    def test_production_config_integration(self):
        """Test production configuration integration"""
        from app.config import settings, env_config, security_config
        
        assert settings.app.app_env == "prod"
        assert settings.app.debug is False
        assert env_config.is_prod is True
        assert env_config.enable_openapi is False
        assert security_config.cookie_secure is True
        assert security_config.enforce_https is True
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION_NAME": "test_collection",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_qdrant_environment_suffix(self):
        """Test Qdrant collection name includes environment suffix"""
        from app.config import settings
        
        collection_name = settings.qdrant.get_collection_name_with_env(settings.app.app_env)
        assert collection_name == "test_collection_dev"
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
        "SANDBOX_TIME_LIMIT_MS": "5000",
        "SANDBOX_MEMORY_LIMIT_KB": "524288",
    }, clear=True)
    def test_sandbox_config_integration(self):
        """Test sandbox configuration integration"""
        from app.config import settings
        
        assert settings.sandbox.sandbox_time_limit_ms == 5000
        assert settings.sandbox.sandbox_memory_limit_kb == 524288
        assert settings.sandbox.sandbox_network_disabled is True
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_password_policy_integration(self):
        """Test password policy integration with security config"""
        from app.config import password_policy
        
        # Valid password
        valid, error = password_policy.validate("MyPassword123!")
        assert valid is True
        
        # Invalid password
        valid, error = password_policy.validate("weak")
        assert valid is False
        assert error != ""
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_constants_accessible(self):
        """Test constants are accessible from config module"""
        from app.config import constants
        
        assert constants.SUPPORTED_LANGUAGES
        assert constants.MAX_CODE_SIZE_BYTES > 0
        assert constants.INTERVIEW_STATUS_VALUES
    
    @patch.dict(os.environ, {
        "APP_ENV": "staging",
        "DEBUG": "false",
        "BASE_URL": "https://staging.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@staging/db",
        "REDIS_URL": "redis://staging:6379/0",
        "QDRANT_URL": "http://staging:6333",
        "GROQ_API_KEY": "staging-key",
        "JWT_SECRET_KEY": "staging-secret-key",
    }, clear=True)
    def test_staging_environment_integration(self):
        """Test staging environment configuration"""
        from app.config import settings, env_config
        
        assert settings.app.app_env == "staging"
        assert env_config.is_staging is True
        assert env_config.enable_openapi is True
        assert env_config.should_use_ssl() is True
        assert env_config.get_log_level() == "INFO"


class TestConfigValidationIntegration:
    """Test configuration validation in integration scenarios"""
    
    @patch.dict(os.environ, {
        "TESTING": "1",
        "APP_ENV": "prod",
        "DEBUG": "true",  # Invalid: prod with debug
        "BASE_URL": "https://api.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
        "REDIS_URL": "redis://host:6379/0",
        "QDRANT_URL": "https://qdrant.example.com",
        "GROQ_API_KEY": "key",
        "JWT_SECRET_KEY": "secret",
    }, clear=True)
    def test_production_debug_validation_fails(self):
        """Test that production with DEBUG=true fails validation"""
        from pydantic import ValidationError
        from app.config.settings import Settings
        
        with pytest.raises(ValidationError):
            Settings.load()
    
    @patch.dict(os.environ, {
        "TESTING": "1",
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "DEFAULT_LLM_PROVIDER": "openai",
        # Missing OPENAI_API_KEY
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_missing_llm_api_key_fails(self):
        """Test that missing LLM API key fails validation"""
        from pydantic import ValidationError
        from app.config.settings import Settings
        
        with pytest.raises(ValidationError):
            Settings.load()
    
    @patch.dict(os.environ, {
        "TESTING": "1",
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_ALGORITHM": "HS256",
        # Missing JWT_SECRET_KEY
    }, clear=True)
    def test_missing_jwt_secret_fails(self):
        """Test that missing JWT secret key fails validation"""
        from pydantic import ValidationError
        from app.config.settings import Settings
        
        with pytest.raises(ValidationError):
            Settings.load()


class TestConfigUsagePatterns:
    """Test common configuration usage patterns"""
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
        "ENABLE_AI_EVALUATION": "true",
    }, clear=True)
    def test_feature_flag_conditional_logic(self):
        """Test using feature flags for conditional logic"""
        from app.config import feature_flags
        
        # Simulate conditional feature logic
        if feature_flags.ENABLE_AI_EVALUATION:
            result = "ai_evaluation_enabled"
        else:
            result = "ai_evaluation_disabled"
        
        assert result == "ai_evaluation_enabled"
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_constants_usage(self):
        """Test using constants in business logic"""
        from app.config import constants
        
        # Simulate validation logic
        code_size = 50_000
        is_valid = code_size <= constants.MAX_CODE_SIZE_BYTES
        
        assert is_valid is True
        
        # Test with invalid size
        code_size = 150_000
        is_valid = code_size <= constants.MAX_CODE_SIZE_BYTES
        
        assert is_valid is False
    
    @patch.dict(os.environ, {
        "APP_ENV": "dev",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "DEFAULT_LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "test-key",
        "JWT_SECRET_KEY": "test-secret",
    }, clear=True)
    def test_settings_access_patterns(self):
        """Test common settings access patterns"""
        from app.config import settings
        
        # Test nested access
        llm_provider = settings.llm.default_llm_provider
        assert llm_provider == "groq"
        
        # Test settings usage in connection strings
        db_url = settings.database.database_url
        assert "postgresql" in db_url


# Run tests with pytest -v tests/integration/config/
