"""
Identity Builder

Transforms validated JWT claims into IdentityContext.
NO JWT validation happens here (auth module responsibility).
"""

from typing import Dict, Any
from .models import IdentityContext, UserType, AdminRole


class IdentityBuilder:
    """
    Build IdentityContext from validated JWT claims.
    
    NOTE: JWT cryptographic validation is done by auth module.
    This only transforms validated claims into IdentityContext.
    
    Expected JWT Claims Structure:
    {
        "sub": 42,                    # user_id
        "user_type": "admin",         # "admin" | "candidate"
        "organization_id": 1,         # required if admin, null if candidate
        "admin_role": "superadmin",   # required if admin, null if candidate
        "token_version": 3,
        "iat": 1700000000,            # issued at (unix timestamp)
        "exp": 1700003600             # expires at (unix timestamp)
    }
    """
    
    @staticmethod
    def from_jwt_claims(claims: Dict[str, Any]) -> IdentityContext:
        """
        Build IdentityContext from validated JWT claims.
        
        Args:
            claims: Validated JWT payload (dict)
        
        Returns:
            Immutable IdentityContext
        
        Raises:
            ValueError: If required claims missing or invalid
            KeyError: If critical claim missing
        
        Example:
            claims = await auth_service.validate_access_token(token)
            identity = IdentityBuilder.from_jwt_claims(claims)
        """
        # Extract user type
        user_type_str = claims["user_type"]
        try:
            user_type = UserType(user_type_str)
        except ValueError:
            raise ValueError(f"Invalid user_type: {user_type_str}. Must be 'admin' or 'candidate'")
        
        # Extract admin role (if admin)
        admin_role = None
        if user_type == UserType.ADMIN:
            admin_role_str = claims.get("admin_role")
            if not admin_role_str:
                raise ValueError("Admin user must have admin_role in JWT claims")
            try:
                admin_role = AdminRole(admin_role_str)
            except ValueError:
                raise ValueError(
                    f"Invalid admin_role: {admin_role_str}. "
                    f"Must be 'superadmin', 'admin', or 'read_only'"
                )
        
        # Extract candidate_id (only present for candidate tokens)
        candidate_id = claims.get("candidate_id") if user_type == UserType.CANDIDATE else None

        # Build IdentityContext
        return IdentityContext(
            user_id=claims["sub"],
            user_type=user_type,
            candidate_id=candidate_id,
            organization_id=claims.get("organization_id"),
            admin_role=admin_role,
            token_version=claims["token_version"],
            issued_at=claims["iat"],
            expires_at=claims["exp"]
        )
    
    @staticmethod
    def validate_claims_structure(claims: Dict[str, Any]) -> None:
        """
        Validate JWT claims have required structure.
        
        Does NOT validate cryptographic signature (auth module does that).
        Only validates presence and type of required fields.
        
        Args:
            claims: Decoded JWT payload
        
        Raises:
            ValueError: If claims structure invalid
        """
        required_fields = ["sub", "user_type", "token_version", "iat", "exp"]
        
        for field in required_fields:
            if field not in claims:
                raise ValueError(f"Missing required claim: {field}")
        
        # Validate types
        if not isinstance(claims["sub"], int):
            raise ValueError("Claim 'sub' (user_id) must be integer")
        
        if not isinstance(claims["user_type"], str):
            raise ValueError("Claim 'user_type' must be string")
        
        if not isinstance(claims["token_version"], int):
            raise ValueError("Claim 'token_version' must be integer")
        
        if not isinstance(claims["iat"], int):
            raise ValueError("Claim 'iat' (issued_at) must be integer")
        
        if not isinstance(claims["exp"], int):
            raise ValueError("Claim 'exp' (expires_at) must be integer")
        
        # Validate user_type specific requirements
        user_type = claims.get("user_type")
        
        if user_type == "admin":
            if "organization_id" not in claims or claims["organization_id"] is None:
                raise ValueError("Admin user must have organization_id in claims")
            
            if "admin_role" not in claims or claims["admin_role"] is None:
                raise ValueError("Admin user must have admin_role in claims")
        
        elif user_type == "candidate":
            # Candidates should NOT have these fields (or they should be null)
            if claims.get("organization_id") is not None:
                raise ValueError("Candidate user cannot have organization_id")
            
            if claims.get("admin_role") is not None:
                raise ValueError("Candidate user cannot have admin_role")
