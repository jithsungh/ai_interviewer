"""
Integration Tests – RefreshTokenRepository

Tests token lifecycle (create → find → revoke → cleanup) against PostgreSQL.
Each test is rolled back automatically.
"""

import pytest
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from app.auth.persistence.refresh_token_repository import RefreshTokenRepository
from app.shared.errors.exceptions import ConflictError


pytestmark = pytest.mark.integration


def _random_hash() -> str:
    """Generate a unique token hash."""
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


class TestRefreshTokenCreateIntegration:

    def test_create_token_persists_row(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        token = repo.create(
            user_id=create_test_user["id"],
            token_hash=_random_hash(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert token.id is not None
        assert token.user_id == create_test_user["id"]
        assert token.revoked_at is None

    def test_create_token_with_device_info(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        token = repo.create(
            user_id=create_test_user["id"],
            token_hash=_random_hash(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            device_info="Chrome/Linux",
            ip_address="192.168.1.1",
        )

        assert token.device_info == "Chrome/Linux"
        assert str(token.ip_address) == "192.168.1.1"

    def test_create_duplicate_hash_raises_conflict(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        dup_hash = _random_hash()
        repo.create(
            user_id=create_test_user["id"],
            token_hash=dup_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.flush()

        with pytest.raises(ConflictError):
            repo.create(
                user_id=create_test_user["id"],
                token_hash=dup_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )


class TestRefreshTokenReadIntegration:

    def test_find_by_hash_returns_token(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        h = _random_hash()
        repo.create(
            user_id=create_test_user["id"],
            token_hash=h,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.flush()

        found = repo.find_by_hash(h)
        assert found is not None
        assert found.token_hash == h

    def test_find_by_hash_missing(self, db_session):
        repo = RefreshTokenRepository(db_session)
        assert repo.find_by_hash("nonexistent_hash") is None

    def test_list_active_for_user_excludes_revoked(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        uid = create_test_user["id"]
        future = datetime.now(timezone.utc) + timedelta(days=7)

        # Active token
        repo.create(user_id=uid, token_hash=_random_hash(), expires_at=future)
        # Revoked token
        revoked = repo.create(
            user_id=uid, token_hash=_random_hash(), expires_at=future
        )
        db_session.flush()
        repo.revoke(revoked.id, reason="test")
        db_session.flush()

        active = repo.list_active_for_user(uid)
        assert len(active) == 1
        assert active[0].revoked_at is None


class TestRefreshTokenRevokeIntegration:

    def test_revoke_sets_timestamp_and_reason(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        token = repo.create(
            user_id=create_test_user["id"],
            token_hash=_random_hash(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.flush()

        repo.revoke(token.id, reason="user_logout")
        db_session.flush()
        db_session.expire_all()

        revoked = repo.find_by_hash(token.token_hash)
        assert revoked.revoked_at is not None
        assert revoked.revoked_reason == "user_logout"

    def test_revoke_all_for_user_returns_count(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        uid = create_test_user["id"]
        future = datetime.now(timezone.utc) + timedelta(days=7)

        for _ in range(3):
            repo.create(user_id=uid, token_hash=_random_hash(), expires_at=future)
        db_session.flush()

        count = repo.revoke_all_for_user(uid, reason="password_change")
        assert count == 3

    def test_revoke_all_for_user_zero_when_none(self, db_session, create_test_user):
        repo = RefreshTokenRepository(db_session)
        # User exists but has no tokens
        count = repo.revoke_all_for_user(create_test_user["id"], reason="test")
        assert count == 0


class TestRefreshTokenCleanupIntegration:

    def test_cleanup_expired_removes_old_tokens(self, db_session, create_test_user):
        """Tokens expired > grace_days ago are deleted; recent ones remain."""
        repo = RefreshTokenRepository(db_session)
        uid = create_test_user["id"]

        # Token expired 40 days ago (should be cleaned with default 30-day grace)
        old_expires = datetime.now(timezone.utc) - timedelta(days=40)
        repo.create(
            user_id=uid,
            token_hash=_random_hash(),
            expires_at=old_expires,
        )
        # Token expired 10 days ago (within grace period)
        recent_expires = datetime.now(timezone.utc) - timedelta(days=10)
        repo.create(
            user_id=uid,
            token_hash=_random_hash(),
            expires_at=recent_expires,
        )
        db_session.flush()

        deleted = repo.cleanup_expired(grace_days=30)
        assert deleted == 1
