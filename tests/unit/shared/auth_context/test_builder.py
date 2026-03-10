"""
Unit Tests for Identity Builder

Tests transformation of JWT claims into IdentityContext.
"""

import pytest
from app.shared.auth_context.builder import IdentityBuilder
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole


class TestIdentityBuilder:
    """Test IdentityBuilder class"""
    
    def test_build_admin_identity_from_claims(self):
        """Test building admin identity from JWT claims"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            "organization_id": 1,
            "admin_role": "admin",
            "token_version": 3,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        identity = IdentityBuilder.from_jwt_claims(claims)
        
        assert identity.user_id == 42
        assert identity.user_type == UserType.ADMIN
        assert identity.organization_id == 1
        assert identity.admin_role == AdminRole.ADMIN
        assert identity.token_version == 3
        assert identity.issued_at == 1700000000
        assert identity.expires_at == 1700003600
    
    def test_build_candidate_identity_from_claims(self):
        """Test building candidate identity from JWT claims"""
        claims = {
            "sub": 123,
            "user_type": "candidate",
            "candidate_id": 123,
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        identity = IdentityBuilder.from_jwt_claims(claims)
        
        assert identity.user_id == 123
        assert identity.user_type == UserType.CANDIDATE
        assert identity.organization_id is None
        assert identity.admin_role is None
    
    def test_build_superadmin_identity(self):
        """Test building superadmin identity"""
        claims = {
            "sub": 1,
            "user_type": "admin",
            "organization_id": 1,
            "admin_role": "superadmin",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        identity = IdentityBuilder.from_jwt_claims(claims)
        
        assert identity.is_superadmin() is True
    
    def test_invalid_user_type_raises_error(self):
        """Test invalid user_type raises ValueError"""
        claims = {
            "sub": 42,
            "user_type": "invalid",  # Invalid
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Invalid user_type: invalid"):
            IdentityBuilder.from_jwt_claims(claims)
    
    def test_admin_without_organization_raises_error(self):
        """Test admin claims without organization_id raises error"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            # Missing organization_id
            "admin_role": "admin",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Admin user must have organization_id"):
            IdentityBuilder.from_jwt_claims(claims)
    
    def test_admin_without_role_raises_error(self):
        """Test admin claims without admin_role raises error"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            "organization_id": 1,
            # Missing admin_role
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Admin user must have admin_role"):
            IdentityBuilder.from_jwt_claims(claims)
    
    def test_invalid_admin_role_raises_error(self):
        """Test invalid admin_role raises ValueError"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            "organization_id": 1,
            "admin_role": "invalid_role",  # Invalid
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Invalid admin_role: invalid_role"):
            IdentityBuilder.from_jwt_claims(claims)
    
    def test_missing_sub_raises_error(self):
        """Test missing 'sub' claim raises KeyError"""
        claims = {
            # Missing "sub"
            "user_type": "candidate",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(KeyError):
            IdentityBuilder.from_jwt_claims(claims)


class TestClaimsValidation:
    """Test validate_claims_structure()"""
    
    def test_valid_admin_claims(self):
        """Test valid admin claims pass validation"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            "organization_id": 1,
            "admin_role": "admin",
            "token_version": 3,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        # Should not raise
        IdentityBuilder.validate_claims_structure(claims)
    
    def test_valid_candidate_claims(self):
        """Test valid candidate claims pass validation"""
        claims = {
            "sub": 123,
            "user_type": "candidate",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        # Should not raise
        IdentityBuilder.validate_claims_structure(claims)
    
    def test_missing_required_field_raises_error(self):
        """Test missing required field raises ValueError"""
        claims = {
            "sub": 42,
            # Missing "user_type"
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Missing required claim: user_type"):
            IdentityBuilder.validate_claims_structure(claims)
    
    def test_invalid_sub_type_raises_error(self):
        """Test non-integer 'sub' raises ValueError"""
        claims = {
            "sub": "not_an_integer",  # Invalid type
            "user_type": "candidate",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Claim 'sub'.*must be integer"):
            IdentityBuilder.validate_claims_structure(claims)
    
    def test_admin_without_organization_in_claims_raises_error(self):
        """Test admin claims without organization_id raises error"""
        claims = {
            "sub": 42,
            "user_type": "admin",
            "organization_id": None,  # Invalid for admin
            "admin_role": "admin",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Admin user must have organization_id in claims"):
            IdentityBuilder.validate_claims_structure(claims)
    
    def test_candidate_with_organization_raises_error(self):
        """Test candidate claims with organization_id raises error"""
        claims = {
            "sub": 123,
            "user_type": "candidate",
            "organization_id": 1,  # Invalid for candidate
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Candidate user cannot have organization_id"):
            IdentityBuilder.validate_claims_structure(claims)
    
    def test_candidate_with_admin_role_raises_error(self):
        """Test candidate claims with admin_role raises error"""
        claims = {
            "sub": 123,
            "user_type": "candidate",
            "admin_role": "admin",  # Invalid for candidate
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        with pytest.raises(ValueError, match="Candidate user cannot have admin_role"):
            IdentityBuilder.validate_claims_structure(claims)
