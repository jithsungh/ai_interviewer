"""
Auth Domain Module

Contains core business logic for authentication and authorization:
- User registration (admin, candidate)
- Login and JWT token issuance
- Token validation and refresh
- RBAC (Role-Based Access Control)
- Password hashing and verification
- Audit logging

This module contains ZERO HTTP/API concerns - pure domain logic.
"""

from .contracts import (
    # Commands
    RegisterAdminCommand,
    RegisterCandidateCommand,
    LoginCommand,
    RefreshTokenCommand,
    LogoutCommand,
    ChangePasswordCommand,
    
    # Results
    AuthenticationResult,
    UserProfile,
    TokenValidationResult,
)

from .auth_service import AuthService
from .rbac_enforcer import RBACEnforcer, Permission
from .password_hasher import PasswordHasher
from .jwt_service import JWTService

__all__ = [
    # Commands
    "RegisterAdminCommand",
    "RegisterCandidateCommand",
    "LoginCommand",
    "RefreshTokenCommand",
    "LogoutCommand",
    "ChangePasswordCommand",
    
    # Results
    "AuthenticationResult",
    "UserProfile",
    "TokenValidationResult",
    
    # Services
    "AuthService",
    "RBACEnforcer",
    "PasswordHasher",
    "JWTService",
    
    # Enums
    "Permission",
]
