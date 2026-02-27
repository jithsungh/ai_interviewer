"""
Integration Tests – AdminRepository

Tests CRUD against a real PostgreSQL database.
Each test is rolled back automatically.
"""

import pytest
from sqlalchemy import text

from app.auth.persistence.admin_repository import AdminRepository
from app.shared.errors.exceptions import ConflictError, DatabaseError


pytestmark = pytest.mark.integration


class TestAdminRepositoryCreateIntegration:
    """Test AdminRepository.create against a live database."""

    def test_create_admin_persists_row(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        admin = repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="admin",
        )

        assert admin.id is not None
        assert admin.user_id == create_test_user["id"]
        assert admin.organization_id == create_test_organization["id"]
        assert admin.role == "admin"
        assert admin.status == "active"

    def test_create_admin_duplicate_raises_conflict(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="admin",
        )
        db_session.flush()

        with pytest.raises(ConflictError):
            repo.create(
                user_id=create_test_user["id"],
                organization_id=create_test_organization["id"],
                role="read_only",
            )


class TestAdminRepositoryReadIntegration:
    """Test AdminRepository read methods against a live database."""

    def test_get_by_id_returns_admin(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        admin = repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="admin",
        )
        db_session.flush()

        found = repo.get_by_id(admin.id)
        assert found is not None
        assert found.id == admin.id

    def test_find_by_user_id_returns_admin(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="read_only",
        )
        db_session.flush()

        found = repo.find_by_user_id(create_test_user["id"])
        assert found is not None
        assert found.user_id == create_test_user["id"]

    def test_list_by_organization_returns_members(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="admin",
        )
        db_session.flush()

        admins = repo.list_by_organization(create_test_organization["id"])
        assert len(admins) >= 1
        assert any(a.user_id == create_test_user["id"] for a in admins)


class TestAdminRepositoryUpdateIntegration:
    """Test AdminRepository update methods against a live database."""

    def test_update_role_changes_role(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        admin = repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="read_only",
        )
        db_session.flush()

        repo.update_role(admin.id, "admin")
        db_session.flush()
        db_session.expire_all()

        updated = repo.get_by_id(admin.id)
        assert updated.role == "admin"

    def test_update_status_changes_status(
        self, db_session, create_test_user, create_test_organization
    ):
        repo = AdminRepository(db_session)
        admin = repo.create(
            user_id=create_test_user["id"],
            organization_id=create_test_organization["id"],
            role="admin",
        )
        db_session.flush()

        repo.update_status(admin.id, "suspended")
        db_session.flush()
        db_session.expire_all()

        updated = repo.get_by_id(admin.id)
        assert updated.status == "suspended"


class TestAdminRepositoryConstraints:
    """Test DB constraint enforcement."""

    def test_foreign_key_user_id_enforced(
        self, db_session, create_test_organization
    ):
        """References non-existent user_id → DatabaseError."""
        repo = AdminRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(
                user_id=999_999_999,
                organization_id=create_test_organization["id"],
                role="admin",
            )

    def test_foreign_key_organization_id_enforced(
        self, db_session, create_test_user
    ):
        """References non-existent organization_id → DatabaseError."""
        repo = AdminRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(
                user_id=create_test_user["id"],
                organization_id=999_999_999,
                role="admin",
            )
