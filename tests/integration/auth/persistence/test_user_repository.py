"""
Integration Tests – UserRepository

Tests CRUD operations against a real PostgreSQL database.
Each test runs inside a transaction that is rolled back afterward.
"""

import pytest
from sqlalchemy import text

from app.auth.persistence.user_repository import UserRepository
from app.auth.persistence.models import User
from app.shared.errors.exceptions import ConflictError, DatabaseError


pytestmark = pytest.mark.integration


class TestUserRepositoryCreateIntegration:
    """Test UserRepository.create against a live database."""

    def test_create_user_persists_row(self, db_session, unique_email):
        repo = UserRepository(db_session)
        user = repo.create(
            name="Alice",
            email=unique_email,
            password_hash="$2b$12$abcdefhashed",
            user_type="candidate",
        )

        assert user.id is not None
        assert user.email == unique_email
        assert user.status == "active"
        assert user.token_version == 1

    def test_create_user_duplicate_email_raises_conflict(
        self, db_session, create_test_user
    ):
        repo = UserRepository(db_session)
        with pytest.raises(ConflictError):
            repo.create(
                name="Dup",
                email=create_test_user["email"],
                password_hash="hash",
                user_type="admin",
            )

    def test_create_user_enforces_user_type_constraint(self, db_session, unique_email):
        """DB check constraint rejects invalid user_type values."""
        repo = UserRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(
                name="Bad",
                email=unique_email,
                password_hash="hash",
                user_type="superadmin",  # Not in CHECK constraint
            )


class TestUserRepositoryReadIntegration:
    """Test UserRepository read methods against a live database."""

    def test_get_by_id_returns_user(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        user = repo.get_by_id(create_test_user["id"])

        assert user is not None
        assert user.email == create_test_user["email"]

    def test_get_by_id_nonexistent_returns_none(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_by_id(999_999_999) is None

    def test_find_by_email_case_insensitive(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        user = repo.find_by_email(create_test_user["email"].upper())
        assert user is not None
        assert user.id == create_test_user["id"]

    def test_email_exists_true(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        assert repo.email_exists(create_test_user["email"]) is True

    def test_email_exists_false(self, db_session):
        repo = UserRepository(db_session)
        assert repo.email_exists("no-such@email.test") is False


class TestUserRepositoryUpdateIntegration:
    """Test UserRepository update methods against a live database."""

    def test_update_last_login_sets_timestamp(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        repo.update_last_login(create_test_user["id"])
        db_session.flush()

        user = repo.get_by_id(create_test_user["id"])
        assert user is not None
        assert user.last_login_at is not None

    def test_update_password_changes_hash(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        repo.update_password(create_test_user["id"], "new-hash-value")
        db_session.flush()

        user = repo.get_by_id(create_test_user["id"])
        assert user is not None
        assert user.password_hash == "new-hash-value"

    def test_update_status_changes_status(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        repo.update_status(create_test_user["id"], "banned")
        db_session.flush()

        user = repo.get_by_id(create_test_user["id"])
        assert user is not None
        assert user.status == "banned"

    def test_increment_token_version_atomically(self, db_session, create_test_user):
        repo = UserRepository(db_session)
        user_before = repo.get_by_id(create_test_user["id"])
        original_version = user_before.token_version

        repo.increment_token_version(create_test_user["id"])
        db_session.flush()
        db_session.expire_all()

        user_after = repo.get_by_id(create_test_user["id"])
        assert user_after.token_version == original_version + 1


class TestUserRepositoryConstraints:
    """Test that DB constraints are enforced."""

    def test_nullable_name_rejected(self, db_session, unique_email):
        """name is NOT NULL."""
        repo = UserRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(
                name=None,
                email=unique_email,
                password_hash="hash",
                user_type="admin",
            )

    def test_nullable_email_rejected(self, db_session):
        """email is NOT NULL."""
        repo = UserRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(
                name="Nobody",
                email=None,
                password_hash="hash",
                user_type="candidate",
            )
