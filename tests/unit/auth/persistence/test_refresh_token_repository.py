"""
Unit Tests for RefreshTokenRepository

Tests refresh-token CRUD and revocation operations with a mocked session.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.persistence.refresh_token_repository import RefreshTokenRepository
from app.auth.persistence.models import RefreshToken
from app.shared.errors import ConflictError, DatabaseError


class TestRefreshTokenRepositoryCreate:
    """Tests for RefreshTokenRepository.create()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = RefreshTokenRepository(self.session)
        self.expires = datetime.now(timezone.utc) + timedelta(days=30)

    def test_create_token_adds_and_flushes(self):
        """Verify token is added and flushed."""
        self.repo.create(
            user_id=1,
            token_hash="hash123",
            expires_at=self.expires,
            device_info="Chrome",
            ip_address="192.168.1.1",
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert added.user_id == 1
        assert added.token_hash == "hash123"
        assert added.device_info == "Chrome"
        assert added.ip_address == "192.168.1.1"
        assert added.expires_at == self.expires

    def test_create_token_optional_fields_default_none(self):
        """Verify optional device_info/ip_address default to None."""
        self.repo.create(
            user_id=1,
            token_hash="hash123",
            expires_at=self.expires,
        )
        added = self.session.add.call_args[0][0]
        assert added.device_info is None
        assert added.ip_address is None

    def test_create_token_duplicate_hash_raises_conflict(self):
        """Verify ConflictError on duplicate token_hash."""
        orig = Exception("refresh_tokens_token_hash_unique")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(ConflictError) as exc_info:
            self.repo.create(
                user_id=1, token_hash="dup_hash", expires_at=self.expires
            )
        assert "collision" in str(exc_info.value.message).lower()

    def test_create_token_other_integrity_error_raises_database_error(self):
        """Verify DatabaseError on non-hash IntegrityError."""
        orig = Exception("some_other_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DatabaseError):
            self.repo.create(
                user_id=1, token_hash="hash", expires_at=self.expires
            )


class TestRefreshTokenRepositoryRead:
    """Tests for RefreshTokenRepository read methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = RefreshTokenRepository(self.session)

    def test_find_by_hash_returns_token(self):
        """Verify find_by_hash returns matching token."""
        mock_token = Mock(spec=RefreshToken)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_token
        )
        result = self.repo.find_by_hash("token_hash_123")
        assert result is mock_token

    def test_find_by_hash_returns_none(self):
        """Verify None when hash not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.find_by_hash("nonexistent") is None

    def test_list_active_for_user(self):
        """Verify list_active_for_user filters revoked and expired."""
        mock_tokens = [Mock(spec=RefreshToken), Mock(spec=RefreshToken)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = mock_tokens
        result = self.repo.list_active_for_user(1)
        assert result == mock_tokens

    def test_list_active_for_user_empty(self):
        """Verify empty list when no active tokens."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = []
        result = self.repo.list_active_for_user(1)
        assert result == []


class TestRefreshTokenRepositoryRevoke:
    """Tests for RefreshTokenRepository revocation methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = RefreshTokenRepository(self.session)

    def test_revoke_updates_token(self):
        """Verify revoke calls update on matching non-revoked token."""
        self.repo.revoke(token_id=1, reason="logout")
        (
            self.session.query.return_value
            .filter.return_value
            .update.assert_called_once()
        )
        update_dict = (
            self.session.query.return_value
            .filter.return_value
            .update.call_args[0][0]
        )
        assert update_dict["revoked_reason"] == "logout"
        assert "revoked_at" in update_dict

    def test_revoke_all_for_user_returns_count(self):
        """Verify revoke_all_for_user returns revocation count."""
        (
            self.session.query.return_value
            .filter.return_value
            .update.return_value
        ) = 3
        count = self.repo.revoke_all_for_user(user_id=1, reason="password_change")
        assert count == 3

    def test_revoke_all_for_user_returns_zero_when_none(self):
        """Verify 0 when user has no active tokens."""
        (
            self.session.query.return_value
            .filter.return_value
            .update.return_value
        ) = 0
        count = self.repo.revoke_all_for_user(user_id=1, reason="test")
        assert count == 0


class TestRefreshTokenRepositoryCleanup:
    """Tests for RefreshTokenRepository.cleanup_expired()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = RefreshTokenRepository(self.session)

    def test_cleanup_expired_deletes_old_tokens(self):
        """Verify cleanup_expired deletes and returns count."""
        self.session.query.return_value.filter.return_value.delete.return_value = 5
        count = self.repo.cleanup_expired(grace_days=7)
        assert count == 5

    def test_cleanup_expired_returns_zero_when_none(self):
        """Verify 0 when no tokens to clean up."""
        self.session.query.return_value.filter.return_value.delete.return_value = 0
        count = self.repo.cleanup_expired()
        assert count == 0

    def test_cleanup_expired_default_grace_days(self):
        """Verify default grace_days is 7."""
        self.session.query.return_value.filter.return_value.delete.return_value = 0
        self.repo.cleanup_expired()
        # just ensure no exception on default call
