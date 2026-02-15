"""
Pytest configuration and fixtures for config tests

Provides common fixtures and test utilities.
"""

import pytest
import os
from unittest.mock import patch

# Set TESTING flag before any imports to disable .env loading
os.environ["TESTING"] = "1"


@pytest.fixture(scope="session", autouse=True)
def disable_dotenv_for_tests():
    """Ensure TESTING flag persists throughout test session"""
    os.environ["TESTING"] = "1"
    yield
    os.environ.pop("TESTING", None)


@pytest.fixture
def minimal_env():
    """Minimal environment variables for config loading"""
    return {
        "APP_ENV": "dev",
        "DEBUG": "false",
        "BASE_URL": "http://localhost:8000",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-groq-key",
        "JWT_SECRET_KEY": "test-secret-key-long-enough",
    }


@pytest.fixture
def dev_env(minimal_env):
    """Development environment variables"""
    env = minimal_env.copy()
    env.update({
        "APP_ENV": "dev",
        "DEBUG": "true",
        "BASE_URL": "http://localhost:8000",
    })
    return env


@pytest.fixture
def staging_env(minimal_env):
    """Staging environment variables"""
    env = minimal_env.copy()
    env.update({
        "APP_ENV": "staging",
        "DEBUG": "false",
        "BASE_URL": "https://staging-api.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@staging/db?ssl=require",
    })
    return env


@pytest.fixture
def prod_env(minimal_env):
    """Production environment variables"""
    env = minimal_env.copy()
    env.update({
        "APP_ENV": "prod",
        "DEBUG": "false",
        "BASE_URL": "https://api.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@prod/db?ssl=require",
        "REDIS_URL": "redis://:password@prod-redis:6379/0",
        "QDRANT_URL": "https://prod-qdrant.example.com",
    })
    return env


@pytest.fixture
def mock_env(minimal_env):
    """Mock environment with patch.dict"""
    with patch.dict(os.environ, minimal_env, clear=True):
        yield minimal_env


@pytest.fixture
def sample_passwords():
    """Sample passwords for testing password policy"""
    return {
        "valid": [
            "MyPassword123!",
            "Secure@Pass999",
            "Complex#2024Password",
            "Test$User123",
        ],
        "invalid": {
            "too_short": "Short1!",
            "no_uppercase": "mypassword123!",
            "no_lowercase": "MYPASSWORD123!",
            "no_digit": "MyPassword!",
            "no_special": "MyPassword123",
        }
    }


@pytest.fixture
def security_settings_hs256():
    """Sample SecuritySettings with HS256"""
    from app.config.settings import SecuritySettings
    return SecuritySettings(
        jwt_algorithm="HS256",
        jwt_secret_key="test-secret-key-for-testing"
    )


@pytest.fixture
def feature_flags_all_enabled():
    """Feature flags with all features enabled"""
    from app.config.settings import FeatureFlagsSettings
    return FeatureFlagsSettings(
        enable_ai_evaluation=True,
        enable_proctoring=True,
        enable_audio_analysis=True,
        enable_code_execution=True,
        enable_practice_mode=True,
        enable_human_override=True,
        enable_resume_parsing=True
    )


@pytest.fixture
def feature_flags_all_disabled():
    """Feature flags with all features disabled"""
    from app.config.settings import FeatureFlagsSettings
    return FeatureFlagsSettings(
        enable_ai_evaluation=False,
        enable_proctoring=False,
        enable_audio_analysis=False,
        enable_code_execution=False,
        enable_practice_mode=False,
        enable_human_override=False,
        enable_resume_parsing=False
    )


@pytest.fixture(autouse=True)
def reset_config_module():
    """
    Reset config module between tests to prevent state leakage.
    
    This is autouse=True so it runs for every test automatically.
    """
    # Cleanup any cached imports
    import sys
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith('app.config')]
    for module in modules_to_remove:
        if module != 'app.config.constants':  # Keep constants as they're truly immutable
            sys.modules.pop(module, None)
    
    yield
    
    # Cleanup after test
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith('app.config')]
    for module in modules_to_remove:
        if module != 'app.config.constants':
            sys.modules.pop(module, None)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "config: mark test as related to configuration"
    )
