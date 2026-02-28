"""
Pytest configuration for admin API integration tests.

Sets minimal environment variables so the app can start without real
infrastructure (DB, Redis, Qdrant, etc.).
"""

import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_admin_api_test_env():
    """
    Set minimal env vars required for create_app() to succeed.

    Override if .env already supplies them — these are safe test-only
    defaults that prevent pydantic ValidationError on import.
    """
    defaults = {
        "APP_ENV": "dev",
        "DEBUG": "false",
        "BASE_URL": "http://localhost:8000",
        "DATABASE_URL": "postgresql+psycopg2://test:test@localhost:5432/test_db",
        "REDIS_URL": "redis://localhost:6379/0",
        "QDRANT_URL": "http://localhost:6333",
        "GROQ_API_KEY": "test-groq-key",
        "JWT_SECRET_KEY": "test-secret-key-for-admin-api-integration-tests",
    }
    original = {}
    for key, val in defaults.items():
        original[key] = os.environ.get(key)
        os.environ.setdefault(key, val)

    yield

    # Restore
    for key, val in original.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val
