"""
Auth Audit Log Repository

Data access layer for the auth_audit_log table.
Provides INSERT and READ operations only — this table is immutable.
No UPDATE or DELETE operations are permitted (audit log integrity).
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.shared.observability import get_context_logger

from .models import AuthAuditLog

logger = get_context_logger(__name__)


class AuthAuditLogRepository:
    """
    Repository for the immutable auth audit log.

    INSERT-ONLY — no update or delete methods are exposed.

    All methods receive an injected SQLAlchemy Session.
    Transaction commit/rollback is the caller's responsibility.
    """

    def __init__(self, session: Session):
        self.session = session

    # ========================================================================
    # CREATE (INSERT-ONLY)
    # ========================================================================

    def log_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuthAuditLog:
        """
        Insert an authentication event into the audit log.

        Args:
            event_type: Event classifier (e.g. 'login_success', 'login_failure',
                        'logout', 'token_refresh', 'password_change',
                        'admin_role_changed', 'user_status_changed',
                        'suspicious_activity').
            user_id: Optional FK to users.id (NULL for pre-auth events).
            ip_address: Client IP address.
            user_agent: Client user-agent string.
            metadata: Additional context as JSONB.

        Returns:
            Created AuthAuditLog ORM instance.
        """
        entry = AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata,
        )
        self.session.add(entry)
        self.session.flush()

        logger.debug(
            "Audit event logged",
            event_type="persistence.audit_log.created",
            metadata={
                "audit_event_type": event_type,
                "user_id": user_id,
            },
        )
        return entry

    # ========================================================================
    # READ
    # ========================================================================

    def get_recent_events(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[AuthAuditLog]:
        """
        Get the most recent auth events for a user.

        Args:
            user_id: User ID.
            limit: Max number of records to return (default 50).

        Returns:
            List of AuthAuditLog records ordered by created_at DESC.
        """
        return (
            self.session.query(AuthAuditLog)
            .filter(AuthAuditLog.user_id == user_id)
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_failed_login_attempts(
        self,
        email: str,
        since: datetime,
    ) -> int:
        """
        Count failed login attempts for an email since a given timestamp.

        Used for rate-limiting / brute-force detection.
        Searches by email inside the JSONB metadata column because
        failed logins may not have a user_id (user may not exist).

        Args:
            email: Email address to check.
            since: Count events after this timestamp.

        Returns:
            Number of 'login_failure' events.
        """
        return (
            self.session.query(func.count(AuthAuditLog.id))
            .filter(
                AuthAuditLog.event_type == "login_failure",
                AuthAuditLog.created_at >= since,
                AuthAuditLog.event_metadata["email"].astext == email.lower(),
            )
            .scalar()
        ) or 0

    def get_suspicious_events(
        self,
        since: datetime,
        limit: int = 100,
    ) -> List[AuthAuditLog]:
        """
        Get suspicious activity events since a given timestamp.

        Args:
            since: Start timestamp.
            limit: Max records (default 100).

        Returns:
            List of AuthAuditLog records.
        """
        return (
            self.session.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == "suspicious_activity",
                AuthAuditLog.created_at >= since,
            )
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_events_by_type(
        self,
        event_type: str,
        since: datetime,
        limit: int = 100,
    ) -> List[AuthAuditLog]:
        """
        Get audit events of a specific type since a given timestamp.

        Generic query helper used for monitoring dashboards.

        Args:
            event_type: Event type to filter by.
            since: Start timestamp.
            limit: Max records (default 100).

        Returns:
            List of AuthAuditLog records.
        """
        return (
            self.session.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == event_type,
                AuthAuditLog.created_at >= since,
            )
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
