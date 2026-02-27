"""
Unit Tests for AdminRepository

Tests admin CRUD operations with a mocked SQLAlchemy session.
"""

import pytest
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.persistence.admin_repository import AdminRepository
from app.auth.persistence.models import Admin
from app.shared.errors import ConflictError, DatabaseError


class TestAdminRepositoryCreate:
    """Tests for AdminRepository.create()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AdminRepository(self.session)

    def test_create_admin_adds_to_session_and_flushes(self):
        """Verify admin is added to session and flushed."""
        self.repo.create(
            user_id=1,
            organization_id=10,
            role="admin",
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert added.user_id == 1
        assert added.organization_id == 10
        assert added.role == "admin"
        assert added.status == "active"

    def test_create_admin_default_status_active(self):
        """Verify default status is 'active'."""
        self.repo.create(user_id=1, organization_id=10, role="read_only")
        added = self.session.add.call_args[0][0]
        assert added.status == "active"

    def test_create_admin_duplicate_raises_conflict(self):
        """Verify ConflictError on duplicate user_id+organization_id UNIQUE violation."""
        orig = Exception("admins_user_id_organization_id_key")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(ConflictError) as exc_info:
            self.repo.create(user_id=1, organization_id=10, role="admin")
        assert "already exists" in str(exc_info.value.message)

    def test_create_admin_other_integrity_error_raises_database_error(self):
        """Verify DatabaseError on non-UNIQUE IntegrityError."""
        orig = Exception("some_other_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DatabaseError):
            self.repo.create(user_id=1, organization_id=10, role="admin")


class TestAdminRepositoryRead:
    """Tests for AdminRepository read methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AdminRepository(self.session)

    def test_get_by_id_returns_admin(self):
        """Verify get_by_id returns matching admin."""
        mock_admin = Mock(spec=Admin)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_admin
        )
        result = self.repo.get_by_id(1)
        assert result is mock_admin

    def test_get_by_id_returns_none(self):
        """Verify None when admin not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.get_by_id(999) is None

    def test_find_by_user_id_returns_admin(self):
        """Verify find_by_user_id queries Admin.user_id."""
        mock_admin = Mock(spec=Admin)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_admin
        )
        result = self.repo.find_by_user_id(1)
        assert result is mock_admin

    def test_find_by_user_id_returns_none(self):
        """Verify None when user has no admin record."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.find_by_user_id(999) is None

    def test_list_by_organization(self):
        """Verify list_by_organization returns list and orders by created_at."""
        mock_admins = [Mock(spec=Admin), Mock(spec=Admin)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = mock_admins
        result = self.repo.list_by_organization(10)
        assert result == mock_admins

    def test_list_by_organization_empty(self):
        """Verify empty list when no admins for org."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = []
        result = self.repo.list_by_organization(999)
        assert result == []


class TestAdminRepositoryUpdate:
    """Tests for AdminRepository update methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AdminRepository(self.session)

    def test_update_role(self):
        """Verify update_role calls session update."""
        self.repo.update_role(1, "superadmin")
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert update_dict["role"] == "superadmin"

    def test_update_status(self):
        """Verify update_status calls session update."""
        self.repo.update_status(1, "inactive")
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert update_dict["status"] == "inactive"
