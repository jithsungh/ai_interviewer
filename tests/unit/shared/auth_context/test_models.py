"""
Unit Tests for Auth Context Models

Tests IdentityContext, UserType, AdminRole, and TaskContext.
"""

import pytest
import time
from app.shared.auth_context.models import (
    IdentityContext,
    UserType,
    AdminRole,
    TaskContext
)


class TestUserType:
    """Test UserType enum"""
    
    def test_user_type_values(self):
        """Test UserType has correct values"""
        assert UserType.ADMIN.value == "admin"
        assert UserType.CANDIDATE.value == "candidate"
    
    def test_user_type_exhaustive(self):
        """Test UserType has exactly 2 values (admin, candidate)"""
        assert len(UserType) == 2
        assert set(UserType) == {UserType.ADMIN, UserType.CANDIDATE}


class TestAdminRole:
    """Test AdminRole enum"""
    
    def test_admin_role_values(self):
        """Test AdminRole has correct schema-aligned values"""
        assert AdminRole.SUPERADMIN.value == "superadmin"
        assert AdminRole.ADMIN.value == "admin"
        assert AdminRole.READ_ONLY.value == "read_only"
    
    def test_admin_role_exhaustive(self):
        """Test AdminRole has exactly 3 values"""
        assert len(AdminRole) == 3
        assert set(AdminRole) == {AdminRole.SUPERADMIN, AdminRole.ADMIN, AdminRole.READ_ONLY}


