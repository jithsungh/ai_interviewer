"""
Prompt Service

Orchestrates prompt retrieval and rendering.

This is the primary public interface for the prompts layer.
Domain services in other modules (question/generation, evaluation/scoring, etc.)
depend on this service to get rendered prompts for LLM calls.

Design:
- Takes PromptTemplateRepository (protocol) via DI
- Uses PromptRenderer for variable substitution
- Handles scope resolution with fallback
- Returns RenderedPrompt ready for LLM consumption
- Raises typed errors for missing prompts

NO business logic. NO domain coupling. Infrastructure only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.ai.prompts.entities import PromptTemplate, RenderedPrompt
from app.ai.prompts.errors import PromptNotFoundError
from app.ai.prompts.protocols import PromptTemplateRepository
from app.ai.prompts.renderer import PromptRenderer

logger = logging.getLogger(__name__)


class PromptService:
    """
    Primary API for prompt template retrieval and rendering.

    Usage:
        service = PromptService(repository=SqlPromptTemplateRepository(session))
        rendered = service.get_rendered_prompt(
            prompt_type="question_generation",
            organization_id=42,
            variables={"role": "Backend Engineer", "topics": "Python, SQL"},
        )
    """

    def __init__(
        self,
        repository: PromptTemplateRepository,
        renderer: Optional[PromptRenderer] = None,
    ) -> None:
        self._repository = repository
        self._renderer = renderer or PromptRenderer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_prompt(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
        *,
        fallback_to_global: bool = True,
    ) -> PromptTemplate:
        """
        Retrieve the active prompt template for the given type.

        Resolution:
        1. Org-scoped active (if organization_id provided)
        2. Global active (if fallback_to_global=True)
        3. Raise PromptNotFoundError

        Args:
            prompt_type: Prompt type key ('question_generation', 'evaluation', etc.)
            organization_id: Organization scope (None = global only)
            fallback_to_global: Whether to fall back to global if org-scoped not found

        Returns:
            Active PromptTemplate

        Raises:
            PromptNotFoundError: No active prompt found
        """
        if fallback_to_global:
            template = self._repository.get_active_by_type(
                prompt_type, organization_id
            )
        else:
            template = self._repository.get_active_by_type_strict(
                prompt_type, organization_id
            )

        if template is None:
            raise PromptNotFoundError(
                prompt_type=prompt_type,
                organization_id=organization_id,
            )

        return template

    def render_prompt(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
        *,
        truncate_context: bool = False,
        max_context_tokens: Optional[int] = None,
    ) -> RenderedPrompt:
        """
        Render a prompt template with variable substitution.

        Args:
            template: Source prompt template
            variables: Variable name → value mapping
            truncate_context: Whether to truncate long values
            max_context_tokens: Max tokens for truncation

        Returns:
            RenderedPrompt ready for LLM call

        Raises:
            VariableMissingError: If required variables missing
            TemplateSyntaxError: If template syntax is invalid
        """
        return self._renderer.render(
            template=template,
            variables=variables,
            truncate_context=truncate_context,
            max_context_tokens=max_context_tokens,
        )

    def get_rendered_prompt(
        self,
        prompt_type: str,
        variables: Dict[str, Any],
        organization_id: Optional[int] = None,
        *,
        fallback_to_global: bool = True,
        truncate_context: bool = False,
        max_context_tokens: Optional[int] = None,
    ) -> RenderedPrompt:
        """
        Convenience method: retrieve + render in one call.

        Combines get_prompt() and render_prompt() for the common case.

        Args:
            prompt_type: Prompt type key
            variables: Variable values for substitution
            organization_id: Organization scope
            fallback_to_global: Whether to fall back to global
            truncate_context: Whether to truncate
            max_context_tokens: Max tokens for truncation

        Returns:
            RenderedPrompt ready for LLM call

        Raises:
            PromptNotFoundError: No active prompt found
            VariableMissingError: Required variables missing
            TemplateSyntaxError: Invalid template syntax
        """
        template = self.get_prompt(
            prompt_type=prompt_type,
            organization_id=organization_id,
            fallback_to_global=fallback_to_global,
        )

        rendered = self.render_prompt(
            template=template,
            variables=variables,
            truncate_context=truncate_context,
            max_context_tokens=max_context_tokens,
        )

        logger.info(
            "Prompt rendered successfully",
            extra={
                "event_type": "prompt.rendered",
                "prompt_type": prompt_type,
                "version": rendered.version,
                "variables_count": len(rendered.variables_used),
                "truncated": rendered.truncated,
                "organization_id": organization_id,
            },
        )

        return rendered

    def list_available_types(
        self,
        organization_id: Optional[int] = None,
    ) -> List[str]:
        """
        List all prompt types that have active versions.

        Args:
            organization_id: Organization scope

        Returns:
            Sorted list of distinct prompt_type strings
        """
        return self._repository.list_active_types(organization_id)

    def get_prompt_by_id(self, prompt_id: int) -> PromptTemplate:
        """
        Retrieve a prompt template by primary key.

        Args:
            prompt_id: Primary key

        Returns:
            PromptTemplate

        Raises:
            PromptNotFoundError: If not found
        """
        template = self._repository.get_by_id(prompt_id)
        if template is None:
            raise PromptNotFoundError(
                prompt_type=f"id={prompt_id}",
            )
        return template
