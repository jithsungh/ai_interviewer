"""
Risk Model Service — Orchestrates Risk Score Computation

Coordinates between persistence, domain computation, Redis cache,
and submission record updates. No business logic here — delegates to
the pure domain function ``compute_risk_score``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.proctoring.persistence.repository import ProctoringEventRepository
from app.proctoring.risk_model.domain.risk_computation import (
    DEFAULT_THRESHOLDS,
    EventData,
    RiskScore,
    RiskThresholds,
    compute_risk_score,
    is_flaggable,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class RiskModelService:
    """
    Application service for risk score computation.

    - Fetches events from repository
    - Delegates to pure domain computation
    - Persists results to Redis cache and submission record
    - Advisory-only: NEVER modifies interview state or evaluation scores
    """

    def __init__(
        self,
        session: Session,
        redis_client: Optional[object] = None,
        thresholds: Optional[RiskThresholds] = None,
        enable_time_decay: bool = False,
        decay_half_life_minutes: float = 30.0,
    ) -> None:
        self._session = session
        self._redis = redis_client
        self._repo = ProctoringEventRepository(session)
        self._thresholds = thresholds or DEFAULT_THRESHOLDS
        self._enable_time_decay = enable_time_decay
        self._decay_half_life_minutes = decay_half_life_minutes

    def compute(self, submission_id: int) -> RiskScore:
        """
        Compute current risk score for a submission.

        Fetches all events, computes score, caches result,
        and updates the submission record.
        """
        events = self._repo.get_by_submission(submission_id)
        event_data = [
            EventData(
                event_id=e.id,
                event_type=e.event_type,
                risk_weight=float(e.risk_weight),
                severity=e.severity,
                occurred_at=e.occurred_at,
            )
            for e in events
        ]

        risk_score = compute_risk_score(
            submission_id=submission_id,
            events=event_data,
            thresholds=self._thresholds,
            enable_time_decay=self._enable_time_decay,
            decay_half_life_minutes=self._decay_half_life_minutes,
        )

        # Cache in Redis
        self._cache_risk_score(risk_score)

        # Update submission record
        self._update_submission_risk(risk_score)

        logger.info(
            "Risk score computed",
            extra={
                "submission_id": submission_id,
                "total_risk": risk_score.total_risk,
                "classification": risk_score.classification,
                "event_count": risk_score.event_count,
            },
        )

        if is_flaggable(risk_score.classification):
            logger.warning(
                "Submission flagged for admin review",
                extra={
                    "submission_id": submission_id,
                    "risk_score": risk_score.total_risk,
                    "classification": risk_score.classification,
                },
            )

        return risk_score

    def recompute(self, submission_id: int) -> RiskScore:
        """
        Recompute risk score from scratch (audit use case).

        Same as compute — all events are always fetched fresh.
        """
        return self.compute(submission_id)

    def get_cached_risk(self, submission_id: int) -> Optional[dict]:
        """Retrieve cached risk score from Redis (fast path)."""
        if not self._redis:
            return None
        try:
            key = f"proctoring:risk:{submission_id}"
            data = self._redis.hgetall(key)
            if data:
                return {
                    "total_risk": float(data.get("total_risk", 0)),
                    "classification": data.get("classification", "low"),
                    "event_count": int(data.get("event_count", 0)),
                    "last_updated": data.get("last_updated", ""),
                }
        except Exception:
            logger.debug("Redis cache miss for risk score", extra={"submission_id": submission_id})
        return None

    # ────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────

    def _cache_risk_score(self, risk_score: RiskScore) -> None:
        """Store risk score in Redis for fast lookup."""
        if not self._redis:
            return
        try:
            key = f"proctoring:risk:{risk_score.submission_id}"
            self._redis.hset(
                key,
                mapping={
                    "total_risk": str(risk_score.total_risk),
                    "classification": risk_score.classification,
                    "event_count": str(risk_score.event_count),
                    "last_updated": risk_score.computed_at.isoformat(),
                },
            )
            self._redis.expire(key, 86400)  # 24 hours TTL
        except Exception:
            logger.debug(
                "Failed to cache risk score in Redis",
                extra={"submission_id": risk_score.submission_id},
            )

    def _update_submission_risk(self, risk_score: RiskScore) -> None:
        """Update interview_submissions with current risk data."""
        flagged = is_flaggable(risk_score.classification)
        try:
            self._session.execute(
                sql_text(
                    """
                    UPDATE interview_submissions
                    SET proctoring_risk_score = :score,
                        proctoring_risk_classification = :classification,
                        proctoring_flagged = :flagged,
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "score": risk_score.total_risk,
                    "classification": risk_score.classification,
                    "flagged": flagged,
                    "id": risk_score.submission_id,
                },
            )
        except Exception:
            logger.warning(
                "Failed to update submission risk columns "
                "(migration may not have been applied yet)",
                extra={"submission_id": risk_score.submission_id},
            )
