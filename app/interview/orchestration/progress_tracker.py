"""
Progress Tracker — Exchange Progress Management

Manages progress tracking in both PostgreSQL (durable) and Redis (fast reads).
Updates ``current_exchange_sequence`` in DB and session progress in Redis.

Uses existing infrastructure:
- ``app.persistence.redis`` for Redis operations
- DB session for atomic progress updates
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.interview.orchestration.contracts import ProgressUpdate
from app.interview.session.persistence.models import InterviewSubmissionModel
from app.shared.errors import NotFoundError

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Tracks interview progress across DB and Redis.

    DB: ``current_exchange_sequence`` column (durable, source of truth).
    Redis: session progress snapshot (fast reads for real-time updates).
    """

    def __init__(self, db: Session, redis) -> None:
        self._db = db
        self._redis = redis

    def update_progress(
        self,
        submission_id: int,
        sequence_order: int,
        total_questions: int,
    ) -> ProgressUpdate:
        """
        Update progress in both DB and Redis after exchange creation.

        Steps:
        1. Atomically update ``current_exchange_sequence`` in DB
        2. Update Redis session snapshot with progress data
        3. Return progress DTO for broadcast

        Args:
            submission_id: Interview submission ID.
            sequence_order: The sequence_order of the just-created exchange.
            total_questions: Total questions from template snapshot.

        Returns:
            ProgressUpdate DTO with current progress data.

        Raises:
            NotFoundError: If submission does not exist.
        """
        # Step 1: Atomic DB update (only advance, never go backward)
        self._update_db_progress(submission_id, sequence_order)

        # Step 2: Compute progress
        progress_percentage = (
            (sequence_order / total_questions) * 100
            if total_questions > 0
            else 0.0
        )
        is_complete = sequence_order >= total_questions

        progress = ProgressUpdate(
            submission_id=submission_id,
            current_sequence=sequence_order,
            total_questions=total_questions,
            progress_percentage=round(progress_percentage, 2),
            is_complete=is_complete,
        )

        # Step 3: Update Redis
        self._update_redis_progress(progress)

        logger.info(
            "Progress updated",
            extra={
                "submission_id": submission_id,
                "sequence_order": sequence_order,
                "total_questions": total_questions,
                "progress_percentage": progress.progress_percentage,
                "is_complete": is_complete,
            },
        )

        return progress

    def get_progress(self, submission_id: int) -> Optional[ProgressUpdate]:
        """
        Read current progress from Redis (fast path).

        Falls back to DB if Redis cache miss.

        Args:
            submission_id: Interview submission ID.

        Returns:
            ProgressUpdate if found, None otherwise.
        """
        # Try Redis first
        try:
            key = f"interview_session:{submission_id}"
            raw = self._redis.get(key)
            if raw:
                data = json.loads(raw)
                current_seq = data.get("current_sequence", 0)
                total_q = data.get("total_questions", 0)
                if total_q > 0:
                    return ProgressUpdate(
                        submission_id=submission_id,
                        current_sequence=current_seq,
                        total_questions=total_q,
                        progress_percentage=round(
                            (current_seq / total_q) * 100, 2
                        ),
                        is_complete=current_seq >= total_q,
                    )
        except Exception:
            logger.warning(
                "Failed to read progress from Redis, falling back to DB",
                exc_info=True,
            )

        # Fallback: read from DB
        sub = (
            self._db.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == submission_id)
            .first()
        )
        if sub is None:
            return None

        # Derive total_questions from template snapshot if available
        total_q = 0
        snapshot = getattr(sub, "template_structure_snapshot", None)
        if isinstance(snapshot, dict):
            total_q = snapshot.get("total_questions", 0)

        if total_q <= 0:
            # Cannot build a valid ProgressUpdate without total_questions
            logger.debug(
                "DB fallback: no template snapshot — cannot compute progress",
                extra={"submission_id": submission_id},
            )
            return None

        current_seq = sub.current_exchange_sequence or 0
        return ProgressUpdate(
            submission_id=submission_id,
            current_sequence=current_seq,
            total_questions=total_q,
            progress_percentage=round((current_seq / total_q) * 100, 2),
            is_complete=current_seq >= total_q,
        )

    # ────────────────────────────────────────────────────────────
    # Internal
    # ────────────────────────────────────────────────────────────

    def _update_db_progress(self, submission_id: int, sequence_order: int) -> None:
        """
        Atomically update current_exchange_sequence in DB.

        Uses UPDATE...WHERE to ensure we only advance (never regress).
        """
        sql = text(
            "UPDATE interview_submissions "
            "SET current_exchange_sequence = :seq, updated_at = now() "
            "WHERE id = :sid AND current_exchange_sequence < :seq "
            "RETURNING id"
        )
        result = self._db.execute(
            sql, {"seq": sequence_order, "sid": submission_id}
        )
        row = result.fetchone()

        if row is None:
            # Either submission doesn't exist or sequence already >= seq
            sub = (
                self._db.query(InterviewSubmissionModel)
                .filter(InterviewSubmissionModel.id == submission_id)
                .first()
            )
            if sub is None:
                raise NotFoundError(
                    resource_type="Submission", resource_id=submission_id
                )
            # Otherwise: idempotent (sequence already at or past this value)
            logger.debug(
                "Progress already at or past sequence",
                extra={
                    "submission_id": submission_id,
                    "requested_sequence": sequence_order,
                    "current_sequence": sub.current_exchange_sequence,
                },
            )

    def _update_redis_progress(self, progress: ProgressUpdate) -> None:
        """
        Update Redis session snapshot with progress data.

        Merges into existing session snapshot if present.
        """
        key = f"interview_session:{progress.submission_id}"
        try:
            # Read existing session data (set by SessionService)
            existing_raw = self._redis.get(key)
            if existing_raw:
                session_data = json.loads(existing_raw)
            else:
                session_data = {"submission_id": progress.submission_id}

            # Merge progress fields
            session_data["current_sequence"] = progress.current_sequence
            session_data["total_questions"] = progress.total_questions
            session_data["progress_percentage"] = progress.progress_percentage
            session_data["is_complete"] = progress.is_complete

            self._redis.set(
                key,
                json.dumps(session_data, default=str),
                ex=3900,  # ~65 minutes TTL
            )
        except Exception:
            logger.warning(
                "Failed to update progress in Redis",
                exc_info=True,
            )
