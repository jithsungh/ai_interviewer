"""
Unit tests for Environment Configuration

Tests environment-specific behavior and configuration.
"""

import pytest

from app.config.environments import EnvironmentConfig, create_env_config


class TestEnvironmentConfig:
    """Test environment configuration"""
    
    def test_dev_environment(self):
        """Test dev environment configuration"""
        config = EnvironmentConfig.from_app_env("dev")
        
        assert config.env == "dev"
        assert config.is_dev is True
        assert config.is_staging is False
        assert config.is_prod is False
        assert config.enable_openapi is True
        assert config.enable_debug_logging is True
        assert config.strict_cors is False
        assert config.require_ssl is False
        assert config.allow_insecure_transport is True
    
    def test_staging_environment(self):
        """Test staging environment configuration"""
        config = EnvironmentConfig.from_app_env("staging")
        
        assert config.env == "staging"
        assert config.is_dev is False
        assert config.is_staging is True
        assert config.is_prod is False
        assert config.enable_openapi is True
        assert config.enable_debug_logging is False
        assert config.strict_cors is False
        assert config.require_ssl is True
        assert config.allow_insecure_transport is False
    
    def test_prod_environment(self):
        """Test prod environment configuration"""
        config = EnvironmentConfig.from_app_env("prod")
        
        assert config.env == "prod"
        assert config.is_dev is False
        assert config.is_staging is False
        assert config.is_prod is True
        assert config.enable_openapi is False  # Disabled in prod
        assert config.enable_debug_logging is False
        assert config.strict_cors is True
        assert config.require_ssl is True
        assert config.allow_insecure_transport is False
    
    def test_get_log_level_dev(self):
        """Test log level for dev environment"""
        config = EnvironmentConfig.from_app_env("dev")
        assert config.get_log_level() == "DEBUG"
    
    def test_get_log_level_staging(self):
        """Test log level for staging environment"""
        config = EnvironmentConfig.from_app_env("staging")
        assert config.get_log_level() == "INFO"
    
    def test_get_log_level_prod(self):
        """Test log level for prod environment"""
        config = EnvironmentConfig.from_app_env("prod")
        assert config.get_log_level() == "WARNING"
    
    def test_get_pool_size_dev(self):
        """Test database pool size for dev environment"""
        config = EnvironmentConfig.from_app_env("dev")
        assert config.get_pool_size(20) == 10  # Half in dev
    
    def test_get_pool_size_staging(self):
        """Test database pool size for staging environment"""
        config = EnvironmentConfig.from_app_env("staging")
        assert config.get_pool_size(20) == 20  # Default in staging
    
    def test_get_pool_size_prod(self):
        """Test database pool size for prod environment"""
        config = EnvironmentConfig.from_app_env("prod")
        assert config.get_pool_size(20) == 40  # Double in prod
    
    def test_should_use_ssl_dev(self):
        """Test SSL requirement for dev environment"""
        config = EnvironmentConfig.from_app_env("dev")
        assert config.should_use_ssl() is False
    
    def test_should_use_ssl_staging(self):
        """Test SSL requirement for staging environment"""
        config = EnvironmentConfig.from_app_env("staging")
        assert config.should_use_ssl() is True
    
    def test_should_use_ssl_prod(self):
        """Test SSL requirement for prod environment"""
        config = EnvironmentConfig.from_app_env("prod")
        assert config.should_use_ssl() is True
    
    def test_get_error_detail_level_dev(self):
        """Test error detail level for dev environment"""
        config = EnvironmentConfig.from_app_env("dev")
        assert config.get_error_detail_level() == "verbose"
    
    def test_get_error_detail_level_staging(self):
        """Test error detail level for staging environment"""
        config = EnvironmentConfig.from_app_env("staging")
        assert config.get_error_detail_level() == "standard"
    
    def test_get_error_detail_level_prod(self):
        """Test error detail level for prod environment"""
        config = EnvironmentConfig.from_app_env("prod")
        assert config.get_error_detail_level() == "minimal"
    
    def test_environment_config_immutable(self):
        """Test that environment config is immutable"""
        config = EnvironmentConfig.from_app_env("dev")
        
        from dataclasses import FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            config.is_dev = False  # type: ignore
    
    def test_create_env_config_factory(self):
        """Test environment config factory function"""
        config = create_env_config("dev")
        
        assert isinstance(config, EnvironmentConfig)
        assert config.env == "dev"


# Run tests with pytest -v tests/unit/config/test_environments.py
