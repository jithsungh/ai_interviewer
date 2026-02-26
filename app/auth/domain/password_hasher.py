"""
Password Hashing and Validation

Provides bcrypt-based password hashing with complexity validation.
All passwords are hashed with cost factor 12 (configurable).
"""

import re
import bcrypt
from typing import Optional

from app.shared.errors import ValidationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class PasswordHasher:
    """
    Password hashing and complexity validation.
    
    Uses bcrypt with configurable cost factor (default: 12).
    Enforces password complexity requirements.
    """
    
    def __init__(
        self,
        cost_factor: int = 12,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True
    ):
        """
        Initialize password hasher.
        
        Args:
            cost_factor: bcrypt cost factor (higher = slower but more secure)
            min_length: Minimum password length
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
        """
        self.cost_factor = cost_factor
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
        
        logger.info(
            "PasswordHasher initialized",
            extra={
                "cost_factor": cost_factor,
                "min_length": min_length
            }
        )
    
    def hash(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plaintext password
            
        Returns:
            bcrypt hash string
            
        Raises:
            ValidationError: If password doesn't meet complexity requirements
        """
        # Validate complexity before hashing
        self.validate_complexity(password)
        
        # Hash with bcrypt
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=self.cost_factor)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        return hashed.decode('utf-8')
    
    def verify(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            password: Plaintext password to verify
            password_hash: bcrypt hash to verify against
            
        Returns:
            True if password matches hash, False otherwise
        """
        try:
            password_bytes = password.encode('utf-8')
            hash_bytes = password_hash.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as e:
            logger.warning(
                "Password verification failed",
                extra={
                    "error": str(e),
                    "event_type": "password.verification.error"
                }
            )
            return False
    
    def validate_complexity(self, password: str) -> None:
        """
        Validate password meets complexity requirements.
        
        Args:
            password: Password to validate
            
        Raises:
            ValidationError: If password doesn't meet requirements
        """
        errors = []
        
        # Check length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters")
        
        # Check uppercase
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        # Check lowercase
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        # Check digit
        if self.require_digit and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        # Check special character
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        if errors:
            raise ValidationError(
                message="; ".join(errors),
                field="password",
                metadata={"requirements": errors}
            )
