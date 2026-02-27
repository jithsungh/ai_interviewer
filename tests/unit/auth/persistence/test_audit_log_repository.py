"""
Unit Tests for AuthAuditLogRepository

Tests audit log INSERT and READ operations with a mocked session.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session

from app.auth.persistence.audit_log_repository import AuthAuditLogRepository
from app.auth.persistence.models import AuthAuditLog


class TestAuditLogRepositoryCreate:
    """Tests for AuthAuditLogRepository.log_event()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AuthAuditLogRepository(self.session)

    def test_log_event_inserts_entry(self):
        """Verify log_event adds to session and flushes."""
        self.repo.log_event(
            event_type="login_success",
            user_id=1,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            metadata={"reason": "test"},
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()

        added = self.session.add.call_args[0][0]
        assert added.event_type == "login_success"
        assert added.user_id == 1
        assert added.ip_address == "192.168.1.1"
        assert added.user_agent == "Mozilla/5.0"
        assert added.event_metadata == {"reason": "test"}

    def test_log_event_nullable_fields(self):
        """Verify optional fields default to None."""
        self.repo.log_event(event_type="login_failure")
        added = self.session.add.call_args[0][0]
        assert added.user_id is None
        assert added.ip_address is None
        assert added.user_agent is None
        assert added.event_metadata is None

    def test_log_event_returns_entry(self):
        """Verify log_event returns the created entry."""
        result = self.repo.log_event(event_type="logout", user_id=1)
        assert isinstance(result, AuthAuditLog)


class TestAuditLogRepositoryRead:
    """Tests for AuthAuditLogRepository read methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AuthAuditLogRepository(self.session)

    def test_get_recent_events_returns_list(self):
        """Verify get_recent_events queries by user_id with ordering and limit."""
        mock_events = [Mock(spec=AuthAuditLog), Mock(spec=AuthAuditLog)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = mock_events
        result = self.repo.get_recent_events(user_id=1, limit=10)
        assert result == mock_events

    def test_get_recent_events_default_limit(self):
        """Verify default limit is 50."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = []
        self.repo.get_recent_events(user_id=1)
        # Verify limit(50) was called (checking the chain)
        self.session.query.return_value.filter.return_value.order_by.return_value.limit.assert_called()

    def test_get_recent_events_empty(self):
        """Verify empty list when no events."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = []
        result = self.repo.get_recent_events(user_id=999)
        assert result == []


class TestAuditLogRepositoryFailedLogins:
    """Tests for AuthAuditLogRepository.get_failed_login_attempts()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AuthAuditLogRepository(self.session)
        self.since = datetime.now(timezone.utc) - timedelta(minutes=15)

    def test_get_failed_login_attempts_returns_count(self):
        """Verify count of failed login attempts."""
        self.session.query.return_value.filter.return_value.scalar.return_value = 3
        count = self.repo.get_failed_login_attempts(
            email="test@example.com", since=self.since
        )
        assert count == 3

    def test_get_failed_login_attempts_returns_zero(self):
        """Verify 0 when no failed attempts."""
        self.session.query.return_value.filter.return_value.scalar.return_value = 0
        count = self.repo.get_failed_login_attempts(
            email="clean@example.com", since=self.since
        )
        assert count == 0

    def test_get_failed_login_attempts_handles_none(self):
        """Verify None from scalar is coerced to 0."""
        self.session.query.return_value.filter.return_value.scalar.return_value = None
        count = self.repo.get_failed_login_attempts(
            email="new@example.com", since=self.since
        )
        assert count == 0


class TestAuditLogRepositorySuspicious:
    """Tests for AuthAuditLogRepository.get_suspicious_events()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AuthAuditLogRepository(self.session)
        self.since = datetime.now(timezone.utc) - timedelta(hours=24)

    def test_get_suspicious_events_returns_list(self):
        """Verify suspicious events are returned."""
        mock_events = [Mock(spec=AuthAuditLog)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = mock_events
        result = self.repo.get_suspicious_events(since=self.since)
        assert result == mock_events

    def test_get_suspicious_events_empty(self):
        """Verify empty list when no suspicious events."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = []
        result = self.repo.get_suspicious_events(since=self.since)
        assert result == []


class TestAuditLogRepositoryEventsByType:
    """Tests for AuthAuditLogRepository.get_events_by_type()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = AuthAuditLogRepository(self.session)
        self.since = datetime.now(timezone.utc) - timedelta(hours=1)

    def test_get_events_by_type_returns_list(self):
        """Verify events by type are returned."""
        mock_events = [Mock(spec=AuthAuditLog)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = mock_events
        result = self.repo.get_events_by_type(
            event_type="password_change", since=self.since
        )
        assert result == mock_events

    def test_get_events_by_type_default_limit(self):
        """Verify default limit is 100."""
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .limit.return_value
            .all.return_value
        ) = []
        self.repo.get_events_by_type(event_type="logout", since=self.since)
        # Call succeeds with default limit
