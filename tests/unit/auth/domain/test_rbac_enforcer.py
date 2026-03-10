"""
Unit Tests for RBACEnforcer

Tests role-based access control permission checking.
"""

import pytest
from app.auth.domain.rbac_enforcer import RBACEnforcer, Permission
from app.shared.auth_context import IdentityContext, UserType, AdminRole
from app.shared.errors import AuthorizationError


class TestRBACEnforcer:
    """Test suite for RBACEnforcer"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.enforcer = RBACEnforcer()
        
        # Create test identity contexts
        self.superadmin_context = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        self.admin_context = IdentityContext(
            user_id=2,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        self.read_only_context = IdentityContext(
            user_id=3,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.READ_ONLY,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        self.candidate_context = IdentityContext(
            user_id=4,
            user_type=UserType.CANDIDATE,
            candidate_id=4,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
    
    # ========================================================================
    # SUPERADMIN PERMISSION TESTS
    # ========================================================================
    
    def test_superadmin_has_all_permissions(self):
        """Test that superadmin has all permissions"""
        for permission in Permission:
            assert self.enforcer.has_permission(self.superadmin_context, permission)
    
    def test_superadmin_can_manage_admins(self):
        """Test that superadmin can manage admins"""
        assert self.enforcer.has_permission(
            self.superadmin_context,
            Permission.MANAGE_ADMINS
        )
    
    def test_superadmin_can_manage_organization(self):
        """Test that superadmin can manage organization"""
        assert self.enforcer.has_permission(
            self.superadmin_context,
            Permission.MANAGE_ORGANIZATION
        )
    
    def test_superadmin_require_permission_succeeds(self):
        """Test that superadmin passes permission requirement"""
        # Should not raise exception
        self.enforcer.require_permission(
            self.superadmin_context,
            Permission.MANAGE_ADMINS
        )
    
    # ========================================================================
    # ADMIN PERMISSION TESTS
    # ========================================================================
    
    def test_admin_can_create_templates(self):
        """Test that admin can create templates"""
        assert self.enforcer.has_permission(
            self.admin_context,
            Permission.CREATE_TEMPLATES
        )
    
    def test_admin_can_manage_candidates(self):
        """Test that admin can manage candidates"""
        assert self.enforcer.has_permission(
            self.admin_context,
            Permission.MANAGE_CANDIDATES
        )
    
    def test_admin_cannot_manage_admins(self):
        """Test that admin cannot manage other admins"""
        assert not self.enforcer.has_permission(
            self.admin_context,
            Permission.MANAGE_ADMINS
        )
    
    def test_admin_cannot_manage_organization(self):
        """Test that admin cannot manage organization"""
        assert not self.enforcer.has_permission(
            self.admin_context,
            Permission.MANAGE_ORGANIZATION
        )
    
    def test_admin_require_permission_fails_for_manage_admins(self):
        """Test that admin fails permission requirement for manage_admins"""
        with pytest.raises(AuthorizationError) as exc_info:
            self.enforcer.require_permission(
                self.admin_context,
                Permission.MANAGE_ADMINS
            )
        
        assert "MANAGE_ADMINS" in str(exc_info.value) or "manage_admins" in str(exc_info.value)
    
    # ========================================================================
    # READ_ONLY PERMISSION TESTS
    # ========================================================================
    
    def test_read_only_can_view_submissions(self):
        """Test that read_only can view submissions"""
        assert self.enforcer.has_permission(
            self.read_only_context,
            Permission.VIEW_SUBMISSIONS
        )
    
    def test_read_only_can_download_reports(self):
        """Test that read_only can download reports"""
        assert self.enforcer.has_permission(
            self.read_only_context,
            Permission.DOWNLOAD_REPORTS
        )
    
    def test_read_only_can_view_analytics(self):
        """Test that read_only can view analytics"""
        assert self.enforcer.has_permission(
            self.read_only_context,
            Permission.VIEW_ANALYTICS
        )
    
    def test_read_only_cannot_create_templates(self):
        """Test that read_only cannot create templates"""
        assert not self.enforcer.has_permission(
            self.read_only_context,
            Permission.CREATE_TEMPLATES
        )
    
    def test_read_only_cannot_manage_candidates(self):
        """Test that read_only cannot manage candidates"""
        assert not self.enforcer.has_permission(
            self.read_only_context,
            Permission.MANAGE_CANDIDATES
        )
    
    def test_read_only_require_permission_fails_for_create_templates(self):
        """Test that read_only fails permission requirement for create_templates"""
        with pytest.raises(AuthorizationError):
            self.enforcer.require_permission(
                self.read_only_context,
                Permission.CREATE_TEMPLATES
            )
    
    # ========================================================================
    # CANDIDATE PERMISSION TESTS
    # ========================================================================
    
    def test_candidate_has_no_permissions(self):
        """Test that candidates have no permissions"""
        for permission in Permission:
            assert not self.enforcer.has_permission(self.candidate_context, permission)
    
    def test_candidate_require_permission_always_fails(self):
        """Test that candidates always fail permission requirements"""
        with pytest.raises(AuthorizationError):
            self.enforcer.require_permission(
                self.candidate_context,
                Permission.VIEW_SUBMISSIONS
            )


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
