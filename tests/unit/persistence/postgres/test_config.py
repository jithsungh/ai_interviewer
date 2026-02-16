"""
Unit Tests for DatabaseSettings Configuration

Tests configuration validation from centralized config module.
"""

import pytest
import os
from pydantic import ValidationError


class TestDatabaseSettingsValidation:
    """Test configuration validation logic."""
    
    def test_valid_config_from_env(self):
        """Test configuration loads from environment."""
        # This test is more about integration with settings
        # Unit tests for DatabaseSettings would be in tests/unit/config/
        from app.config.settings import DatabaseSettings
        
        # Set test env vars
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/testdb"
        
        config = DatabaseSettings()
        
        assert config.database_url == "postgresql://user:pass@localhost/testdb"
        assert config.db_pool_size == 20  # Default
        assert config.db_max_overflow == 10  # Default
        assert config.db_pool_timeout == 30  # Default
        assert config.db_echo is False  # Default
        
        # Cleanup
        del os.environ["DATABASE_URL"]
    
    def test_config_with_all_parameters(self):
        """Test configuration with custom values."""
        from app.config.settings import DatabaseSettings
        
        config = DatabaseSettings(
            database_url="postgresql://user:pass@localhost/testdb",
            db_pool_size=30,
            db_max_overflow=15,
            db_pool_timeout=60,
            db_pool_recycle=1800,
            db_pool_pre_ping=True,
            db_query_timeout=45,
            db_echo=True,
        )
        
        assert config.db_pool_size == 30
        assert config.db_max_overflow == 15
        assert config.db_query_timeout == 45
        assert config.db_echo is True
    
    def test_pool_size_validation(self):
        """Test pool_size must be positive."""
        from app.config.settings import DatabaseSettings
        
        # Too small (validation happens in model_validator)
        with pytest.raises(ValueError) as exc_info:
            DatabaseSettings(
                database_url="postgresql://user:pass@localhost/testdb",
                db_pool_size=0
            )
        assert "DB_POOL_SIZE must be > 0" in str(exc_info.value)
    
# Note: SSL settings and advanced infrastructure configs
# are handled in engine.py as needed, not as env vars
