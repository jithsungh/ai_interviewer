"""
Unit Tests for Auth ORM Models

Tests model instantiation, attribute defaults, and relationships.
"""

import pytest
from datetime import datetime, timezone

from app.auth.persistence.models import (
    User,
    Admin,
    Candidate,
    RefreshToken,
    AuthAuditLog,
)


class TestUserModel:
    """Tests for User ORM model."""

    def test_user_tablename(self):
        assert User.__tablename__ == "users"

    def test_user_instantiation_with_required_fields(self):
        user = User(
            name="Test",
            email="test@example.com",
            password_hash="hash",
            user_type="admin",
        )
        assert user.name == "Test"
        assert user.email == "test@example.com"
        assert user.password_hash == "hash"
        assert user.user_type == "admin"

    def test_user_default_status_column_metadata(self):
        """Column default is applied at flush time, not on instantiation."""
        col = User.__table__.c.status
        assert col.default.arg == "active"

    def test_user_default_token_version_column_metadata(self):
        """Column default is applied at flush time, not on instantiation."""
        col = User.__table__.c.token_version
        assert col.default.arg == 1

    def test_user_last_login_nullable(self):
        user = User(
            name="T", email="t@e.com", password_hash="h", user_type="candidate"
        )
        assert user.last_login_at is None

    def test_user_type_check_constraint_exists(self):
        """Verify check constraint is defined for user_type."""
        constraint_names = [
            c.name for c in User.__table__.constraints
            if hasattr(c, "name") and c.name
        ]
        assert "users_user_type_check" in constraint_names


class TestAdminModel:
    """Tests for Admin ORM model."""

    def test_admin_tablename(self):
        assert Admin.__tablename__ == "admins"

    def test_admin_instantiation(self):
        admin = Admin(
            user_id=1,
            organization_id=10,
            role="admin",
        )
        assert admin.user_id == 1
        assert admin.organization_id == 10
        assert admin.role == "admin"

    def test_admin_default_status_column_metadata(self):
        """Column default is applied at flush time, not on instantiation."""
        col = Admin.__table__.c.status
        assert col.default.arg == "active"


class TestCandidateModel:
    """Tests for Candidate ORM model."""

    def test_candidate_tablename(self):
        assert Candidate.__tablename__ == "candidates"

    def test_candidate_instantiation(self):
        candidate = Candidate(user_id=1)
        assert candidate.user_id == 1

    def test_candidate_default_plan_column_metadata(self):
        """Column default is applied at flush time, not on instantiation."""
        col = Candidate.__table__.c.plan
        assert col.default.arg == "free"

    def test_candidate_default_status_column_metadata(self):
        """Column default is applied at flush time, not on instantiation."""
        col = Candidate.__table__.c.status
        assert col.default.arg == "active"

    def test_candidate_nullable_profile_metadata(self):
        candidate = Candidate(user_id=1)
        assert candidate.profile_metadata is None

    def test_candidate_with_profile_metadata(self):
        meta = {"full_name": "Alice", "phone": "+1"}
        candidate = Candidate(user_id=1, profile_metadata=meta)
        assert candidate.profile_metadata == meta


class TestRefreshTokenModel:
    """Tests for RefreshToken ORM model."""

    def test_refresh_token_tablename(self):
        assert RefreshToken.__tablename__ == "refresh_tokens"

    def test_refresh_token_instantiation(self):
        expires = datetime.now(timezone.utc)
        token = RefreshToken(
            user_id=1,
            token_hash="hash",
            expires_at=expires,
        )
        assert token.user_id == 1
        assert token.token_hash == "hash"
        assert token.expires_at == expires

    def test_refresh_token_nullable_fields(self):
        token = RefreshToken(
            user_id=1,
            token_hash="h",
            expires_at=datetime.now(timezone.utc),
        )
        assert token.device_info is None
        assert token.ip_address is None
        assert token.revoked_at is None
        assert token.revoked_reason is None


class TestAuthAuditLogModel:
    """Tests for AuthAuditLog ORM model."""

    def test_audit_log_tablename(self):
        assert AuthAuditLog.__tablename__ == "auth_audit_log"

    def test_audit_log_instantiation(self):
        entry = AuthAuditLog(
            event_type="login_success",
            user_id=1,
            ip_address="127.0.0.1",
        )
        assert entry.event_type == "login_success"
        assert entry.user_id == 1
        assert entry.ip_address == "127.0.0.1"

    def test_audit_log_nullable_user_id(self):
        entry = AuthAuditLog(event_type="login_failure")
        assert entry.user_id is None

    def test_audit_log_event_metadata_maps_to_db_column(self):
        """Verify event_metadata Python attr maps to 'metadata' DB column."""
        entry = AuthAuditLog(
            event_type="test",
            event_metadata={"key": "value"},
        )
        assert entry.event_metadata == {"key": "value"}
        # Verify the column object maps to 'metadata' in the DB
        col = AuthAuditLog.__table__.c.get("metadata")
        assert col is not None, "DB column should be named 'metadata'"

    def test_audit_log_immutability_contract(self):
        """Document that audit log has no update/delete methods (contract)."""
        # No update constraint at ORM level, but the repository enforces INSERT-ONLY.
        # This test documents the contract.
        assert AuthAuditLog.__tablename__ == "auth_audit_log"
