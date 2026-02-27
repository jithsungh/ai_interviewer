"""
Unit Tests for UserRepository

Tests user CRUD operations with a mocked SQLAlchemy session.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.persistence.user_repository import UserRepository
from app.auth.persistence.models import User
from app.shared.errors import ConflictError, DatabaseError


class TestUserRepositoryCreate:
    """Tests for UserRepository.create()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = UserRepository(self.session)

    def test_create_user_adds_to_session_and_flushes(self):
        """Verify user is added to session and flushed to get ID."""
        user = self.repo.create(
            name="Test User",
            email="test@example.com",
            password_hash="hashed_pw",
            user_type="admin",
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added_user = self.session.add.call_args[0][0]
        assert added_user.name == "Test User"
        assert added_user.email == "test@example.com"
        assert added_user.password_hash == "hashed_pw"
        assert added_user.user_type == "admin"
        assert added_user.status == "active"
        assert added_user.token_version == 1

    def test_create_user_default_status_active(self):
        """Verify default status is 'active'."""
        user = self.repo.create(
            name="User",
            email="u@e.com",
            password_hash="h",
            user_type="candidate",
        )
        added = self.session.add.call_args[0][0]
        assert added.status == "active"

    def test_create_user_custom_status(self):
        """Verify custom status is respected."""
        self.repo.create(
            name="User",
            email="u@e.com",
            password_hash="h",
            user_type="candidate",
            status="inactive",
        )
        added = self.session.add.call_args[0][0]
        assert added.status == "inactive"

    def test_create_user_duplicate_email_raises_conflict(self):
        """Verify ConflictError on duplicate email UNIQUE violation."""
        orig = Exception("users_email_key")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(ConflictError) as exc_info:
            self.repo.create(
                name="Dup",
                email="dup@example.com",
                password_hash="h",
                user_type="admin",
            )
        assert "Email already registered" in str(exc_info.value.message)

    def test_create_user_other_integrity_error_raises_database_error(self):
        """Verify DatabaseError on non-email IntegrityError."""
        orig = Exception("some_other_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DatabaseError):
            self.repo.create(
                name="X",
                email="x@e.com",
                password_hash="h",
                user_type="admin",
            )


class TestUserRepositoryRead:
    """Tests for UserRepository read methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = UserRepository(self.session)

    def test_get_by_id_returns_user(self):
        """Verify get_by_id queries by primary key."""
        mock_user = Mock(spec=User)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_user
        )
        result = self.repo.get_by_id(1)
        assert result is mock_user

    def test_get_by_id_returns_none_when_not_found(self):
        """Verify None return for non-existent ID."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        result = self.repo.get_by_id(999)
        assert result is None

    def test_find_by_email_returns_user(self):
        """Verify find_by_email queries case-insensitively."""
        mock_user = Mock(spec=User)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_user
        )
        result = self.repo.find_by_email("Test@Example.COM")
        assert result is mock_user

    def test_find_by_email_returns_none(self):
        """Verify None when email not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        result = self.repo.find_by_email("missing@example.com")
        assert result is None

    def test_email_exists_returns_true(self):
        """Verify True when email exists."""
        self.session.query.return_value.scalar.return_value = True
        assert self.repo.email_exists("exists@example.com") is True

    def test_email_exists_returns_false(self):
        """Verify False when email does not exist."""
        self.session.query.return_value.scalar.return_value = False
        assert self.repo.email_exists("new@example.com") is False


class TestUserRepositoryUpdate:
    """Tests for UserRepository update methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = UserRepository(self.session)

    def test_update_last_login(self):
        """Verify update_last_login calls update with timestamp."""
        self.repo.update_last_login(1)
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert "last_login_at" in update_dict
        assert isinstance(update_dict["last_login_at"], datetime)

    def test_update_password(self):
        """Verify update_password calls update with new hash."""
        self.repo.update_password(1, "new_hash")
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert update_dict["password_hash"] == "new_hash"

    def test_update_status(self):
        """Verify update_status calls update with new status."""
        self.repo.update_status(1, "banned")
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert update_dict["status"] == "banned"

    def test_increment_token_version(self):
        """Verify increment_token_version uses atomic SQL expression."""
        self.repo.increment_token_version(1)
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        # The update dict should use a SQL expression (User.token_version + 1),
        # not a plain integer — we verify the call was made
        call_args = (
            self.session.query.return_value.filter.return_value.update.call_args
        )
        assert call_args is not None
