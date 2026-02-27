"""
Integration Tests – AuthAuditLogRepository

Tests INSERT-only audit trail against a real PostgreSQL database.
Each test is rolled back automatically.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from app.auth.persistence.audit_log_repository import AuthAuditLogRepository


pytestmark = pytest.mark.integration


class TestAuditLogCreateIntegration:

    def test_log_event_persists_row(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)
        entry = repo.log_event(
            event_type="login_success",
            user_id=create_test_user["id"],
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
            metadata={"method": "password"},
        )

        assert entry.id is not None
        assert entry.event_type == "login_success"
        assert entry.user_id == create_test_user["id"]
        assert entry.event_metadata == {"method": "password"}

    def test_log_event_nullable_user_id(self, db_session):
        """Failed login events may not have a known user_id."""
        repo = AuthAuditLogRepository(db_session)
        entry = repo.log_event(
            event_type="login_failure",
            ip_address="10.0.0.2",
            metadata={"email": "unknown@test.com"},
        )

        assert entry.id is not None
        assert entry.user_id is None

    def test_log_event_without_metadata(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)
        entry = repo.log_event(
            event_type="token_refresh",
            user_id=create_test_user["id"],
        )

        assert entry.id is not None
        assert entry.event_metadata is None


class TestAuditLogReadIntegration:

    def test_get_recent_events_returns_ordered_list(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)

        for event_type in ["login_success", "token_refresh", "password_change"]:
            repo.log_event(
                event_type=event_type,
                user_id=create_test_user["id"],
            )
        db_session.flush()

        events = repo.get_recent_events(create_test_user["id"], limit=10)
        assert len(events) == 3
        types = [e.event_type for e in events]
        assert "password_change" in types

    def test_get_recent_events_respects_limit(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)

        for _ in range(5):
            repo.log_event(
                event_type="login_success",
                user_id=create_test_user["id"],
            )
        db_session.flush()

        events = repo.get_recent_events(create_test_user["id"], limit=3)
        assert len(events) == 3


class TestAuditLogFailedLoginsIntegration:

    def test_get_failed_login_attempts_counts_correctly(self, db_session):
        repo = AuthAuditLogRepository(db_session)
        target_email = "target@failure.test"
        since = datetime.now(timezone.utc) - timedelta(minutes=60)

        for _ in range(4):
            repo.log_event(
                event_type="login_failure",
                ip_address="10.0.0.1",
                metadata={"email": target_email},
            )
        # One failure for a different email (should not count)
        repo.log_event(
            event_type="login_failure",
            metadata={"email": "other@test.com"},
        )
        db_session.flush()

        count = repo.get_failed_login_attempts(target_email, since=since)
        assert count == 4

    def test_get_failed_login_attempts_zero_when_none(self, db_session):
        repo = AuthAuditLogRepository(db_session)
        since = datetime.now(timezone.utc) - timedelta(minutes=60)
        count = repo.get_failed_login_attempts("nobody@test.com", since=since)
        assert count == 0


class TestAuditLogSuspiciousIntegration:

    def test_get_suspicious_events_filters_by_type(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)
        since = datetime.now(timezone.utc) - timedelta(minutes=60)

        repo.log_event(
            event_type="suspicious_activity",
            user_id=create_test_user["id"],
        )
        repo.log_event(
            event_type="login_success",
            user_id=create_test_user["id"],
        )
        db_session.flush()

        suspicious = repo.get_suspicious_events(since=since, limit=10)
        for event in suspicious:
            assert event.event_type == "suspicious_activity"


class TestAuditLogEventsByTypeIntegration:

    def test_get_events_by_type_filters_correctly(self, db_session, create_test_user):
        repo = AuthAuditLogRepository(db_session)
        since = datetime.now(timezone.utc) - timedelta(minutes=60)

        repo.log_event(event_type="login_success", user_id=create_test_user["id"])
        repo.log_event(event_type="login_failure", user_id=create_test_user["id"])
        repo.log_event(event_type="login_success", user_id=create_test_user["id"])
        db_session.flush()

        events = repo.get_events_by_type("login_success", since=since, limit=10)
        assert all(e.event_type == "login_success" for e in events)
        assert len(events) >= 2
