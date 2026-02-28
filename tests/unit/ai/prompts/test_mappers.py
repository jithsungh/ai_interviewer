"""
Unit Tests — Prompt Mappers

Tests for app.ai.prompts.mappers:
- ORM model → domain entity conversion
- Domain entity → ORM model conversion
- Field integrity across conversion
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.ai.prompts.entities import PromptTemplate
from app.ai.prompts.mappers import prompt_model_to_entity, prompt_entity_to_model
from app.ai.prompts.models import PromptTemplateModel


class TestModelToEntity:
    """Tests for prompt_model_to_entity mapper."""

    def _make_model(self, **overrides) -> PromptTemplateModel:
        """Create a mock ORM model with default values."""
        model = PromptTemplateModel()
        defaults = dict(
            id=1,
            name="eval_v1",
            prompt_type="evaluation",
            scope="public",
            organization_id=1,
            system_prompt="System",
            user_prompt="User {{var}}",
            model_id=None,
            model_config={"temperature": 0.0},
            version=1,
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        for k, v in defaults.items():
            setattr(model, k, v)
        return model

    def test_all_fields_mapped(self):
        model = self._make_model()
        entity = prompt_model_to_entity(model)
        assert entity.id == 1
        assert entity.name == "eval_v1"
        assert entity.prompt_type == "evaluation"
        assert entity.scope == "public"
        assert entity.organization_id == 1
        assert entity.system_prompt == "System"
        assert entity.user_prompt == "User {{var}}"
        assert entity.model_id is None
        assert entity.model_config == {"temperature": 0.0}
        assert entity.version == 1
        assert entity.is_active is True
        assert entity.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert entity.updated_at == datetime(2026, 1, 2, tzinfo=timezone.utc)

    def test_null_model_config_defaults_to_empty(self):
        model = self._make_model(model_config=None)
        entity = prompt_model_to_entity(model)
        assert entity.model_config == {}

    def test_org_scope(self):
        model = self._make_model(scope="organization", organization_id=42)
        entity = prompt_model_to_entity(model)
        assert entity.scope == "organization"
        assert entity.organization_id == 42
        assert entity.is_global is False

    def test_returns_prompt_template_type(self):
        model = self._make_model()
        entity = prompt_model_to_entity(model)
        assert isinstance(entity, PromptTemplate)


class TestEntityToModel:
    """Tests for prompt_entity_to_model mapper."""

    def _make_entity(self, **overrides) -> PromptTemplate:
        defaults = dict(
            id=1,
            name="eval_v1",
            prompt_type="evaluation",
            scope="public",
            organization_id=1,
            system_prompt="System",
            user_prompt="User {{var}}",
            model_id=None,
            model_config={"temperature": 0.0},
            version=1,
            is_active=True,
        )
        defaults.update(overrides)
        return PromptTemplate(**defaults)

    def test_creates_new_model(self):
        entity = self._make_entity()
        model = prompt_entity_to_model(entity)
        assert isinstance(model, PromptTemplateModel)
        assert model.name == "eval_v1"
        assert model.prompt_type == "evaluation"
        assert model.scope == "public"
        assert model.organization_id == 1
        assert model.system_prompt == "System"
        assert model.user_prompt == "User {{var}}"
        assert model.model_config == {"temperature": 0.0}
        assert model.version == 1
        assert model.is_active is True

    def test_updates_existing_model(self):
        entity = self._make_entity(name="updated")
        existing = PromptTemplateModel()
        existing.id = 99
        model = prompt_entity_to_model(entity, model=existing)
        assert model is existing  # Same object
        assert model.id == 99  # ID preserved
        assert model.name == "updated"

    def test_round_trip_preserves_fields(self):
        """Entity → Model → Entity should preserve all business fields."""
        original = self._make_entity(
            name="roundtrip",
            prompt_type="question_generation",
            model_config={"temperature": 0.7, "max_tokens": 1500},
            version=3,
        )
        model = prompt_entity_to_model(original)
        # Simulate DB setting timestamps
        model.id = 42
        model.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        model.updated_at = datetime(2026, 2, 2, tzinfo=timezone.utc)

        restored = prompt_model_to_entity(model)
        assert restored.name == "roundtrip"
        assert restored.prompt_type == "question_generation"
        assert restored.model_config == {"temperature": 0.7, "max_tokens": 1500}
        assert restored.version == 3
        assert restored.id == 42
