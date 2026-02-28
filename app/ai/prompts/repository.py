"""
SQL Prompt Template Repository

Concrete implementation of PromptTemplateRepository using SQLAlchemy.

Follows the admin module convention:
- Session injected via constructor (caller owns commit/rollback)
- Pure read-only — no writes to prompt_templates
- Uses mappers for ORM ↔ entity conversion
- Multi-tenancy scope resolution (org → global fallback)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import and_, or_, distinct
from sqlalchemy.orm import Session

from app.ai.prompts.entities import PromptTemplate
from app.ai.prompts.mappers import prompt_model_to_entity
from app.ai.prompts.models import PromptTemplateModel
from app.ai.prompts.protocols import SUPER_ORG_ID

logger = logging.getLogger(__name__)


class SqlPromptTemplateRepository:
    """
    Read-only SQL repository for prompt_templates.

    Implements PromptTemplateRepository protocol.

    Scope resolution:
    - organization_id = SUPER_ORG_ID (1) AND scope = 'public' → Global prompt
    - organization_id = X → Organization-scoped prompt

    The get_active_by_type method implements the fallback chain:
    org-scoped active → global active → None
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # PromptTemplateRepository protocol implementation
    # ------------------------------------------------------------------

    def get_active_by_type(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Retrieve active prompt with org → global fallback.

        1. If organization_id provided: try org-scoped active first
        2. Fallback to global (scope='public', org_id=SUPER_ORG_ID)
        3. Return None if nothing found
        """
        # Step 1: Try org-scoped prompt
        if organization_id is not None and organization_id != SUPER_ORG_ID:
            org_prompt = self._get_active_for_scope(prompt_type, organization_id)
            if org_prompt is not None:
                logger.debug(
                    "Resolved org-scoped prompt",
                    extra={
                        "prompt_type": prompt_type,
                        "organization_id": organization_id,
                        "version": org_prompt.version,
                    },
                )
                return org_prompt

        # Step 2: Fallback to global
        global_prompt = self._get_active_global(prompt_type)
        if global_prompt is not None:
            logger.debug(
                "Resolved global prompt%s",
                " (fallback)" if organization_id else "",
                extra={
                    "prompt_type": prompt_type,
                    "organization_id": organization_id,
                    "version": global_prompt.version,
                },
            )
            return global_prompt

        logger.warning(
            "No active prompt found",
            extra={
                "prompt_type": prompt_type,
                "organization_id": organization_id,
            },
        )
        return None

    def get_active_by_type_strict(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Retrieve active prompt for exact scope (no fallback).
        """
        if organization_id is None:
            return self._get_active_global(prompt_type)
        return self._get_active_for_scope(prompt_type, organization_id)

    def get_by_id(self, prompt_id: int) -> Optional[PromptTemplate]:
        """Retrieve prompt template by PK."""
        model = (
            self._session.query(PromptTemplateModel)
            .filter(PromptTemplateModel.id == prompt_id)
            .first()
        )
        if model is None:
            return None
        return prompt_model_to_entity(model)

    def list_by_type(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
        *,
        include_inactive: bool = False,
    ) -> List[PromptTemplate]:
        """
        List all versions of a prompt type, ordered by version desc.
        """
        query = self._session.query(PromptTemplateModel).filter(
            PromptTemplateModel.prompt_type == prompt_type,
        )

        # Scope filter: show org-scoped + global
        if organization_id is not None and organization_id != SUPER_ORG_ID:
            query = query.filter(
                or_(
                    PromptTemplateModel.organization_id == organization_id,
                    and_(
                        PromptTemplateModel.organization_id == SUPER_ORG_ID,
                        PromptTemplateModel.scope == "public",
                    ),
                )
            )
        else:
            query = query.filter(
                and_(
                    PromptTemplateModel.organization_id == SUPER_ORG_ID,
                    PromptTemplateModel.scope == "public",
                )
            )

        if not include_inactive:
            query = query.filter(PromptTemplateModel.is_active == True)  # noqa: E712

        return [
            prompt_model_to_entity(m)
            for m in query.order_by(PromptTemplateModel.version.desc()).all()
        ]

    def list_active_types(
        self,
        organization_id: Optional[int] = None,
    ) -> List[str]:
        """List distinct prompt_type values with at least one active version."""
        query = self._session.query(
            distinct(PromptTemplateModel.prompt_type)
        ).filter(
            PromptTemplateModel.is_active == True,  # noqa: E712
        )

        if organization_id is not None and organization_id != SUPER_ORG_ID:
            query = query.filter(
                or_(
                    PromptTemplateModel.organization_id == organization_id,
                    and_(
                        PromptTemplateModel.organization_id == SUPER_ORG_ID,
                        PromptTemplateModel.scope == "public",
                    ),
                )
            )
        else:
            query = query.filter(
                and_(
                    PromptTemplateModel.organization_id == SUPER_ORG_ID,
                    PromptTemplateModel.scope == "public",
                )
            )

        return sorted([row[0] for row in query.all()])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_active_for_scope(
        self,
        prompt_type: str,
        organization_id: int,
    ) -> Optional[PromptTemplate]:
        """Get active prompt for exact org scope."""
        model = (
            self._session.query(PromptTemplateModel)
            .filter(
                PromptTemplateModel.prompt_type == prompt_type,
                PromptTemplateModel.organization_id == organization_id,
                PromptTemplateModel.is_active == True,  # noqa: E712
            )
            .first()
        )
        if model is None:
            return None
        return prompt_model_to_entity(model)

    def _get_active_global(
        self,
        prompt_type: str,
    ) -> Optional[PromptTemplate]:
        """Get active global prompt (scope='public', org_id=SUPER_ORG_ID)."""
        model = (
            self._session.query(PromptTemplateModel)
            .filter(
                PromptTemplateModel.prompt_type == prompt_type,
                PromptTemplateModel.scope == "public",
                PromptTemplateModel.organization_id == SUPER_ORG_ID,
                PromptTemplateModel.is_active == True,  # noqa: E712
            )
            .first()
        )
        if model is None:
            return None
        return prompt_model_to_entity(model)
