"""
Unit Tests for AuthService

Tests authentication service business logic with mocked dependencies.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch
from sqlalchemy.orm import Session

from app.auth.domain.auth_service import AuthService
from app.auth.domain.contracts import (
    RegisterAdminCommand,
    LoginCommand,
    RefreshTokenCommand,
    LogoutCommand,
    ValidateTokenCommand,
)
from app.auth.domain.password_hasher import PasswordHasher
from app.auth.domain.jwt_service import JWTService
from app.auth.persistence.models import User, Admin, RefreshToken
from app.shared.auth_context import AdminRole, UserType
from app.shared.errors import (
    ValidationError,
    AuthenticationError,
    ConflictError,
)


class TestAuthServiceRegistration:
    """Test suite for admin registration"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.session = MagicMock(spec=Session)
        self.password_hasher = MagicMock(spec=PasswordHasher)
        self.jwt_service = MagicMock(spec=JWTService)
        
        self.auth_service = AuthService(
            session=self.session,
            password_hasher=self.password_hasher,
            jwt_service=self.jwt_service
        )
    
    def test_register_admin_validates_password_complexity(self):
        """Test that registration validates password complexity"""
        # Configure password hasher to reject weak password
        self.password_hasher.validate_complexity.side_effect = ValidationError(
            message="Password too weak",
            field="password"
        )
        
        command = RegisterAdminCommand(
            email="admin@example.com",
            password="weak",
            admin_role="admin",
            organization_id=1,
            full_name="Test Admin"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            self.auth_service.register_admin(command)
        
        assert "password" in str(exc_info.value).lower()
    
    def test_register_admin_checks_email_uniqueness(self):
        """Test that registration checks for duplicate emails"""
        # Mock password hasher
        self.password_hasher.hash.return_value = "hashed_password"
        
        # Mock session to return existing user
        existing_user = Mock(spec=User)
        self.session.query().filter().first.return_value = existing_user
        
        command = RegisterAdminCommand(
            email="existing@example.com",
            password="ValidPass123!",
            admin_role="admin",
            organization_id=1,
            full_name="Test Admin"
        )
        
        with pytest.raises(ConflictError):
            self.auth_service.register_admin(command)
    
    def test_register_admin_hashes_password_with_bcrypt(self):
        """Test that registration hashes password before storage"""
        # Mock dependencies
        self.password_hasher.validate_complexity.return_value = None
        self.password_hasher.hash.return_value = "bcrypt_hashed_password"
        self.session.query.return_value.scalar.return_value = False  # No existing user
        self.session.execute.return_value.first.return_value = (1, 'active')  # Org exists and active
        
        command = RegisterAdminCommand(
            email="newadmin@example.com",
            password="ValidPass123!",
            admin_role="admin",
            organization_id=1,
            full_name="New Admin"
        )
        
        self.auth_service.register_admin(command)
        
        # Verify password hasher was called
        self.password_hasher.hash.assert_called_once_with("ValidPass123!")


class TestAuthServiceLogin:
    """Test suite for login"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.session = MagicMock(spec=Session)
        self.password_hasher = MagicMock(spec=PasswordHasher)
        self.jwt_service = MagicMock(spec=JWTService)
        
        self.auth_service = AuthService(
            session=self.session,
            password_hasher=self.password_hasher,
            jwt_service=self.jwt_service
        )
    
    def test_login_fails_for_nonexistent_user(self):
        """Test that login fails for non-existent email"""
        # Mock session to return no user
        self.session.query().filter().first.return_value = None
        
        command = LoginCommand(
            email="nonexistent@example.com",
            password="SomePassword123!"
        )
        
        with pytest.raises(AuthenticationError):
            self.auth_service.login(command)
    
    def test_login_fails_for_incorrect_password(self):
        """Test that login fails for incorrect password"""
        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.password_hash = "correct_hash"
        mock_user.user_type = "admin"
        mock_user.is_active = True
        
        self.session.query().filter().first.return_value = mock_user
        
        # Configure password hasher to reject password
        self.password_hasher.verify.return_value = False
        
        command = LoginCommand(
            email="admin@example.com",
            password="WrongPassword123!"
        )
        
        with pytest.raises(AuthenticationError):
            self.auth_service.login(command)
        
        # Verify password was checked
        self.password_hasher.verify.assert_called_once_with(
            "WrongPassword123!",
            "correct_hash"
        )
    
    def test_login_generates_jwt_and_refresh_token(self):
        """Test that successful login generates both tokens"""
        # Mock user and admin
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = "admin@example.com"
        mock_user.password_hash = "hash"
        mock_user.user_type = "admin"
        mock_user.status = "active"
        mock_user.token_version = 1
        mock_user.last_login_at = None
        mock_user.created_at = datetime.now()
        
        mock_admin = Mock(spec=Admin)
        mock_admin.id = 10
        mock_admin.user_id = 1
        mock_admin.role = "admin"
        mock_admin.organization_id = 1
        mock_admin.status = "active"
        mock_admin.first_name = "Test"
        mock_admin.last_name = "Admin"
        
        # Configure session mocks
        # query(User).filter(...).first() for user lookup
        self.session.query.return_value.filter.return_value.first.return_value = mock_user
        # query(Admin).filter_by(...).first() for admin lookup
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_admin
        # execute(...).first() for org status lookup
        self.session.execute.return_value.first.return_value = ('active',)
        
        # Configure password verification
        self.password_hasher.verify.return_value = True
        
        # Configure token generation
        self.jwt_service.generate_access_token.return_value = "jwt_token"
        self.jwt_service.generate_refresh_token.return_value = "refresh_token_raw"
        self.jwt_service.hash_refresh_token.return_value = "refresh_token_hash"
        self.jwt_service.get_refresh_token_expiry.return_value = datetime.now() + timedelta(days=30)
        self.jwt_service.access_token_ttl = timedelta(minutes=15)
        
        command = LoginCommand(
            email="admin@example.com",
            password="CorrectPassword123!"
        )
        
        result = self.auth_service.login(command)
        
        # Verify tokens were generated
        assert result.access_token == "jwt_token"
        assert result.refresh_token == "refresh_token_raw"
        self.jwt_service.generate_access_token.assert_called_once()
        self.jwt_service.generate_refresh_token.assert_called_once()


class TestAuthServiceRefreshToken:
    """Test suite for token refresh"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.session = MagicMock(spec=Session)
        self.password_hasher = MagicMock(spec=PasswordHasher)
        self.jwt_service = MagicMock(spec=JWTService)
        
        self.auth_service = AuthService(
            session=self.session,
            password_hasher=self.password_hasher,
            jwt_service=self.jwt_service
        )
    
    def test_refresh_fails_for_invalid_token(self):
        """Test that refresh fails for invalid token"""
        # Mock token hashing
        self.jwt_service.hash_refresh_token.return_value = "token_hash"
        
        # Mock session to return no token
        self.session.query.return_value.filter_by.return_value.first.return_value = None
        
        command = RefreshTokenCommand(refresh_token="invalid_token")
        
        with pytest.raises(AuthenticationError):
            self.auth_service.refresh_token(command)
    
    def test_refresh_fails_for_expired_token(self):
        """Test that refresh fails for expired token"""
        # Mock token
        mock_token = Mock(spec=RefreshToken)
        mock_token.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)  # Expired
        mock_token.revoked_at = None
        
        self.jwt_service.hash_refresh_token.return_value = "token_hash"
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_token
        
        command = RefreshTokenCommand(refresh_token="expired_token")
        
        with pytest.raises(AuthenticationError):
            self.auth_service.refresh_token(command)
    
    def test_refresh_fails_for_revoked_token(self):
        """Test that refresh fails for revoked token"""
        # Mock revoked token
        mock_token = Mock(spec=RefreshToken)
        mock_token.expires_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
        mock_token.revoked_at = datetime(2025, 1, 1, tzinfo=timezone.utc)  # Already revoked
        mock_token.user_id = 1
        
        self.jwt_service.hash_refresh_token.return_value = "token_hash"
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_token
        
        command = RefreshTokenCommand(refresh_token="revoked_token")
        
        with pytest.raises(AuthenticationError):
            self.auth_service.refresh_token(command)


