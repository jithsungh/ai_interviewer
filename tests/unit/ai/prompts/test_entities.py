"""
Unit Tests — Prompt Entities

Tests for app.ai.prompts.entities:
- PromptTemplate dataclass behavior
- RenderedPrompt properties and defaults
- PromptType enum values
"""

import pytest
from app.ai.prompts.entities import PromptTemplate, RenderedPrompt, PromptType


# ============================================================================
# PromptType Enum
# ============================================================================

class TestPromptType:
    """Tests for PromptType enum."""

    def test_question_generation_value(self):
        assert PromptType.QUESTION_GENERATION.value == "question_generation"

    def test_evaluation_value(self):
        assert PromptType.EVALUATION.value == "evaluation"

    def test_resume_parsing_value(self):
        assert PromptType.RESUME_PARSING.value == "resume_parsing"

    def test_jd_parsing_value(self):
        assert PromptType.JD_PARSING.value == "jd_parsing"

    def test_report_generation_value(self):
        assert PromptType.REPORT_GENERATION.value == "report_generation"

    def test_clarification_value(self):
        assert PromptType.CLARIFICATION.value == "clarification"

    def test_all_types_are_strings(self):
        for pt in PromptType:
            assert isinstance(pt, str)
            assert isinstance(pt.value, str)


# ============================================================================
# PromptTemplate Entity
# ============================================================================

class TestPromptTemplate:
    """Tests for PromptTemplate dataclass."""

    def _make(self, **overrides) -> PromptTemplate:
        defaults = dict(
            id=1,
            name="test",
            prompt_type="evaluation",
            scope="public",
            organization_id=1,
            system_prompt="System msg",
            user_prompt="User msg {{var}}",
            model_id=None,
            model_config={"temperature": 0.7, "max_tokens": 2000},
            version=1,
            is_active=True,
        )
        defaults.update(overrides)
        return PromptTemplate(**defaults)

    def test_basic_creation(self):
        t = self._make()
        assert t.id == 1
        assert t.name == "test"
        assert t.prompt_type == "evaluation"
        assert t.is_active is True

    def test_temperature_property(self):
        t = self._make(model_config={"temperature": 0.0})
        assert t.temperature == 0.0

    def test_temperature_missing_returns_none(self):
        t = self._make(model_config={})
        assert t.temperature is None

    def test_max_tokens_property(self):
        t = self._make(model_config={"max_tokens": 1500})
        assert t.max_tokens == 1500

    def test_max_tokens_missing_returns_none(self):
        t = self._make(model_config={})
        assert t.max_tokens is None

    def test_is_global_public_scope(self):
        t = self._make(scope="public")
        assert t.is_global is True

    def test_is_global_org_scope(self):
        t = self._make(scope="organization")
        assert t.is_global is False

    def test_is_global_private_scope(self):
        t = self._make(scope="private")
        assert t.is_global is False

    def test_optional_fields_default(self):
        t = self._make()
        assert t.created_at is None
        assert t.updated_at is None


# ============================================================================
# RenderedPrompt Entity
# ============================================================================

class TestRenderedPrompt:
    """Tests for RenderedPrompt dataclass."""

    def test_basic_creation(self):
        r = RenderedPrompt(
            text="Hello world",
            system_prompt="Be helpful",
            version=3,
            prompt_type="evaluation",
        )
        assert r.text == "Hello world"
        assert r.system_prompt == "Be helpful"
        assert r.version == 3

    def test_defaults(self):
        r = RenderedPrompt(text="Hello")
        assert r.system_prompt is None
        assert r.model_id is None
        assert r.model_config == {}
        assert r.version == 0
        assert r.prompt_type == ""
        assert r.variables_used == []
        assert r.truncated is False

    def test_temperature_property(self):
        r = RenderedPrompt(
            text="Hello",
            model_config={"temperature": 0.0},
        )
        assert r.temperature == 0.0

    def test_max_tokens_property(self):
        r = RenderedPrompt(
            text="Hello",
            model_config={"max_tokens": 2000},
        )
        assert r.max_tokens == 2000

    def test_empty_model_config_returns_none(self):
        r = RenderedPrompt(text="Hello")
        assert r.temperature is None
        assert r.max_tokens is None
