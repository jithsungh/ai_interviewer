"""
Security Configuration

Security policies, CORS settings, password rules, and other security-related configuration.
"""

from dataclasses import dataclass
from typing import List
from app.config.settings import SecuritySettings


@dataclass(frozen=True)
class SecurityConfig:
    """
    Immutable security configuration.
    
    Defines CORS policies, cookie settings, HTTPS enforcement, and password rules.
    """
    
    # CORS
    cors_origins: List[str]
    cors_allow_credentials: bool
    cors_max_age: int
    
    # Cookies
    cookie_secure: bool  # True in prod
    cookie_httponly: bool
    cookie_samesite: str  # "lax" or "strict"
    
    # HTTPS
    enforce_https: bool
    allow_insecure_transport: bool
    
    # Headers
    enable_security_headers: bool
    
    # Password
    min_password_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special_char: bool
    
    @classmethod
    def from_settings(cls, settings: SecuritySettings, app_env: str) -> "SecurityConfig":
        """Create SecurityConfig from SecuritySettings"""
        is_prod = app_env == "prod"
        is_dev = app_env == "dev"
        
        return cls(
            cors_origins=settings.allowed_hosts,
            cors_allow_credentials=True,
            cors_max_age=3600,
            cookie_secure=is_prod,
            cookie_httponly=True,
            cookie_samesite="lax",
            enforce_https=is_prod,
            allow_insecure_transport=is_dev,
            enable_security_headers=settings.enable_secure_headers,
            min_password_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special_char=True
        )


@dataclass(frozen=True)
class CORSConfig:
    """CORS configuration for API"""
    
    allow_origins: List[str]
    allow_credentials: bool
    allow_methods: List[str]
    allow_headers: List[str]
    max_age: int
    
    @classmethod
    def from_security_config(cls, security_config: SecurityConfig) -> "CORSConfig":
        """Create CORS configuration from security config"""
        return cls(
            allow_origins=security_config.cors_origins,
            allow_credentials=security_config.cors_allow_credentials,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["*"],
            max_age=security_config.cors_max_age
        )


@dataclass(frozen=True)
class PasswordPolicy:
    """Password complexity requirements"""
    
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special_char: bool
    
    @classmethod
    def from_security_config(cls, security_config: SecurityConfig) -> "PasswordPolicy":
        """Create password policy from security config"""
        return cls(
            min_length=security_config.min_password_length,
            require_uppercase=security_config.require_uppercase,
            require_lowercase=security_config.require_lowercase,
            require_digit=security_config.require_digit,
            require_special_char=security_config.require_special_char
        )
    
    def validate(self, password: str) -> tuple[bool, str]:
        """
        Validate password against policy.
        
        Returns:
            (is_valid, error_message)
        """
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters long"
        
        if self.require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if self.require_lowercase and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if self.require_digit and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        if self.require_special_char:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                return False, "Password must contain at least one special character"
        
        return True, ""


def create_security_config(settings: SecuritySettings, app_env: str) -> SecurityConfig:
    """Factory function to create security config from settings"""
    return SecurityConfig.from_settings(settings, app_env)


def create_cors_config(security_config: SecurityConfig) -> CORSConfig:
    """Factory function to create CORS config from security config"""
    return CORSConfig.from_security_config(security_config)


def create_password_policy(security_config: SecurityConfig) -> PasswordPolicy:
    """Factory function to create password policy from security config"""
    return PasswordPolicy.from_security_config(security_config)
