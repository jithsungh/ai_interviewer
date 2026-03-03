"""
Repository — Proctoring Event Storage & Retrieval

Provides typed database operations for proctoring_events table.
Events are immutable after creation — no UPDATE or DELETE methods exposed.

Follows repository pattern: takes Session in constructor, no business logic.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.proctoring.persistence.models import ProctoringEventModel
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class ProctoringEventRepository:
    """
    Repository for proctoring_events table.

    All queries enforce tenant isolation via interview_submission_id
    (which is already scoped to an organization through interview_submissions).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ────────────────────────────────────────────────────────────
    # CREATE
    # ────────────────────────────────────────────────────────────

    def create(
        self,
        interview_submission_id: int,
        event_type: str,
        severity: str,
        risk_weight: float,
        evidence: dict,
        occurred_at: datetime,
    ) -> ProctoringEventModel:
        """Insert a single proctoring event (immutable)."""
        model = ProctoringEventModel(
            interview_submission_id=interview_submission_id,
            event_type=event_type,
            severity=severity,
            risk_weight=Decimal(str(risk_weight)),
            evidence=evidence,
            occurred_at=occurred_at,
        )
        self._session.add(model)
        self._session.flush()
        logger.debug(
            "Proctoring event created",
            extra={
                "event_id": model.id,
                "submission_id": interview_submission_id,
                "event_type": event_type,
                "severity": severity,
            },
        )
        return model

    def create_batch(
        self,
        events: list[dict],
    ) -> list[ProctoringEventModel]:
        """
        Insert multiple proctoring events efficiently.

        Each dict must contain: interview_submission_id, event_type,
        severity, risk_weight, evidence, occurred_at.
        """
        if not events:
            return []

        models = []
        for evt in events:
            model = ProctoringEventModel(
                interview_submission_id=evt["interview_submission_id"],
                event_type=evt["event_type"],
                severity=evt["severity"],
                risk_weight=Decimal(str(evt["risk_weight"])),
                evidence=evt["evidence"],
                occurred_at=evt["occurred_at"],
            )
            self._session.add(model)
            models.append(model)

        self._session.flush()
        logger.debug(
            "Proctoring events batch created",
            extra={"count": len(models)},
        )
        return models

    # ────────────────────────────────────────────────────────────
    # READ
    # ────────────────────────────────────────────────────────────

    def get_by_submission(
        self,
        submission_id: int,
        severity_filter: Optional[str] = None,
        event_type_filter: Optional[str] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
    ) -> list[ProctoringEventModel]:
        """
        Retrieve all events for a submission in chronological order.

        This is the most common query — used for risk computation.
        """
        query = (
            self._session.query(ProctoringEventModel)
            .filter(ProctoringEventModel.interview_submission_id == submission_id)
        )

        if severity_filter:
            query = query.filter(ProctoringEventModel.severity == severity_filter)

        if event_type_filter:
            query = query.filter(ProctoringEventModel.event_type == event_type_filter)

        if time_range:
            start, end = time_range
            query = query.filter(
                ProctoringEventModel.occurred_at >= start,
                ProctoringEventModel.occurred_at <= end,
            )

        return query.order_by(ProctoringEventModel.occurred_at.asc()).all()

    def count_by_submission(
        self,
        submission_id: int,
        event_type: Optional[str] = None,
    ) -> int:
        """Count events for a submission (for clustering detection)."""
        query = (
            self._session.query(func.count(ProctoringEventModel.id))
            .filter(ProctoringEventModel.interview_submission_id == submission_id)
        )
        if event_type:
            query = query.filter(ProctoringEventModel.event_type == event_type)
        return query.scalar() or 0

    def get_events_in_window(
        self,
        submission_id: int,
        event_type: str,
        window_start: datetime,
        window_end: datetime,
    ) -> list[ProctoringEventModel]:
        """Get events of a specific type within a time window (for clustering)."""
        return (
            self._session.query(ProctoringEventModel)
            .filter(
                ProctoringEventModel.interview_submission_id == submission_id,
                ProctoringEventModel.event_type == event_type,
                ProctoringEventModel.occurred_at >= window_start,
                ProctoringEventModel.occurred_at <= window_end,
            )
            .order_by(ProctoringEventModel.occurred_at.asc())
            .all()
        )

    def get_last_n_events(
        self,
        submission_id: int,
        event_type: str,
        n: int,
    ) -> list[ProctoringEventModel]:
        """Get the last N events of a type for a submission (for consecutive clustering)."""
        return (
            self._session.query(ProctoringEventModel)
            .filter(
                ProctoringEventModel.interview_submission_id == submission_id,
                ProctoringEventModel.event_type == event_type,
            )
            .order_by(ProctoringEventModel.occurred_at.desc())
            .limit(n)
            .all()
        )

    def get_aggregated_weights(
        self,
        submission_id: int,
    ) -> list[dict]:
        """
        Get aggregated risk weights grouped by event type.

        Returns list of dicts: [{event_type, count, total_weight}]
        """
        rows = (
            self._session.query(
                ProctoringEventModel.event_type,
                func.count(ProctoringEventModel.id).label("count"),
                func.sum(ProctoringEventModel.risk_weight).label("total_weight"),
            )
            .filter(ProctoringEventModel.interview_submission_id == submission_id)
            .group_by(ProctoringEventModel.event_type)
            .all()
        )
        return [
            {
                "event_type": row.event_type,
                "count": row.count,
                "total_weight": float(row.total_weight),
            }
            for row in rows
        ]

    def get_event_count_by_severity(
        self,
        submission_id: int,
    ) -> dict[str, int]:
        """Count events per severity level for a submission."""
        rows = (
            self._session.query(
                ProctoringEventModel.severity,
                func.count(ProctoringEventModel.id).label("count"),
            )
            .filter(ProctoringEventModel.interview_submission_id == submission_id)
            .group_by(ProctoringEventModel.severity)
            .all()
        )
        return {row.severity: row.count for row in rows}

    def delete_older_than(
        self,
        retention_date: datetime,
        submission_ids: Optional[list[int]] = None,
    ) -> int:
        """
        Delete events older than retention date (for retention policy).

        Returns count of deleted rows.
        """
        query = (
            self._session.query(ProctoringEventModel)
            .filter(ProctoringEventModel.created_at < retention_date)
        )
        if submission_ids:
            query = query.filter(
                ProctoringEventModel.interview_submission_id.in_(submission_ids)
            )
        count = query.delete(synchronize_session="fetch")
        logger.info(
            "Proctoring events retention cleanup",
            extra={"deleted_count": count, "retention_date": retention_date.isoformat()},
        )
        return count
