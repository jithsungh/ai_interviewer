"""
Unit Tests for FastAPI Dependencies

Tests dependency injection functions for auth context.
"""

import pytest
from unittest.mock import Mock
from fastapi import HTTPException
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole
from app.shared.auth_context.dependencies import (
    get_identity,
    get_optional_identity,
    require_admin,
    require_candidate,
    require_superadmin
)
from app.shared.errors import AuthenticationError, AuthorizationError


class TestGetIdentity:
    """Test get_identity() dependency"""
    
    def test_returns_identity_when_present(self):
        """Test returns identity from request.state"""
        mock_request = Mock()
        mock_request.state.identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        identity = get_identity(mock_request)
        
        assert identity.user_id == 42
        assert identity.user_type == UserType.ADMIN
    
    def test_raises_when_identity_missing(self):
        """Test raises AuthenticationError when identity not in request.state"""
        mock_request = Mock()
        mock_request.state = Mock(spec=[])  # No identity attribute
        
        with pytest.raises(AuthenticationError, match="Authentication required"):
            get_identity(mock_request)


class TestGetOptionalIdentity:
    """Test get_optional_identity() dependency"""
    
    def test_returns_identity_when_present(self):
        """Test returns identity when present"""
        mock_request = Mock()
        mock_request.state.identity = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        identity = get_optional_identity(mock_request)
        
        assert identity.user_id == 123
        assert identity.user_type == UserType.CANDIDATE
    
    def test_returns_none_when_missing(self):
        """Test returns None when identity not present"""
        mock_request = Mock()
        mock_request.state = Mock(spec=[])  # No identity attribute
        
        identity = get_optional_identity(mock_request)
        
        assert identity is None


class TestRequireAdmin:
    """Test require_admin() dependency"""
    
    def test_allows_admin_user(self):
        """Test allows admin user"""
        admin_identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise
        identity = require_admin(admin_identity)
        
        assert identity == admin_identity
    
    def test_allows_superadmin_user(self):
        """Test allows superadmin user"""
        superadmin_identity = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise
        identity = require_admin(superadmin_identity)
        
        assert identity == superadmin_identity
    
    def test_allows_readonly_admin(self):
        """Test allows read-only admin"""
        readonly_identity = IdentityContext(
            user_id=99,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.READ_ONLY,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise
        identity = require_admin(readonly_identity)
        
        assert identity == readonly_identity
    
    def test_rejects_candidate_user(self):
        """Test rejects candidate user"""
        candidate_identity = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        with pytest.raises(AuthorizationError, match="Admin access required"):
            require_admin(candidate_identity)


class TestRequireCandidate:
    """Test require_candidate() dependency"""
    
    def test_allows_candidate_user(self):
        """Test allows candidate user"""
        candidate_identity = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise
        identity = require_candidate(candidate_identity)
        
        assert identity == candidate_identity
    
    def test_rejects_admin_user(self):
        """Test rejects admin user"""
        admin_identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        with pytest.raises(AuthorizationError, match="Candidate access required"):
            require_candidate(admin_identity)


class TestRequireSuperadmin:
    """Test require_superadmin() dependency"""
    
    def test_allows_superadmin_user(self):
        """Test allows superadmin user"""
        superadmin_identity = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Should not raise
        identity = require_superadmin(superadmin_identity)
        
        assert identity == superadmin_identity
    
    def test_rejects_regular_admin(self):
        """Test rejects regular admin"""
        admin_identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        with pytest.raises(AuthorizationError, match="Superadmin access required"):
            require_superadmin(admin_identity)
    
    def test_rejects_readonly_admin(self):
        """Test rejects read-only admin"""
        readonly_identity = IdentityContext(
            user_id=99,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.READ_ONLY,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        with pytest.raises(AuthorizationError, match="Superadmin access required"):
            require_superadmin(readonly_identity)
    
    def test_rejects_candidate_user(self):
        """Test rejects candidate user"""
        candidate_identity = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        with pytest.raises(AuthorizationError, match="Superadmin access required"):
            require_superadmin(candidate_identity)
