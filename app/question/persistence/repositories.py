"""
Question Persistence Repositories — Read-Only SQLAlchemy Implementations

Three concrete repositories:
- ``QuestionRepository``       — questions table with multi-tenant filtering
- ``TopicRepository``          — hierarchical topics with recursive CTE
- ``CodingProblemRepository``  — coding problems with secure test case loading

All repositories:
- Accept a SQLAlchemy ``Session`` via constructor
- Are strictly READ-ONLY (no create, update, or delete)
- Enforce multi-tenant isolation on every query
- Map ORM models → frozen domain entities via mappers

Session lifecycle is managed by the caller (FastAPI ``Depends(get_db_session)``).

Follows the pattern established by:
- app.question.retrieval.persistence.question_read_repository
- app.coding.persistence.repositories

References:
- persistence/REQUIREMENTS.md §3 (QuestionRepository)
- persistence/REQUIREMENTS.md §4 (TopicRepository)
- persistence/REQUIREMENTS.md §5 (CodingProblemRepository)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased

from app.admin.persistence.models import (
    CodingProblemModel,
    QuestionModel,
    TopicModel,
)
from app.question.persistence.entities import (
    CodingProblemEntity,
    QuestionEntity,
    TopicEntity,
)
from app.question.persistence.mappers import (
    coding_problem_model_to_entity,
    question_model_to_entity,
    topic_model_to_entity,
)
from app.question.persistence.models import (
    CodingProblemTopicModel,
    CodingTestCaseModel,
    QuestionTopicModel,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# QuestionRepository (read-only)
# ═══════════════════════════════════════════════════════════════════════════


class QuestionRepository:
    """
    Read-only repository for the ``questions`` table.

    All queries enforce multi-tenant isolation via ``_tenant_filter()``.
    No create/update/delete methods are provided.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Tenant filter ──────────────────────────────────────────────

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
    ) -> Optional[QuestionEntity]:
        """
        Retrieve single question by ID with multi-tenant check.

        Returns None if not found or not accessible to the organization.
        """
        row = (
            self._session.query(QuestionModel)
            .filter(
                QuestionModel.id == question_id,
                QuestionModel.is_active.is_(True),
                self._tenant_filter(organization_id),
            )
            .first()
        )
        if row is None:
            return None

        topic_ids = self._load_topic_ids([row.id]).get(row.id, [])
        return question_model_to_entity(row, topic_ids=topic_ids)

    def filter_by_criteria(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        question_type: Optional[str] = None,
        is_active: bool = True,
        limit: int = 100,
    ) -> List[QuestionEntity]:
        """
        Filter questions by criteria with multi-tenant enforcement.

        Args:
            organization_id: Tenant ID (required).
            difficulty: Filter by difficulty level.
            topic_ids: Filter by topic IDs (via question_topics junction).
            question_type: Filter by type (behavioral, technical, etc.).
            is_active: Filter by active status (default True).
            limit: Max results (default 100).

        Returns:
            List of matching QuestionEntity instances.
        """
        query = self._session.query(QuestionModel).filter(
            QuestionModel.is_active == is_active,
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        if question_type:
            query = query.filter(QuestionModel.question_type == question_type)

        if topic_ids:
            # Filter via junction table: question must be linked to at least
            # one of the requested topics.
            query = query.filter(
                QuestionModel.id.in_(
                    self._session.query(QuestionTopicModel.question_id).filter(
                        QuestionTopicModel.topic_id.in_(topic_ids)
                    )
                )
            )

        rows = query.limit(limit).all()

        # Batch-load topic IDs for all returned questions
        qids = [r.id for r in rows]
        topic_map = self._load_topic_ids(qids)

        return [
            question_model_to_entity(r, topic_ids=topic_map.get(r.id, []))
            for r in rows
        ]

    def get_random(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        exclude_ids: Optional[List[int]] = None,
        limit: int = 1,
    ) -> List[QuestionEntity]:
        """
        Get random questions matching criteria.

        Used for static-pool selection when Qdrant is unavailable.
        Uses PostgreSQL ``RANDOM()`` for selection.
        """
        query = self._session.query(QuestionModel).filter(
            QuestionModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)

        if topic_ids:
            query = query.filter(
                QuestionModel.id.in_(
                    self._session.query(QuestionTopicModel.question_id).filter(
                        QuestionTopicModel.topic_id.in_(topic_ids)
                    )
                )
            )

        if exclude_ids:
            query = query.filter(QuestionModel.id.notin_(exclude_ids))

        rows = query.order_by(func.random()).limit(limit).all()

        qids = [r.id for r in rows]
        topic_map = self._load_topic_ids(qids)

        return [
            question_model_to_entity(r, topic_ids=topic_map.get(r.id, []))
            for r in rows
        ]

    def get_by_ids_batch(
        self,
        question_ids: List[int],
        organization_id: int,
    ) -> Dict[int, QuestionEntity]:
        """
        Batch-retrieve questions by IDs with multi-tenant enforcement.

        Returns a dict mapping ``question_id → QuestionEntity``.
        Missing or inaccessible IDs are silently omitted.
        """
        if not question_ids:
            return {}

        rows = (
            self._session.query(QuestionModel)
            .filter(
                QuestionModel.id.in_(question_ids),
                QuestionModel.is_active.is_(True),
                self._tenant_filter(organization_id),
            )
            .all()
        )

        qids = [r.id for r in rows]
        topic_map = self._load_topic_ids(qids)

        return {
            r.id: question_model_to_entity(r, topic_ids=topic_map.get(r.id, []))
            for r in rows
        }

    def count_available(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> int:
        """Count available (active, tenant-visible) questions."""
        query = self._session.query(func.count(QuestionModel.id)).filter(
            QuestionModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )
        if difficulty:
            query = query.filter(QuestionModel.difficulty == difficulty)
        if question_type:
            query = query.filter(QuestionModel.question_type == question_type)
        return query.scalar() or 0

    # ── Private helpers ────────────────────────────────────────────

    def _load_topic_ids(self, question_ids: List[int]) -> Dict[int, List[int]]:
        """
        Batch-load topic IDs for a list of question IDs.

        Returns a dict mapping ``question_id → [topic_id, ...]``.
        Avoids N+1 queries.
        """
        if not question_ids:
            return {}

        rows = (
            self._session.query(
                QuestionTopicModel.question_id,
                QuestionTopicModel.topic_id,
            )
            .filter(QuestionTopicModel.question_id.in_(question_ids))
            .all()
        )

        result: Dict[int, List[int]] = {}
        for qid, tid in rows:
            result.setdefault(qid, []).append(tid)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# TopicRepository (read-only, hierarchical)
# ═══════════════════════════════════════════════════════════════════════════


class TopicRepository:
    """
    Read-only repository for the ``topics`` table.

    Supports hierarchical topic resolution via recursive CTEs.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, topic_id: int) -> Optional[TopicEntity]:
        """Get topic by primary key. Returns None if not found."""
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return None
        return topic_model_to_entity(row)

    def get_descendants(self, topic_id: int) -> List[int]:
        """
        Get all descendant topic IDs (inclusive of the starting node).

        Uses a recursive CTE:
            WITH RECURSIVE topic_tree AS (
                SELECT id, parent_topic_id FROM topics WHERE id = :topic_id
                UNION ALL
                SELECT t.id, t.parent_topic_id FROM topics t
                JOIN topic_tree tt ON t.parent_topic_id = tt.id
            )
            SELECT id FROM topic_tree;

        Example: topic_id=1 ("Technical") → [1, 2, 3, 5, 6, 7, ...]
        """
        # Anchor: the starting topic
        anchor = (
            self._session.query(
                TopicModel.id,
                TopicModel.parent_topic_id,
            )
            .filter(TopicModel.id == topic_id)
            .cte(name="topic_tree", recursive=True)
        )

        # Recursive term: children whose parent is in the CTE
        topic_alias = aliased(TopicModel, name="child_topic")
        recursive = self._session.query(
            topic_alias.id,
            topic_alias.parent_topic_id,
        ).join(anchor, topic_alias.parent_topic_id == anchor.c.id)

        full_cte = anchor.union_all(recursive)

        results = self._session.query(full_cte.c.id).all()
        return [row[0] for row in results]

    def get_ancestors(self, topic_id: int) -> List[int]:
        """
        Get all ancestor topic IDs from leaf to root.

        Uses a recursive CTE walking up parent_topic_id.

        Example: topic_id=5 ("Sorting") → [5, 2, 1]
                 (Sorting → Algorithms → Technical)
        """
        anchor = (
            self._session.query(
                TopicModel.id,
                TopicModel.parent_topic_id,
            )
            .filter(TopicModel.id == topic_id)
            .cte(name="ancestor_tree", recursive=True)
        )

        parent_alias = aliased(TopicModel, name="parent_topic")
        recursive = self._session.query(
            parent_alias.id,
            parent_alias.parent_topic_id,
        ).join(anchor, parent_alias.id == anchor.c.parent_topic_id)

        full_cte = anchor.union_all(recursive)

        results = self._session.query(full_cte.c.id).all()
        return [row[0] for row in results]

    def get_topic_tree(
        self,
        root_topic_id: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get topic tree as nested dicts.

        If ``root_topic_id`` is provided, returns the subtree rooted there.
        Otherwise returns the full forest (all root-level topics and children).

        Returns:
            List of ``{"id": int, "name": str, "children": [...]}`` dicts.
        """
        if root_topic_id is not None:
            descendant_ids = self.get_descendants(root_topic_id)
            rows = (
                self._session.query(TopicModel)
                .filter(TopicModel.id.in_(descendant_ids))
                .all()
            )
        else:
            rows = self._session.query(TopicModel).all()

        # Build lookup and tree
        by_id: Dict[int, Dict] = {}
        for r in rows:
            by_id[r.id] = {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "parent_topic_id": r.parent_topic_id,
                "children": [],
            }

        roots: List[Dict] = []
        for node in by_id.values():
            parent_id = node["parent_topic_id"]
            if parent_id and parent_id in by_id:
                by_id[parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    def resolve_topic_path(self, topic_id: int) -> str:
        """
        Build breadcrumb path from root to topic.

        Example: topic_id=5 → "Technical > Algorithms > Sorting"
        """
        ancestor_ids = self.get_ancestors(topic_id)
        # Ancestors are leaf-to-root; reverse for root-first breadcrumb
        ancestor_ids.reverse()

        names: List[str] = []
        for aid in ancestor_ids:
            topic = self.get_by_id(aid)
            if topic:
                names.append(topic.name)

        return " > ".join(names)

    def list_by_organization(
        self,
        organization_id: int,
        limit: int = 200,
    ) -> List[TopicEntity]:
        """
        List topics visible to an organization.

        Returns public + organization-scoped topics.
        """
        rows = (
            self._session.query(TopicModel)
            .filter(
                or_(
                    TopicModel.scope == "public",
                    and_(
                        TopicModel.scope == "organization",
                        TopicModel.organization_id == organization_id,
                    ),
                )
            )
            .limit(limit)
            .all()
        )
        return [topic_model_to_entity(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# CodingProblemRepository (read-only)
# ═══════════════════════════════════════════════════════════════════════════


class CodingProblemRepository:
    """
    Read-only repository for the ``coding_problems`` table.

    Security: Hidden test case expected outputs are masked by default.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Tenant filter ──────────────────────────────────────────────

    @staticmethod
    def _tenant_filter(organization_id: int):
        """Multi-tenant isolation for coding problems."""
        return or_(
            CodingProblemModel.scope == "public",
            and_(
                CodingProblemModel.scope == "organization",
                CodingProblemModel.organization_id == organization_id,
            ),
        )

    # ── Query methods ──────────────────────────────────────────────

    def get_by_id(
        self,
        problem_id: int,
        organization_id: int,
        *,
        include_hidden: bool = False,
    ) -> Optional[CodingProblemEntity]:
        """
        Get coding problem with test cases.

        Args:
            problem_id: Problem primary key.
            organization_id: Tenant ID for access check.
            include_hidden: If False (default), hidden test case expected_outputs
                           are set to None (security measure).

        Returns:
            CodingProblemEntity with loaded test_cases, or None.
        """
        row = (
            self._session.query(CodingProblemModel)
            .filter(
                CodingProblemModel.id == problem_id,
                CodingProblemModel.is_active.is_(True),
                self._tenant_filter(organization_id),
            )
            .first()
        )
        if row is None:
            return None

        test_cases = (
            self._session.query(CodingTestCaseModel)
            .filter(CodingTestCaseModel.coding_problem_id == problem_id)
            .order_by(CodingTestCaseModel.id)
            .all()
        )

        return coding_problem_model_to_entity(
            row, test_cases=test_cases, include_hidden_output=include_hidden
        )

    def filter_by_criteria(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        is_active: bool = True,
        limit: int = 50,
    ) -> List[CodingProblemEntity]:
        """
        Filter coding problems by criteria.

        Topic filtering uses the ``coding_problem_topics`` junction table.
        Test cases are NOT eagerly loaded for list queries (performance).
        """
        query = self._session.query(CodingProblemModel).filter(
            CodingProblemModel.is_active == is_active,
            self._tenant_filter(organization_id),
        )

        if difficulty:
            query = query.filter(CodingProblemModel.difficulty == difficulty)

        if topic_ids:
            query = query.filter(
                CodingProblemModel.id.in_(
                    self._session.query(
                        CodingProblemTopicModel.coding_problem_id
                    ).filter(
                        CodingProblemTopicModel.coding_topic_id.in_(topic_ids)
                    )
                )
            )

        rows = query.limit(limit).all()

        # For list queries, return without test cases (caller can load individually)
        return [coding_problem_model_to_entity(r) for r in rows]

    def get_starter_code(
        self,
        problem_id: int,
        language: str,
    ) -> Optional[str]:
        """
        Get starter code template for a given language.

        The ``code_snippets`` JSONB column stores
        ``{"python": "def solution(): ...", "javascript": "function solution() {}", ...}``.

        Returns:
            Starter code string, or None if problem not found or language unavailable.
        """
        row = (
            self._session.query(CodingProblemModel.code_snippets)
            .filter(CodingProblemModel.id == problem_id)
            .first()
        )
        if row is None or row[0] is None:
            return None

        snippets = row[0]
        if isinstance(snippets, dict):
            return snippets.get(language)
        return None

    def count_available(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
    ) -> int:
        """Count available (active, tenant-visible) coding problems."""
        query = self._session.query(func.count(CodingProblemModel.id)).filter(
            CodingProblemModel.is_active.is_(True),
            self._tenant_filter(organization_id),
        )
        if difficulty:
            query = query.filter(CodingProblemModel.difficulty == difficulty)
        return query.scalar() or 0
