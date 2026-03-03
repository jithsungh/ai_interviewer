"""
Proctoring Ingestion Service — Event Processing Orchestrator

Validates incoming events, applies rules, persists to DB,
and triggers risk score recomputation.

Follows single-responsibility: receives validated DTO, returns result.
No HTTP concerns here — those live in the API layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.proctoring.ingestion.contracts.schemas import (
    BatchIngestionResult,
    EventIngestionResult,
    ProctoringEventInput,
)
from app.proctoring.persistence.repository import ProctoringEventRepository
from app.proctoring.rules.domain.rule_definitions import (
    ALLOWED_EVENT_TYPES,
    DEFAULT_CLUSTERING_MAP,
)
from app.proctoring.rules.domain.rule_engine import RuleEngine
from app.proctoring.risk_model.domain.risk_service import RiskModelService
from app.shared.errors import NotFoundError, ValidationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class IngestionService:
    """
    Processes proctoring events: validate → enrich → persist → recompute risk.

    Advisory-only: never blocks interview flow.
    """

    def __init__(
        self,
        session: Session,
        redis_client: Optional[object] = None,
    ) -> None:
        self._session = session
        self._redis = redis_client
        self._repo = ProctoringEventRepository(session)
        self._rule_engine = RuleEngine()
        self._risk_service = RiskModelService(
            session=session,
            redis_client=redis_client,
        )

    def ingest_event(
        self,
        event: ProctoringEventInput,
    ) -> EventIngestionResult:
        """
        Process a single proctoring event.

        Steps:
        1. Validate event type
        2. Check deduplication (via Redis if available)
        3. Apply rules (severity + weight + clustering)
        4. Persist to DB
        5. Recompute risk score

        Returns:
            EventIngestionResult with event_id and status.
        """
        # 1. Validate event type
        if not self._rule_engine.is_valid_event_type(event.event_type):
            raise ValidationError(
                message=f"Unknown event type: {event.event_type!r}",
                field="event_type",
            )

        # 2. Dedup check
        if self._is_duplicate(event):
            return EventIngestionResult(
                event_id=None,
                status="duplicate",
                message="Duplicate event detected — idempotent acknowledgment",
            )

        # 3. Apply rules (get clustering context from DB)
        clustering_context = self._get_clustering_context(
            event.submission_id, event.event_type, event.timestamp,
        )
        enriched = self._rule_engine.apply_rules(
            submission_id=event.submission_id,
            event_type=event.event_type,
            occurred_at=event.timestamp,
            evidence=event.metadata or {},
            recent_count_in_window=clustering_context["count_in_window"],
            consecutive_count=clustering_context["consecutive"],
        )

        # 4. Persist
        model = self._repo.create(
            interview_submission_id=event.submission_id,
            event_type=enriched.event_type,
            severity=enriched.applied_severity,
            risk_weight=enriched.applied_weight,
            evidence={
                **(event.metadata or {}),
                "rule_version": enriched.rule_version,
                "base_severity": enriched.base_severity,
                "base_weight": enriched.base_weight,
                "clustering_detected": enriched.clustering_detected,
                "clustering_reason": enriched.clustering_reason,
            },
            occurred_at=enriched.occurred_at,
        )

        # 5. Mark fingerprint in Redis (dedup)
        self._record_fingerprint(event)

        # 6. Recompute risk score
        try:
            self._risk_service.compute(event.submission_id)
        except Exception:
            logger.warning(
                "Risk recomputation failed after event ingestion",
                extra={"submission_id": event.submission_id, "event_id": model.id},
            )

        logger.debug(
            "Proctoring event ingested",
            extra={
                "event_id": model.id,
                "submission_id": event.submission_id,
                "event_type": event.event_type,
                "severity": enriched.applied_severity,
                "clustering": enriched.clustering_detected,
            },
        )

        return EventIngestionResult(
            event_id=model.id,
            status="accepted",
            message="Event accepted and processed",
        )

    def ingest_batch(
        self,
        submission_id: int,
        events: list[ProctoringEventInput],
    ) -> BatchIngestionResult:
        """
        Process a batch of proctoring events for the same submission.

        Each event is processed individually to ensure clustering detection
        accounts for previously ingested events in the same batch.
        """
        accepted = 0
        rejected = 0
        errors: list[dict] = []
        event_ids: list[int] = []

        for idx, event in enumerate(events):
            # Ensure all events target the same submission
            if event.submission_id != submission_id:
                rejected += 1
                errors.append({
                    "index": idx,
                    "event_type": event.event_type,
                    "reason": "submission_id mismatch with batch submission_id",
                })
                continue

            try:
                result = self.ingest_event(event)
                if result.status == "accepted" and result.event_id:
                    accepted += 1
                    event_ids.append(result.event_id)
                elif result.status == "duplicate":
                    accepted += 1  # Idempotent — counted as success
                else:
                    rejected += 1
                    errors.append({
                        "index": idx,
                        "event_type": event.event_type,
                        "reason": result.message,
                    })
            except (ValidationError, NotFoundError) as exc:
                rejected += 1
                errors.append({
                    "index": idx,
                    "event_type": event.event_type,
                    "reason": exc.message,
                })

        return BatchIngestionResult(
            accepted=accepted,
            rejected=rejected,
            event_ids=event_ids,
            errors=errors if errors else None,
        )

    # ────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────

    def _get_clustering_context(
        self,
        submission_id: int,
        event_type: str,
        current_time: datetime,
    ) -> dict:
        """
        Query DB for clustering detection context.

        Returns counts needed by the rule engine.
        """
        clustering_rules = DEFAULT_CLUSTERING_MAP.get(event_type, [])
        count_in_window = 0
        consecutive = 0

        for cr in clustering_rules:
            if cr.condition_type == "count_in_window":
                window_start = current_time - timedelta(seconds=cr.time_window_seconds)
                recent = self._repo.get_events_in_window(
                    submission_id, event_type, window_start, current_time,
                )
                count_in_window = max(count_in_window, len(recent))
            elif cr.condition_type == "consecutive":
                last_n = self._repo.get_last_n_events(
                    submission_id, event_type, cr.threshold,
                )
                consecutive = max(consecutive, len(last_n))

        return {"count_in_window": count_in_window, "consecutive": consecutive}

    def _is_duplicate(self, event: ProctoringEventInput) -> bool:
        """Check Redis for duplicate event (fingerprint-based)."""
        if not self._redis:
            return False
        try:
            fp = self._fingerprint(event)
            key = f"proctoring:dedup:{event.submission_id}"
            return bool(self._redis.sismember(key, fp))
        except Exception:
            return False

    def _record_fingerprint(self, event: ProctoringEventInput) -> None:
        """Store event fingerprint in Redis for dedup window."""
        if not self._redis:
            return
        try:
            fp = self._fingerprint(event)
            key = f"proctoring:dedup:{event.submission_id}"
            self._redis.sadd(key, fp)
            self._redis.expire(key, 300)  # 5 min dedup window
        except Exception:
            pass

    @staticmethod
    def _fingerprint(event: ProctoringEventInput) -> str:
        """Generate deterministic fingerprint for dedup."""
        import hashlib
        raw = f"{event.submission_id}:{event.event_type}:{event.timestamp.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
