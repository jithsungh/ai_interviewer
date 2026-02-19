"""
Auth Context Configuration

Configuration settings for identity context and WebSocket connections.
"""

from dataclasses import dataclass


@dataclass
class AuthContextConfig:
    """
    Configuration for auth_context module.
    
    Controls behavior of identity injection and WebSocket connections.
    """
    
    # Middleware
    require_authentication: bool = False  # If True, reject all requests without valid token
    
    # WebSocket
    allow_duplicate_connections: bool = True  # If True, replace existing connections
    connection_ttl_seconds: int = 60  # Redis TTL for connection registry
    connection_heartbeat_interval: int = 30  # Seconds between heartbeat pings
    
    # Token expiry
    enforce_token_expiry: bool = True  # If True, reject expired tokens
    token_expiry_grace_period_seconds: int = 300  # 5 minutes grace for token refresh
    
    # Logging
    log_identity_injection: bool = True  # Log when identity is injected
    log_connection_registry_operations: bool = True  # Log connection register/unregister
    
    # Scope enforcement
    strict_tenant_isolation: bool = True  # Raise errors for cross-tenant access
    superadmin_bypass_tenant_isolation: bool = True  # Allow superadmins to access all orgs


# Default configuration instance
auth_context_config = AuthContextConfig()
