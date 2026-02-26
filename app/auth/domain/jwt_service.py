"""
JWT Token Generation and Validation

Provides RS256-based JWT token issuance and verification.
Supports access tokens (short-lived) and refresh tokens (long-lived, opaque).
"""

import jwt
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

from app.shared.errors import AuthenticationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class JWTService:
    """
    JWT token generation and validation service.
    
    Uses RS256 (RSA signatures) for access tokens.
    Generates cryptographically random refresh tokens.
    """
    
    def __init__(
        self,
        private_key: str,
        public_key: str,
        algorithm: str = "RS256",
        access_token_ttl_minutes: int = 15,
        refresh_token_ttl_days: int = 30
    ):
        """
        Initialize JWT service.
        
        Args:
            private_key: RSA private key (PEM format) for signing
            public_key: RSA public key (PEM format) for verification
            algorithm: JWT algorithm (default: RS256)
            access_token_ttl_minutes: Access token time-to-live in minutes
            refresh_token_ttl_days: Refresh token time-to-live in days
        """
        self.private_key = private_key
        self.public_key = public_key
        self.algorithm = algorithm
        self.access_token_ttl = timedelta(minutes=access_token_ttl_minutes)
        self.refresh_token_ttl = timedelta(days=refresh_token_ttl_days)
        
        logger.info(
            "JWTService initialized",
            extra={
                "algorithm": algorithm,
                "access_ttl_minutes": access_token_ttl_minutes,
                "refresh_ttl_days": refresh_token_ttl_days
            }
        )
    
    def generate_access_token(
        self,
        user_id: int,
        user_type: str,
        token_version: int,
        admin_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        admin_role: Optional[str] = None,
        candidate_id: Optional[int] = None
    ) -> str:
        """
        Generate JWT access token.
        
        Args:
            user_id: User ID
            user_type: 'admin' or 'candidate'
            token_version: Token version (for forced logout)
            admin_id: Admin ID (if admin)
            organization_id: Organization ID (if admin)
            admin_role: Admin role (if admin)
            candidate_id: Candidate ID (if candidate)
            
        Returns:
            JWT access token string
        """
        now = datetime.now(timezone.utc)
        exp = now + self.access_token_ttl
        
        # Build claims
        payload: Dict[str, Any] = {
            "sub": user_id,  # Subject (user ID)
            "type": user_type,
            "token_version": token_version,
            "iat": int(now.timestamp()),  # Issued at
            "exp": int(exp.timestamp()),  # Expires at
            "jti": str(uuid4())  # JWT ID (unique token identifier)
        }
        
        # Add admin-specific claims
        if user_type == "admin":
            if not all([admin_id, organization_id, admin_role]):
                raise ValueError("Admin tokens require admin_id, organization_id, admin_role")
            payload["admin_id"] = admin_id
            payload["organization_id"] = organization_id
            payload["role"] = admin_role
        
        # Add candidate-specific claims
        elif user_type == "candidate":
            if not candidate_id:
                raise ValueError("Candidate tokens require candidate_id")
            payload["candidate_id"] = candidate_id
        
        # Sign token
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.algorithm
        )
        
        logger.debug(
            "Access token generated",
            extra={
                "user_id": user_id,
                "user_type": user_type,
                "expires_at": exp.isoformat(),
                "event_type": "jwt.access_token.generated"
            }
        )
        
        return token
    
    def generate_refresh_token(self) -> str:
        """
        Generate cryptographically random refresh token.
        
        Returns:
            Opaque refresh token string (64 bytes, hex-encoded)
        """
        # Generate 64 bytes of random data
        token_bytes = secrets.token_bytes(64)
        
        # Hex encode for storage/transmission
        token = token_bytes.hex()
        
        logger.debug(
            "Refresh token generated",
            extra={"event_type": "jwt.refresh_token.generated"}
        )
        
        return token
    
    def hash_refresh_token(self, token: str) -> str:
        """
        Hash refresh token for storage.
        
        Refresh tokens are hashed before storage (like passwords).
        
        Args:
            token: Plaintext refresh token
            
        Returns:
            SHA-256 hash of token
        """
        token_bytes = token.encode('utf-8')
        hash_bytes = hashlib.sha256(token_bytes).digest()
        return hash_bytes.hex()
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT access token.
        
        Args:
            token: JWT access token string
            
        Returns:
            Decoded token claims
            
        Raises:
            AuthenticationError: If token is invalid, expired, or malformed
        """
        try:
            # Verify signature and decode
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm]
            )
            
            logger.debug(
                "Access token verified",
                extra={
                    "user_id": claims.get("sub"),
                    "user_type": claims.get("type"),
                    "event_type": "jwt.access_token.verified"
                }
            )
            
            return claims
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError(
                message="Token expired",
                metadata={"error_type": "expired"}
            )
        
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(
                message=f"Invalid token: {str(e)}",
                metadata={"error_type": "invalid_signature"}
            )
        
        except Exception as e:
            logger.error(
                "Token verification failed",
                extra={
                    "error": str(e),
                    "event_type": "jwt.verification.error"
                }
            )
            raise AuthenticationError(
                message="Token verification failed",
                metadata={"error_type": "unknown"}
            )
    
    def get_refresh_token_expiry(self) -> datetime:
        """
        Get expiry datetime for a new refresh token.
        
        Returns:
            Expiry datetime (now + refresh_token_ttl)
        """
        return datetime.now(timezone.utc) + self.refresh_token_ttl