class TestIdentityContext:
    """Test IdentityContext model"""
    
    def test_admin_identity_creation(self):
        """Test creating admin identity context"""
        identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=3,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        assert identity.user_id == 42
        assert identity.user_type == UserType.ADMIN
        assert identity.organization_id == 1
        assert identity.admin_role == AdminRole.ADMIN
        assert identity.token_version == 3
    
    def test_candidate_identity_creation(self):
        """Test creating candidate identity context"""
        identity = IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            candidate_id=123,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        assert identity.user_id == 123
        assert identity.user_type == UserType.CANDIDATE
        assert identity.organization_id is None
        assert identity.admin_role is None
    
    def test_admin_without_organization_raises_error(self):
        """Test admin must have organization_id"""
        with pytest.raises(ValueError, match="Admin user must have organization_id"):
            IdentityContext(
                user_id=42,
                user_type=UserType.ADMIN,
                organization_id=None,  # Invalid
                admin_role=AdminRole.ADMIN,
                token_version=1,
                issued_at=1700000000,
                expires_at=1700003600
            )
    
    def test_admin_without_role_raises_error(self):
        """Test admin must have admin_role"""
        with pytest.raises(ValueError, match="Admin user must have admin_role"):
            IdentityContext(
                user_id=42,
                user_type=UserType.ADMIN,
                organization_id=1,
                admin_role=None,  # Invalid
                token_version=1,
                issued_at=1700000000,
                expires_at=1700003600
            )
    
    def test_candidate_with_organization_raises_error(self):
        """Test candidate cannot have organization_id"""
        with pytest.raises(ValueError, match="Candidate user cannot have organization_id"):
            IdentityContext(
                user_id=123,
                user_type=UserType.CANDIDATE,
                organization_id=1,  # Invalid
                admin_role=None,
                token_version=1,
                issued_at=1700000000,
                expires_at=1700003600
            )
    
    def test_candidate_with_admin_role_raises_error(self):
        """Test candidate cannot have admin_role"""
        with pytest.raises(ValueError, match="Candidate user cannot have admin_role"):
            IdentityContext(
                user_id=123,
                user_type=UserType.CANDIDATE,
                organization_id=None,
                admin_role=AdminRole.ADMIN,  # Invalid
                token_version=1,
                issued_at=1700000000,
                expires_at=1700003600
            )
    
    def test_invalid_timestamps_raises_error(self):
        """Test issued_at must be before expires_at"""
        with pytest.raises(ValueError, match="issued_at must be before expires_at"):
            IdentityContext(
                user_id=42,
                user_type=UserType.ADMIN,
                organization_id=1,
                admin_role=AdminRole.ADMIN,
                token_version=1,
                issued_at=1700003600,
                expires_at=1700000000  # Before issued_at (invalid)
            )
    
    def test_is_admin(self):
        """Test is_admin() method"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
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
        
        assert admin.is_admin() is True
        assert candidate.is_admin() is False
    
    def test_is_candidate(self):
        """Test is_candidate() method"""
        admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
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
        
        assert admin.is_candidate() is False
        assert candidate.is_candidate() is True
    
    def test_is_superadmin(self):
        """Test is_superadmin() method"""
        superadmin = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        regular_admin = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        assert superadmin.is_superadmin() is True
        assert regular_admin.is_superadmin() is False
    
    def test_is_expired(self):
        """Test is_expired() method"""
        # Expired token (expires in past)
        expired = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600  # Way in the past
        )
        
        # Valid token (expires in future)
        valid = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=int(time.time()) - 60,
            expires_at=int(time.time()) + 3600  # 1 hour from now
        )
        
        assert expired.is_expired() is True
        assert valid.is_expired() is False
    
    def test_belongs_to_organization(self):
        """Test belongs_to_organization() method"""
        admin_org_1 = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
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
        
        assert admin_org_1.belongs_to_organization(1) is True
        assert admin_org_1.belongs_to_organization(2) is False
        assert candidate.belongs_to_organization(1) is False
    
    def test_can_access_organization(self):
        """Test can_access_organization() method"""
        superadmin = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.SUPERADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        admin_org_1 = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
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
        
        # Superadmin can access all orgs
        assert superadmin.can_access_organization(1) is True
        assert superadmin.can_access_organization(2) is True
        
        # Regular admin can only access own org
        assert admin_org_1.can_access_organization(1) is True
        assert admin_org_1.can_access_organization(2) is False
        
        # Candidate cannot access any org
        assert candidate.can_access_organization(1) is False
    
    def test_to_dict(self):
        """Test to_dict() serialization"""
        identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=3,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        result = identity.to_dict()
        
        assert result == {
            "user_id": 42,
            "user_type": "admin",
            "organization_id": 1,
            "admin_role": "admin",
            "token_version": 3,
            "issued_at": 1700000000,
            "expires_at": 1700003600
        }
    
    def test_identity_is_frozen(self):
        """Test IdentityContext is immutable (frozen)"""
        identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            identity.user_id = 999


class TestTaskContext:
    """Test TaskContext model"""
    
    def test_task_context_creation(self):
        """Test creating TaskContext"""
        task_context = TaskContext(
            request_id="req_abc123",
            user_id=42,
            user_type="admin",
            organization_id=1,
            submission_id=456
        )
        
        assert task_context.request_id == "req_abc123"
        assert task_context.user_id == 42
        assert task_context.user_type == "admin"
        assert task_context.organization_id == 1
        assert task_context.submission_id == 456
    
    def test_from_identity(self):
        """Test TaskContext.from_identity()"""
        identity = IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
        
        task_context = TaskContext.from_identity(
            identity=identity,
            request_id="req_abc123",
            submission_id=456
        )
        
        assert task_context.user_id == 42
        assert task_context.user_type == "admin"
        assert task_context.organization_id == 1
        assert task_context.submission_id == 456
        assert task_context.request_id == "req_abc123"
    
    def test_to_dict(self):
        """Test TaskContext serialization"""
        task_context = TaskContext(
            request_id="req_abc123",
            user_id=42,
            user_type="admin",
            organization_id=1,
            submission_id=456
        )
        
        result = task_context.to_dict()
        
        assert result == {
            "request_id": "req_abc123",
            "user_id": 42,
            "user_type": "admin",
            "organization_id": 1,
            "submission_id": 456
        }
