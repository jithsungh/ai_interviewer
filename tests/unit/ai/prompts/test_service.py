"""
Unit Tests — Prompt Service

Tests for app.ai.prompts.service.PromptService:
- Prompt retrieval with fallback
- Prompt rendering via service
- Combined get_rendered_prompt
- Error propagation

Uses a mock repository (no DB dependency).
"""

import pytest
from typing import List, Optional
from unittest.mock import MagicMock

from app.ai.prompts.entities import PromptTemplate, RenderedPrompt
from app.ai.prompts.errors import PromptNotFoundError, VariableMissingError
from app.ai.prompts.service import PromptService


# ============================================================================
# Mock Repository
# ============================================================================

class FakePromptRepository:
    """In-memory prompt repository for testing."""

    def __init__(self, templates: Optional[List[PromptTemplate]] = None):
        self._templates = templates or []

    def get_active_by_type(
        self, prompt_type: str, organization_id: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        # Try org-scoped first
        if organization_id is not None:
            for t in self._templates:
                if (
                    t.prompt_type == prompt_type
                    and t.organization_id == organization_id
                    and t.is_active
                    and t.scope == "organization"
                ):
                    return t
        # Fallback to global
        for t in self._templates:
            if (
                t.prompt_type == prompt_type
                and t.scope == "public"
                and t.is_active
            ):
                return t
        return None

    def get_active_by_type_strict(
        self, prompt_type: str, organization_id: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        for t in self._templates:
            if (
                t.prompt_type == prompt_type
                and t.organization_id == organization_id
                and t.is_active
            ):
                return t
        return None

    def get_by_id(self, prompt_id: int) -> Optional[PromptTemplate]:
        for t in self._templates:
            if t.id == prompt_id:
                return t
        return None

    def list_by_type(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
        *,
        include_inactive: bool = False,
    ) -> List[PromptTemplate]:
        results = []
        for t in self._templates:
            if t.prompt_type != prompt_type:
                continue
            if not include_inactive and not t.is_active:
                continue
            results.append(t)
        return sorted(results, key=lambda x: x.version, reverse=True)

    def list_active_types(
        self, organization_id: Optional[int] = None
    ) -> List[str]:
        types = set()
        for t in self._templates:
            if t.is_active:
                types.add(t.prompt_type)
        return sorted(types)


# ============================================================================
# Helpers
# ============================================================================

def _make_template(
    id: int = 1,
    name: str = "test_v1",
    prompt_type: str = "evaluation",
    scope: str = "public",
    organization_id: int = 1,
    user_prompt: str = "Question: {{question_text}}",
    system_prompt: str = "You are an evaluator.",
    version: int = 1,
    is_active: bool = True,
    model_config: dict = None,
) -> PromptTemplate:
    return PromptTemplate(
        id=id,
        name=name,
        prompt_type=prompt_type,
        scope=scope,
        organization_id=organization_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_id=None,
        model_config=model_config or {"temperature": 0.0},
        version=version,
        is_active=is_active,
    )


# ============================================================================
# Test: get_prompt
# ============================================================================

class TestGetPrompt:
    """Tests for PromptService.get_prompt()"""

    def test_returns_global_prompt(self):
        repo = FakePromptRepository([
            _make_template(scope="public", organization_id=1),
        ])
        service = PromptService(repository=repo)
        result = service.get_prompt("evaluation")
        assert result.prompt_type == "evaluation"
        assert result.scope == "public"

    def test_returns_org_scoped_with_fallback(self):
        org_template = _make_template(
            id=2, scope="organization", organization_id=42
        )
        global_template = _make_template(
            id=1, scope="public", organization_id=1
        )
        repo = FakePromptRepository([org_template, global_template])
        service = PromptService(repository=repo)
        result = service.get_prompt("evaluation", organization_id=42)
        assert result.id == 2
        assert result.organization_id == 42

    def test_falls_back_to_global(self):
        global_template = _make_template(
            id=1, scope="public", organization_id=1
        )
        repo = FakePromptRepository([global_template])
        service = PromptService(repository=repo)
        # Org 99 has no prompt, should fallback to global
        result = service.get_prompt("evaluation", organization_id=99)
        assert result.id == 1
        assert result.scope == "public"

    def test_no_fallback_raises_not_found(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        with pytest.raises(PromptNotFoundError):
            service.get_prompt("evaluation", organization_id=42, fallback_to_global=False)

    def test_not_found_raises_error(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        with pytest.raises(PromptNotFoundError) as exc_info:
            service.get_prompt("nonexistent")
        assert "nonexistent" in str(exc_info.value)


# ============================================================================
# Test: render_prompt
# ============================================================================

class TestRenderPrompt:
    """Tests for PromptService.render_prompt()"""

    def test_successful_render(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        template = _make_template(user_prompt="Q: {{question_text}}")
        result = service.render_prompt(template, {"question_text": "What is SQL?"})
        assert result.text == "Q: What is SQL?"

    def test_missing_variable_raises(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        template = _make_template(user_prompt="{{a}} {{b}}")
        with pytest.raises(VariableMissingError):
            service.render_prompt(template, {"a": "1"})


# ============================================================================
# Test: get_rendered_prompt (convenience method)
# ============================================================================

class TestGetRenderedPrompt:
    """Tests for PromptService.get_rendered_prompt()"""

    def test_retrieve_and_render(self):
        template = _make_template(
            user_prompt="Q: {{question_text}}",
            system_prompt="You evaluate.",
        )
        repo = FakePromptRepository([template])
        service = PromptService(repository=repo)
        result = service.get_rendered_prompt(
            prompt_type="evaluation",
            variables={"question_text": "What is an index?"},
        )
        assert "What is an index?" in result.text
        assert result.system_prompt == "You evaluate."

    def test_prompt_not_found_propagates(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        with pytest.raises(PromptNotFoundError):
            service.get_rendered_prompt(
                prompt_type="nonexistent",
                variables={},
            )

    def test_missing_variable_propagates(self):
        template = _make_template(user_prompt="{{a}} {{b}}")
        repo = FakePromptRepository([template])
        service = PromptService(repository=repo)
        with pytest.raises(VariableMissingError):
            service.get_rendered_prompt(
                prompt_type="evaluation",
                variables={"a": "1"},
            )


# ============================================================================
# Test: list_available_types
# ============================================================================

class TestListAvailableTypes:
    """Tests for PromptService.list_available_types()"""

    def test_returns_active_types(self):
        templates = [
            _make_template(id=1, prompt_type="evaluation"),
            _make_template(id=2, prompt_type="question_generation"),
        ]
        repo = FakePromptRepository(templates)
        service = PromptService(repository=repo)
        types = service.list_available_types()
        assert "evaluation" in types
        assert "question_generation" in types

    def test_empty_repo_returns_empty(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        assert service.list_available_types() == []


# ============================================================================
# Test: get_prompt_by_id
# ============================================================================

class TestGetPromptById:
    """Tests for PromptService.get_prompt_by_id()"""

    def test_found(self):
        template = _make_template(id=42)
        repo = FakePromptRepository([template])
        service = PromptService(repository=repo)
        result = service.get_prompt_by_id(42)
        assert result.id == 42

    def test_not_found_raises(self):
        repo = FakePromptRepository([])
        service = PromptService(repository=repo)
        with pytest.raises(PromptNotFoundError):
            service.get_prompt_by_id(999)
