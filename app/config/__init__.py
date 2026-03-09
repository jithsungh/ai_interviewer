"""
Configuration Module

Centralized configuration management for the AI Interviewer application.
Provides settings, constants, feature flags, security config, and environment config.

Usage:
    from app.config import settings, feature_flags, constants
    
    if feature_flags.ENABLE_AI_EVALUATION:
        # Use AI evaluation
        pass
"""

from .settings import (
    settings,
    Settings,
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
    AzureStorageSettings
)
from .feature_flags import FeatureFlags, create_feature_flags
from .security import (
    SecurityConfig,
    CORSConfig,
    PasswordPolicy,
    create_security_config,
    create_cors_config,
    create_password_policy
)
from .environments import EnvironmentConfig, create_env_config
from . import constants

# Initialize global configuration objects (skip in testing mode)
if settings is not None:
    feature_flags = create_feature_flags(settings.feature_flags)
    env_config = create_env_config(settings.app.app_env)
    security_config = create_security_config(settings.security, settings.app.app_env)
    cors_config = create_cors_config(security_config)
    password_policy = create_password_policy(security_config)
else:
    # Provide None placeholders in testing mode
    feature_flags = None
    env_config = None
    security_config = None
    cors_config = None
    password_policy = None

__all__ = [
    # Settings
    "settings",
    "Settings",
    "AppSettings",
    "DatabaseSettings",
    "RedisSettings",
    "QdrantSettings",
    "LLMSettings",
    "SandboxSettings",
    "SecuritySettings",
    "AudioSettings",
    "RateLimitSettings",
    "FeatureFlagsSettings",
    "AzureStorageSettings",
    
    # Feature Flags
    "feature_flags",
    "FeatureFlags",
    "create_feature_flags",
    
    # Security
    "security_config",
    "cors_config",
    "password_policy",
    "SecurityConfig",
    "CORSConfig",
    "PasswordPolicy",
    "create_security_config",
    "create_cors_config",
    "create_password_policy",
    
    # Environment
    "env_config",
    "EnvironmentConfig",
    "create_env_config",
    
    # Constants
    "constants",
]

