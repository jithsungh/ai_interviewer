"""
Prompt Repository Protocol

Abstract interface that the persistence layer MUST implement.
Domain services depend on this protocol — never on concrete DB classes.

Uses typing.Protocol for structural subtyping (consistent with
app.admin.domain.protocols pattern).
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from app.ai.prompts.entities import PromptTemplate


SUPER_ORG_ID = 1
"""Organization ID for the super/project-owner organization (global scope)."""


@runtime_checkable
class PromptTemplateRepository(Protocol):
    """
    Read-only repository for prompt_templates table.

    The prompts layer does NOT write to this table.
    All mutations are performed by the admin module.
    """

    def get_active_by_type(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Retrieve the active prompt template for the given type and org scope.

        Resolution priority:
        1. Active organization-scoped prompt (if organization_id provided)
        2. Active global prompt (scope='public', organization_id=SUPER_ORG_ID)
        3. None if nothing found

        Args:
            prompt_type: Prompt type key (e.g. 'question_generation')
            organization_id: Organization scope (None = global only)

        Returns:
            Active PromptTemplate or None
        """
        ...

    def get_active_by_type_strict(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Retrieve active prompt for exact scope only (no fallback).

        Args:
            prompt_type: Prompt type key
            organization_id: Exact org scope (None = global/public only)

        Returns:
            Active PromptTemplate or None (no fallback resolution)
        """
        ...

    def get_by_id(self, prompt_id: int) -> Optional[PromptTemplate]:
        """
        Retrieve prompt template by primary key.

        Args:
            prompt_id: Primary key

        Returns:
            PromptTemplate or None
        """
        ...

    def list_by_type(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
        *,
        include_inactive: bool = False,
    ) -> List[PromptTemplate]:
        """
        List all versions of a prompt type for the given scope.

        Args:
            prompt_type: Prompt type key
            organization_id: Organization scope (None = global only)
            include_inactive: Whether to include inactive versions

        Returns:
            List of PromptTemplate, ordered by version descending
        """
        ...

    def list_active_types(
        self,
        organization_id: Optional[int] = None,
    ) -> List[str]:
        """
        List all prompt_type values that have an active version.

        Includes both org-scoped and global (public) types.

        Args:
            organization_id: Organization scope (None = global only)

        Returns:
            List of distinct prompt_type strings
        """
        ...
