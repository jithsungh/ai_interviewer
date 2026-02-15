"""
Unit tests for Security Configuration

Tests security config, CORS, and password policy.
"""

import pytest
from dataclasses import FrozenInstanceError

from app.config.security import (
    SecurityConfig,
    CORSConfig,
    PasswordPolicy,
    create_security_config,
    create_cors_config,
    create_password_policy
)
from app.config.settings import SecuritySettings


class TestSecurityConfig:
    """Test security configuration"""
    
    def test_security_config_dev(self):
        """Test security config for dev environment"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-secret-key",
            allowed_hosts=["localhost"]
        )
        
        config = SecurityConfig.from_settings(settings, "dev")
        
        assert config.cookie_secure is False  # Dev allows insecure
        assert config.enforce_https is False
        assert config.enable_security_headers is True
        assert config.allow_insecure_transport is True
    
    def test_security_config_prod(self):
        """Test security config for prod environment"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-secret-key-production",
            allowed_hosts=["api.example.com"]
        )
        
        config = SecurityConfig.from_settings(settings, "prod")
        
        assert config.cookie_secure is True  # Prod requires secure
        assert config.enforce_https is True
        assert config.enable_security_headers is True
        assert config.allow_insecure_transport is False
    
    def test_security_config_immutable(self):
        """Test that security config is immutable"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        config = SecurityConfig.from_settings(settings, "dev")
        
        with pytest.raises(FrozenInstanceError):
            config.cookie_secure = True  # type: ignore
    
    def test_security_config_cors_settings(self):
        """Test CORS settings in security config"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key",
            allowed_hosts=["localhost", "127.0.0.1"]
        )
        config = SecurityConfig.from_settings(settings, "dev")
        
        assert config.cors_origins == ["localhost", "127.0.0.1"]
        assert config.cors_allow_credentials is True
        assert config.cors_max_age == 3600
    
    def test_security_config_password_requirements(self):
        """Test password requirements in security config"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        config = SecurityConfig.from_settings(settings, "dev")
        
        assert config.min_password_length == 8
        assert config.require_uppercase is True
        assert config.require_lowercase is True
        assert config.require_digit is True
        assert config.require_special_char is True


class TestCORSConfig:
    """Test CORS configuration"""
    
    def test_cors_config_creation(self):
        """Test CORS config creation from security config"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key",
            allowed_hosts=["localhost"]
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        cors_config = CORSConfig.from_security_config(security_config)
        
        assert cors_config.allow_origins == ["localhost"]
        assert cors_config.allow_credentials is True
        assert "GET" in cors_config.allow_methods
        assert "POST" in cors_config.allow_methods
        assert cors_config.max_age == 3600
    
    def test_cors_config_immutable(self):
        """Test that CORS config is immutable"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        cors_config = CORSConfig.from_security_config(security_config)
        
        with pytest.raises(FrozenInstanceError):
            cors_config.allow_credentials = False  # type: ignore
    
    def test_cors_config_methods(self):
        """Test CORS allowed methods"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        cors_config = CORSConfig.from_security_config(security_config)
        
        expected_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        assert cors_config.allow_methods == expected_methods
    
    def test_cors_config_factory(self):
        """Test CORS config factory function"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        cors_config = create_cors_config(security_config)
        
        assert isinstance(cors_config, CORSConfig)


class TestPasswordPolicy:
    """Test password policy validation"""
    
    def test_password_policy_creation(self):
        """Test password policy creation"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        assert policy.min_length == 8
        assert policy.require_uppercase is True
        assert policy.require_lowercase is True
        assert policy.require_digit is True
        assert policy.require_special_char is True
    
    def test_password_policy_valid_password(self):
        """Test password policy with valid password"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("MyPassword123!")
        assert valid is True
        assert error == ""
    
    def test_password_policy_too_short(self):
        """Test password policy rejects short password"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("Short1!")
        assert valid is False
        assert "at least 8 characters" in error
    
    def test_password_policy_no_uppercase(self):
        """Test password policy requires uppercase"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("mypassword123!")
        assert valid is False
        assert "uppercase" in error
    
    def test_password_policy_no_lowercase(self):
        """Test password policy requires lowercase"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("MYPASSWORD123!")
        assert valid is False
        assert "lowercase" in error
    
    def test_password_policy_no_digit(self):
        """Test password policy requires digit"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("MyPassword!")
        assert valid is False
        assert "digit" in error
    
    def test_password_policy_no_special_char(self):
        """Test password policy requires special character"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid, error = policy.validate("MyPassword123")
        assert valid is False
        assert "special character" in error
    
    def test_password_policy_multiple_valid_passwords(self):
        """Test password policy with multiple valid passwords"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        valid_passwords = [
            "MyPassword123!",
            "Secure@Pass999",
            "Complex#2024Password",
            "Test$User123"
        ]
        
        for password in valid_passwords:
            valid, error = policy.validate(password)
            assert valid is True, f"Password {password} should be valid"
    
    def test_password_policy_immutable(self):
        """Test that password policy is immutable"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = PasswordPolicy.from_security_config(security_config)
        
        with pytest.raises(FrozenInstanceError):
            policy.min_length = 10  # type: ignore
    
    def test_password_policy_factory(self):
        """Test password policy factory function"""
        settings = SecuritySettings(
            jwt_algorithm="HS256",
            jwt_secret_key="test-key"
        )
        security_config = SecurityConfig.from_settings(settings, "dev")
        policy = create_password_policy(security_config)
        
        assert isinstance(policy, PasswordPolicy)


# Run tests with pytest -v tests/unit/config/test_security.py
