"""
Audio Analytics Repository — SQLAlchemy concrete implementation

Manages the ``audio_analytics`` table with full CRUD operations,
finalization (immutability), and concurrent-write safety.

Session lifecycle (commit/rollback) is managed by the caller.
Repository calls ``session.flush()`` after mutations (not ``commit``).

Follows the pattern established by
``app/coding/persistence/repositories.py``.

References:
- audio/persistence/REQUIREMENTS.md §5 (Functional Requirements)
- audio/persistence/REQUIREMENTS.md §7 (Repository Pattern)
- audio/persistence/REQUIREMENTS.md §8 (Concurrency & Race Conditions)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)
from app.audio.persistence.exceptions import (
    DuplicateAnalyticsError,
    ImmutabilityError,
)
from app.audio.persistence.mappers import create_dto_to_model, model_to_entity
from app.audio.persistence.models import AudioAnalyticsModel
from app.shared.errors import NotFoundError

logger = logging.getLogger(__name__)


class SqlAudioAnalyticsRepository:
    """
    Concrete SQLAlchemy implementation of ``AudioAnalyticsRepository``.

    Manages the ``audio_analytics`` table with finalization semantics.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
        """
        Insert a new audio analytics record.

        Raises ``DuplicateAnalyticsError`` if a record already
        exists for the exchange (UNIQUE constraint on
        ``interview_exchange_id``).
        """
        model = create_dto_to_model(data)

        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise DuplicateAnalyticsError(
                    exchange_id=data.interview_exchange_id,
                ) from exc
            raise

        logger.info(
            "Audio analytics created",
            extra={
                "analytics_id": model.id,
                "exchange_id": data.interview_exchange_id,
            },
        )
        return model_to_entity(model)

    def create_or_get(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
        """
        Create analytics or return existing (idempotent).

        Handles the race condition where two threads try to create
        analytics for the same exchange simultaneously.
        """
        try:
            return self.create(data)
        except DuplicateAnalyticsError:
            existing = self.get_by_exchange_id(data.interview_exchange_id)
            if existing is not None:
                return existing
            raise  # Should not happen, but re-raise if it does

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, analytics_id: int) -> Optional[AudioAnalytics]:
        """Get analytics by primary key. Returns ``None`` if not found."""
        model = self._session.get(AudioAnalyticsModel, analytics_id)
        return model_to_entity(model) if model else None

    def get_by_exchange_id(self, exchange_id: int) -> Optional[AudioAnalytics]:
        """
        Get the (at most one) analytics record for an exchange.

        Leverages the UNIQUE constraint on ``interview_exchange_id``.
        """
        model = (
            self._session.query(AudioAnalyticsModel)
            .filter(
                AudioAnalyticsModel.interview_exchange_id == exchange_id
            )
            .first()
        )
        return model_to_entity(model) if model else None

    def get_by_submission_id(
        self, submission_id: int
    ) -> List[AudioAnalytics]:
        """
        Get all analytics for an interview submission (across exchanges).

        Joins ``audio_analytics`` with ``interview_exchanges`` to
        filter by ``interview_submission_id``.
        """
        rows = (
            self._session.execute(
                text("""
                    SELECT aa.id
                    FROM audio_analytics aa
                    JOIN interview_exchanges ie
                        ON aa.interview_exchange_id = ie.id
                    WHERE ie.interview_submission_id = :submission_id
                    ORDER BY ie.sequence_order ASC
                """),
                {"submission_id": submission_id},
            )
            .fetchall()
        )

        analytics_ids = [row[0] for row in rows]
        if not analytics_ids:
            return []

        models = (
            self._session.query(AudioAnalyticsModel)
            .filter(AudioAnalyticsModel.id.in_(analytics_ids))
            .order_by(AudioAnalyticsModel.id.asc())
            .all()
        )
        return [model_to_entity(m) for m in models]

    def is_finalized(self, exchange_id: int) -> bool:
        """Check if analytics for exchange is finalized."""
        analytics = self.get_by_exchange_id(exchange_id)
        return analytics.transcript_finalized if analytics else False

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        analytics_id: int,
        data: AudioAnalyticsUpdate,
    ) -> AudioAnalytics:
        """
        Update analytics (only if not finalized).

        Uses ``SELECT FOR UPDATE`` to prevent concurrent modification
        during finalization (race condition protection per
        REQUIREMENTS.md §8).

        Raises:
            NotFoundError: analytics record does not exist
            ImmutabilityError: record has been finalized
        """
        model = (
            self._session.query(AudioAnalyticsModel)
            .filter(AudioAnalyticsModel.id == analytics_id)
            .with_for_update()
            .first()
        )

        if model is None:
            raise NotFoundError(
                resource_type="AudioAnalytics",
                resource_id=analytics_id,
            )

        if model.transcript_finalized:
            raise ImmutabilityError(analytics_id=analytics_id)

        # Apply non-None fields from the update DTO
        update_fields = {
            k: v
            for k, v in data.__dict__.items()
            if v is not None
        }

        for field_name, value in update_fields.items():
            if hasattr(model, field_name):
                setattr(model, field_name, value)

        model.updated_at = datetime.now(timezone.utc)

        self._session.flush()

        logger.info(
            "Audio analytics updated",
            extra={
                "analytics_id": analytics_id,
                "updated_fields": list(update_fields.keys()),
            },
        )
        return model_to_entity(model)

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def finalize(self, analytics_id: int) -> AudioAnalytics:
        """
        Mark transcript as finalized (immutable).

        After finalization, no further updates are allowed.
        Idempotent: returns existing record if already finalized.

        Raises:
            NotFoundError: analytics record does not exist
        """
        model = (
            self._session.query(AudioAnalyticsModel)
            .filter(AudioAnalyticsModel.id == analytics_id)
            .with_for_update()
            .first()
        )

        if model is None:
            raise NotFoundError(
                resource_type="AudioAnalytics",
                resource_id=analytics_id,
            )

        if model.transcript_finalized:
            # Already finalized — idempotent
            return model_to_entity(model)

        model.transcript_finalized = True
        model.finalized_at = datetime.now(timezone.utc)
        model.updated_at = datetime.now(timezone.utc)

        self._session.flush()

        logger.info(
            "Audio analytics finalized",
            extra={
                "analytics_id": analytics_id,
                "exchange_id": model.interview_exchange_id,
            },
        )
        return model_to_entity(model)
