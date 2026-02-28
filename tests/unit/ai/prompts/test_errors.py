"""
Unit Tests — Prompt Errors

Tests for app.ai.prompts.errors:
- PromptNotFoundError
- VariableMissingError
- TemplateSyntaxError

Validates HTTP status codes, error codes, and metadata.
"""

import pytest
from app.ai.prompts.errors import (
    PromptNotFoundError,
    VariableMissingError,
    TemplateSyntaxError,
)


class TestPromptNotFoundError:
    """Tests for PromptNotFoundError."""

    def test_basic_creation(self):
        err = PromptNotFoundError(prompt_type="evaluation")
        assert err.http_status_code == 404
        assert err.error_code == "NOT_FOUND"
        assert "evaluation" in err.message
        assert err.metadata["prompt_type"] == "evaluation"

    def test_with_organization_id(self):
        err = PromptNotFoundError(
            prompt_type="question_generation",
            organization_id=42,
        )
        assert "42" in err.message
        assert err.metadata["organization_id"] == 42
        assert err.metadata["prompt_type"] == "question_generation"

    def test_without_organization_id(self):
        err = PromptNotFoundError(prompt_type="evaluation")
        assert "global" in err.message.lower() or "evaluation" in err.message

    def test_with_request_id(self):
        err = PromptNotFoundError(
            prompt_type="evaluation",
            request_id="req_abc123",
        )
        assert err.request_id == "req_abc123"

    def test_inherits_from_not_found(self):
        from app.shared.errors import NotFoundError
        err = PromptNotFoundError(prompt_type="evaluation")
        assert isinstance(err, NotFoundError)


class TestVariableMissingError:
    """Tests for VariableMissingError."""

    def test_single_missing_variable(self):
        err = VariableMissingError(missing_variables=["name"])
        assert err.http_status_code == 422
        assert "name" in err.message
        assert err.missing_variables == ["name"]

    def test_multiple_missing_variables(self):
        err = VariableMissingError(missing_variables=["c", "a", "b"])
        assert "a" in err.message
        assert "b" in err.message
        assert "c" in err.message
        # Metadata should have sorted list
        assert err.metadata["missing_variables"] == ["a", "b", "c"]

    def test_with_prompt_type(self):
        err = VariableMissingError(
            missing_variables=["name"],
            prompt_type="evaluation",
        )
        assert err.metadata["prompt_type"] == "evaluation"

    def test_inherits_from_validation_error(self):
        from app.shared.errors import ValidationError
        err = VariableMissingError(missing_variables=["x"])
        assert isinstance(err, ValidationError)


class TestTemplateSyntaxError:
    """Tests for TemplateSyntaxError."""

    def test_basic_creation(self):
        err = TemplateSyntaxError(message="Unclosed brace")
        assert err.http_status_code == 422
        assert "syntax" in err.message.lower()
        assert "Unclosed brace" in err.message

    def test_with_position(self):
        err = TemplateSyntaxError(message="Unclosed", position=42)
        assert err.metadata["position"] == 42

    def test_with_snippet(self):
        err = TemplateSyntaxError(
            message="Unclosed",
            template_snippet="{{name",
        )
        assert err.metadata["template_snippet"] == "{{name"

    def test_inherits_from_validation_error(self):
        from app.shared.errors import ValidationError
        err = TemplateSyntaxError(message="bad")
        assert isinstance(err, ValidationError)
