"""
Fallback Question Repository

Read-heavy repository for generic_fallback_questions table.
Writes are limited to incrementing usage_count (last-resort only).

Follows existing repo patterns:
- Constructor takes SQLAlchemy Session
- No business logic
- Strict typing
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from app.question.generation.persistence.models import GenericFallbackQuestion

logger = logging.getLogger(__name__)


class FallbackQuestionRepository:
    """
    Repository for generic fallback questions.

    Instantiated with a per-request DB session (FastAPI DI).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_difficulty_and_topic(
        self,
        difficulty: str,
        topic: str,
    ) -> Optional[GenericFallbackQuestion]:
        """
        Find the least-used active fallback matching difficulty + topic.

        Returns None if no match found.
        """
        return (
            self._session.query(GenericFallbackQuestion)
            .filter(
                GenericFallbackQuestion.difficulty == difficulty,
                GenericFallbackQuestion.topic == topic,
                GenericFallbackQuestion.is_active.is_(True),
            )
            .order_by(asc(GenericFallbackQuestion.usage_count))
            .first()
        )

    def get_by_difficulty(
        self,
        difficulty: str,
    ) -> Optional[GenericFallbackQuestion]:
        """
        Find the least-used active fallback matching difficulty only.

        Broader search used when topic-specific match unavailable.
        """
        return (
            self._session.query(GenericFallbackQuestion)
            .filter(
                GenericFallbackQuestion.difficulty == difficulty,
                GenericFallbackQuestion.is_active.is_(True),
            )
            .order_by(asc(GenericFallbackQuestion.usage_count))
            .first()
        )

    def get_any_active(self) -> Optional[GenericFallbackQuestion]:
        """
        Last-resort: return any active fallback question.
        """
        return (
            self._session.query(GenericFallbackQuestion)
            .filter(GenericFallbackQuestion.is_active.is_(True))
            .order_by(asc(GenericFallbackQuestion.usage_count))
            .first()
        )

    def increment_usage(self, fallback_id: int) -> None:
        """
        Atomically increment usage_count for the given fallback.

        Uses SQL increment to avoid race conditions.
        """
        self._session.query(GenericFallbackQuestion).filter(
            GenericFallbackQuestion.id == fallback_id,
        ).update(
            {GenericFallbackQuestion.usage_count: GenericFallbackQuestion.usage_count + 1},
            synchronize_session=False,
        )
        # Caller (service) manages commit via session context manager.

    def count_active(self) -> int:
        """Return count of active fallback questions."""
        return (
            self._session.query(func.count(GenericFallbackQuestion.id))
            .filter(GenericFallbackQuestion.is_active.is_(True))
            .scalar()
            or 0
        )
