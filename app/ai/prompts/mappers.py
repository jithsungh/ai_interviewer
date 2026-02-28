"""
Prompt Persistence Mappers

Bidirectional conversion between domain entities (dataclasses)
and SQLAlchemy ORM models.

Keeps the domain layer free of ORM dependencies.
Follows the same pattern as app.admin.persistence.mappers.
"""

from __future__ import annotations

from typing import Optional

from app.ai.prompts.entities import PromptTemplate
from app.ai.prompts.models import PromptTemplateModel


def prompt_model_to_entity(m: PromptTemplateModel) -> PromptTemplate:
    """
    Convert ORM model → domain entity.

    Maps every column from the prompt_templates row into
    the pure-dataclass PromptTemplate.
    """
    return PromptTemplate(
        id=m.id,
        name=m.name,
        prompt_type=m.prompt_type,
        scope=m.scope,
        organization_id=m.organization_id,
        system_prompt=m.system_prompt,
        user_prompt=m.user_prompt,
        model_id=m.model_id,
        model_config=m.model_config or {},
        version=m.version,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def prompt_entity_to_model(
    e: PromptTemplate,
    model: Optional[PromptTemplateModel] = None,
) -> PromptTemplateModel:
    """
    Convert domain entity → ORM model.

    If an existing ORM model instance is provided, updates it in-place.
    Otherwise creates a new one.

    NOTE: The prompts layer is READ-ONLY so this mapper is provided
    for completeness and testing only. In production, the admin module
    handles writes to prompt_templates.
    """
    if model is None:
        model = PromptTemplateModel()
    model.name = e.name
    model.prompt_type = e.prompt_type
    model.scope = e.scope
    model.organization_id = e.organization_id
    model.system_prompt = e.system_prompt
    model.user_prompt = e.user_prompt
    model.model_id = e.model_id
    model.model_config = e.model_config
    model.version = e.version
    model.is_active = e.is_active
    return model
