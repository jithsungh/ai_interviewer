"""
Read-Only Question Repository — PostgreSQL Static Pool Fallback

Provides SELECT-only access to the questions table.
Used when Qdrant is unavailable (circuit breaker open).

Multi-tenant isolation enforced on every query:
    (scope = 'public') OR (scope = 'organization' AND organization_id = X)

Does NOT create/update/delete questions — admin module owns mutations.
Imports QuestionModel from admin.persistence.models (read-only reference).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app.admin.persistence.models import QuestionModel
from app.question.retrieval.contracts import QuestionCandidate

logger = logging.getLogger(__name__)


class QuestionReadRepository:
    """
    Read-only PostgreSQL repository for question data.

    Injected with a SQLAlchemy Session via FastAPI DI.
    All methods enforce multi-tenant filtering.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Tenant filter predicate ────────────────────────────────────

    @staticmethod
    def _tenant_filter(organization_id: int):
        """
        SQLAlchemy WHERE clause for multi-tenant isolation.

        Returns rows where:
            scope = 'public'
            OR (scope = 'organization' AND organization_id = :org_id)
        """
        return or_(
            QuestionModel.scope == "public",
            and_(
                QuestionModel.scope == "organization",
                QuestionModel.organization_id == organization_id,
            ),
        )

    # ── Query methods ──────────────────────────────────────────────

    def get_by_id(
        self,
        question_id: int,
        organization_id: int,
    ) -> Optional[QuestionCandidate]:
        """
        Retrieve single question by ID with tenant check.

        Returns None if not found or not accessible.
        """
        row = (
            self._db.query(QuestionModel)
            .filter(
                QuestionModel.id == question_id,
                QuestionModel.is_active.is_(True),
                self._tenant_filter(organization_id),
            )
            .first()
        )

        if row is None:
            return None

        return self._to_candidate(row)

    def filter_by_criteria(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        question_type: Optional[str] = None,
        exclude_ids: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[QuestionCandidate]:
        """
        Filter questions by criteria with multi-tenant enforcement.

        Note: No topic_id filtering — QuestionModel does not have topic_id.
        Topic filtering is handled by Qdrant (primary path).
        """
        query = self._db.query(QuestionModel).filter(
            QuestionModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        if question_type:
            query = query.filter(QuestionModel.question_type == question_type)

        if exclude_ids:
            query = query.filter(QuestionModel.id.notin_(exclude_ids))

        return [self._to_candidate(row) for row in query.limit(limit).all()]

    def get_random(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        exclude_ids: Optional[List[int]] = None,
        limit: int = 5,
    ) -> List[QuestionCandidate]:
        """
        Get random questions matching criteria.

        Used for static-pool fallback when Qdrant is unavailable.
        Uses PostgreSQL RANDOM() for selection.
        """
        query = self._db.query(QuestionModel).filter(
            QuestionModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        if exclude_ids:
            query = query.filter(QuestionModel.id.notin_(exclude_ids))

        rows = query.order_by(func.random()).limit(limit).all()
        return [self._to_candidate(row) for row in rows]

    def get_by_ids_batch(
        self,
        question_ids: List[int],
        organization_id: int,
    ) -> List[QuestionCandidate]:
        """
        Batch-retrieve questions by IDs.

        Returns only questions accessible under tenant filter.
        Preserves input order.
        """
        if not question_ids:
            return []

        rows = (
            self._db.query(QuestionModel)
            .filter(
                QuestionModel.id.in_(question_ids),
                QuestionModel.is_active.is_(True),
                self._tenant_filter(organization_id),
            )
            .all()
        )

        # Preserve input order
        row_map = {row.id: row for row in rows}
        return [
            self._to_candidate(row_map[qid])
            for qid in question_ids
            if qid in row_map
        ]

    def count_available(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
    ) -> int:
        """Count available questions for given criteria."""
        query = self._db.query(func.count(QuestionModel.id)).filter(
            QuestionModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        return query.scalar() or 0

    # ── Mapper ─────────────────────────────────────────────────────

    @staticmethod
    def _to_candidate(row: QuestionModel) -> QuestionCandidate:
        """Map ORM model to QuestionCandidate DTO."""
        return QuestionCandidate(
            question_id=row.id,
            similarity_score=0.0,  # No vector search → no score
            difficulty=row.difficulty,
            scope=row.scope,
            metadata={
                "question_text": row.question_text,
                "question_type": row.question_type,
                "estimated_time_minutes": row.estimated_time_minutes,
                "source_type": row.source_type,
            },
        )