class TestAuthServiceValidation:
    """Test suite for token validation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.session = MagicMock(spec=Session)
        self.password_hasher = MagicMock(spec=PasswordHasher)
        self.jwt_service = MagicMock(spec=JWTService)
        
        self.auth_service = AuthService(
            session=self.session,
            password_hasher=self.password_hasher,
            jwt_service=self.jwt_service
        )
    
    def test_validate_decodes_jwt_correctly(self):
        """Test that validation decodes JWT and extracts claims"""
        # Mock JWT verification
        self.jwt_service.verify_access_token.return_value = {
            "sub": "1",
            "type": "admin",
            "admin_id": "10",
            "organization_id": "1",
            "role": "admin",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        # Mock user lookup
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.status = "active"
        mock_user.token_version = 1
        
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_user
        self.session.execute.return_value.first.return_value = ('active',)
        
        command = ValidateTokenCommand(access_token="valid.jwt.token")
        
        result = self.auth_service.validate_access_token(command)
        
        # Verify auth context
        assert result.auth_context.user_id == "1"
        assert result.auth_context.user_type == UserType.ADMIN
        assert result.valid is True
    
    def test_validate_fails_for_inactive_user(self):
        """Test that validation fails for inactive user"""
        # Mock JWT verification
        self.jwt_service.verify_access_token.return_value = {
            "sub": "1",
            "type": "admin",
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        # Mock inactive user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.status = "inactive"
        
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        command = ValidateTokenCommand(access_token="valid.jwt.token")
        
        result = self.auth_service.validate_access_token(command)
        assert result.valid is False
        assert result.error == 'user_inactive'
    
    def test_validate_fails_for_token_version_mismatch(self):
        """Test that validation fails when token version doesn't match"""
        # Mock JWT verification
        self.jwt_service.verify_access_token.return_value = {
            "sub": "1",
            "type": "admin",
            "token_version": 1,
            "iat": 1700000000,
            "exp": 1700003600
        }
        
        # Mock user with different token version (e.g., after logout)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.status = "active"
        mock_user.token_version = 2  # Incremented, invalidating old tokens
        
        self.session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        command = ValidateTokenCommand(access_token="old.jwt.token")
        
        result = self.auth_service.validate_access_token(command)
        assert result.valid is False
        assert result.error == 'token_revoked'


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
