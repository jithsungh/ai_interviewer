"""
Unit Tests for Scope Enforcement

Tests tenant isolation and candidate scope enforcement.
"""

import pytest
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole
from app.shared.auth_context.scope import (
    enforce_organization_scope,
    enforce_candidate_scope,
    require_organization_admin
)
from app.shared.errors import AuthorizationError, TenantIsolationViolation


class TestEnforceOrganizationScope:
    """Test enforce_organization_scope()"""
    
    def test_superadmin_can_access_any_organization(self):
        """Test superadmin can access all organizations"""
        superadmin = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise for any organization
        enforce_organization_scope(superadmin, 1)
        enforce_organization_scope(superadmin, 2)
        enforce_organization_scope(superadmin, 999)
    
    def test_admin_can_access_own_organization(self):
        """Test admin can access their own organization"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise for own organization
        enforce_organization_scope(admin, 1)
    
    def test_admin_cannot_access_different_organization(self):
        """Test admin cannot access different organization"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise for different organization
        with pytest.raises(TenantIsolationViolation, match="Cannot access resources from organization 2"):
            enforce_organization_scope(admin, 2)
    
    def test_candidate_cannot_access_organization(self):
        """Test candidate cannot access organization resources"""
        candidate = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise for any organization
        with pytest.raises(AuthorizationError, match="Admin access required"):
            enforce_organization_scope(candidate, 1)


class TestEnforceCandidateScope:
    """Test enforce_candidate_scope()"""
    
    def test_candidate_can_access_own_resources(self):
        """Test candidate can access their own resources"""
        candidate = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise for own candidate_id (user_id == candidate_id)
        enforce_candidate_scope(candidate, 123)
    
    def test_candidate_cannot_access_other_candidate_resources(self):
        """Test candidate cannot access another candidate's resources"""
        candidate = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise for different candidate_id
        with pytest.raises(AuthorizationError, match="Cannot access resources belonging to candidate 456"):
            enforce_candidate_scope(candidate, 456)
    
    def test_admin_cannot_access_candidate_resources(self):
        """Test admin cannot access candidate-scoped resources"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise because user is not candidate
        with pytest.raises(AuthorizationError, match="Candidate access required"):
            enforce_candidate_scope(admin, 123)


class TestRequireOrganizationAdmin:
    """Test require_organization_admin()"""
    
    def test_superadmin_can_access_any_organization_with_any_role(self):
        """Test superadmin can access any organization with any minimum role"""
        superadmin = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise for any organization/role combination
        require_organization_admin(superadmin, 1, minimum_role="superadmin")
        require_organization_admin(superadmin, 2, minimum_role="admin")
        require_organization_admin(superadmin, 3, minimum_role="read_only")
    
    def test_admin_can_access_with_matching_role(self):
        """Test admin can access their org with matching role"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise for own org with admin role
        require_organization_admin(admin, 1, minimum_role="admin")
        
        # Should not raise for lower role requirement
        require_organization_admin(admin, 1, minimum_role="read_only")
    
    def test_admin_cannot_access_when_role_too_low(self):
        """Test admin cannot access when their role is too low"""
        read_only_admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.READ_ONLY,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise because read_only < admin
        with pytest.raises(AuthorizationError, match="Insufficient privileges"):
            require_organization_admin(read_only_admin, 1, minimum_role="admin")
    
    def test_admin_cannot_access_different_organization(self):
        """Test admin cannot access different organization"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise for different organization
        with pytest.raises(TenantIsolationViolation, match="Cannot access organization 2"):
            require_organization_admin(admin, 2, minimum_role="admin")
    
    def test_candidate_cannot_access_organization_resources(self):
        """Test candidate cannot access organization resources"""
        candidate = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should raise because not admin
        with pytest.raises(AuthorizationError, match="Admin access required"):
            require_organization_admin(candidate, 1, minimum_role="read_only")
    
    def test_role_hierarchy(self):
        """Test role hierarchy is enforced correctly"""
        superadmin = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        read_only = IdentityContext(
            user_id=99,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.READ_ONLY,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Superadmin can do anything
        require_organization_admin(superadmin, 1, minimum_role="superadmin")
        require_organization_admin(superadmin, 1, minimum_role="admin")
        require_organization_admin(superadmin, 1, minimum_role="read_only")
        
        # Admin can do admin and read_only
        with pytest.raises(AuthorizationError):
            require_organization_admin(admin, 1, minimum_role="superadmin")
        require_organization_admin(admin, 1, minimum_role="admin")
        require_organization_admin(admin, 1, minimum_role="read_only")
        
        # Read-only can only do read_only
        with pytest.raises(AuthorizationError):
            require_organization_admin(read_only, 1, minimum_role="superadmin")
        with pytest.raises(AuthorizationError):
            require_organization_admin(read_only, 1, minimum_role="admin")
        require_organization_admin(read_only, 1, minimum_role="read_only")
