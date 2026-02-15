"""
Environment-Specific Configuration

Environment-aware defaults and validation for dev/staging/prod environments.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EnvironmentConfig:
    """
    Environment-specific configuration.
    
    Provides clear separation between dev/staging/prod behavior
    and environment-specific settings.
    """
    
    env: Literal["dev", "staging", "prod"]
    is_dev: bool
    is_staging: bool
    is_prod: bool
    
    # Environment-specific settings
    enable_openapi: bool  # Disable in prod
    enable_debug_logging: bool
    strict_cors: bool
    require_ssl: bool
    allow_insecure_transport: bool
    
    @classmethod
    def from_app_env(cls, app_env: str) -> "EnvironmentConfig":
        """Create EnvironmentConfig from app environment string"""
        is_dev = app_env == "dev"
        is_staging = app_env == "staging"
        is_prod = app_env == "prod"
        
        return cls(
            env=app_env,  # type: ignore
            is_dev=is_dev,
            is_staging=is_staging,
            is_prod=is_prod,
            enable_openapi=(not is_prod),
            enable_debug_logging=is_dev,
            strict_cors=is_prod,
            require_ssl=(is_prod or is_staging),
            allow_insecure_transport=is_dev
        )
    
    def get_log_level(self) -> str:
        """Get appropriate log level for environment"""
        if self.is_dev:
            return "DEBUG"
        elif self.is_staging:
            return "INFO"
        else:
            return "WARNING"
    
    def get_pool_size(self, default: int = 20) -> int:
        """Get appropriate database pool size for environment"""
        if self.is_prod:
            return default * 2  # Higher pool size in prod
        elif self.is_staging:
            return default
        else:
            return default // 2  # Lower pool size in dev
    
    def should_use_ssl(self) -> bool:
        """Determine if SSL should be enforced"""
        return self.is_prod or self.is_staging
    
    def get_error_detail_level(self) -> str:
        """Get error detail level for responses"""
        if self.is_dev:
            return "verbose"  # Include stack traces
        elif self.is_staging:
            return "standard"  # Include error messages
        else:
            return "minimal"  # Minimal error info in prod


def create_env_config(app_env: str) -> EnvironmentConfig:
    """Factory function to create environment config"""
    return EnvironmentConfig.from_app_env(app_env)
