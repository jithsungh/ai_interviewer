"""
Submission expiry processor.

Expires overdue in-progress submissions in bulk while honoring DB-level
transition constraints and audit logging triggers.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SubmissionExpiryService:
    """Bulk expiry operations for interview submissions."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def expire_overdue_submissions(
        self,
        *,
        limit: int = 500,
        actor: str = "system:expiry_worker",
    ) -> int:
        """
        Transition overdue in-progress submissions to expired.

        Returns number of rows transitioned in the current transaction.
        Idempotent across repeated runs.
        """
        if limit <= 0:
            return 0

        self._db.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor},
        )

        result = self._db.execute(
            text(
                "WITH overdue AS ("
                "    SELECT id "
                "    FROM interview_submissions "
                "    WHERE status = 'in_progress' "
                "      AND scheduled_end IS NOT NULL "
                "      AND scheduled_end < now() "
                "    ORDER BY scheduled_end ASC "
                "    LIMIT :limit "
                ") "
                "UPDATE interview_submissions s "
                "SET status = 'expired', "
                "    submitted_at = COALESCE(submitted_at, now()), "
                "    updated_at = now(), "
                "    version = version + 1 "
                "FROM overdue "
                "WHERE s.id = overdue.id "
                "RETURNING s.id"
            ),
            {"limit": limit},
        )

        transitioned = len(result.fetchall())
        if transitioned > 0:
            logger.info(
                "Expired overdue submissions",
                extra={"count": transitioned, "limit": limit},
            )
        return transitioned
