"""
Unit Tests — PromptConfig

Tests default values, computed properties, and immutability.
No mocks, no I/O.
"""

import pytest

from app.question.prompting.config import PromptConfig, DEFAULT_INJECTION_PATTERNS


class TestPromptConfigDefaults:
    """Tests for PromptConfig default values."""

    def test_default_prompt_type(self):
        c = PromptConfig()
        assert c.prompt_type == "question_generation"

    def test_default_token_budget(self):
        c = PromptConfig()
        assert c.max_context_tokens == 7500
        assert c.llm_max_output_tokens == 500
        assert c.safety_margin_tokens == 192

    def test_default_safety_flags(self):
        c = PromptConfig()
        assert c.enable_injection_detection is True
        assert c.enable_sanitization is True

    def test_default_token_model(self):
        c = PromptConfig()
        assert c.token_model == "gpt-4"

    def test_default_context_limits(self):
        c = PromptConfig()
        assert c.max_previous_exchanges == 5
        assert c.max_resume_chars == 50_000
        assert c.max_jd_chars == 20_000

    def test_default_truncate_strategy(self):
        c = PromptConfig()
        assert c.truncate_strategy == "tail"


class TestPromptConfigComputedProperties:
    """Tests for PromptConfig.available_context_tokens."""

    def test_available_context_tokens(self):
        c = PromptConfig()
        expected = c.max_context_tokens - c.llm_max_output_tokens - c.safety_margin_tokens
        assert c.available_context_tokens == expected

    def test_available_context_tokens_custom(self):
        c = PromptConfig(
            max_context_tokens=10000,
            llm_max_output_tokens=1000,
            safety_margin_tokens=200,
        )
        assert c.available_context_tokens == 8800


class TestPromptConfigImmutability:
    """Tests that frozen=True is enforced."""

    def test_cannot_modify_prompt_type(self):
        c = PromptConfig()
        with pytest.raises(AttributeError):
            c.prompt_type = "changed"  # type: ignore[misc]

    def test_cannot_modify_token_budget(self):
        c = PromptConfig()
        with pytest.raises(AttributeError):
            c.max_context_tokens = 999  # type: ignore[misc]


class TestPromptConfigInjectionPatterns:
    """Tests for default injection patterns."""

    def test_default_patterns_not_empty(self):
        assert len(DEFAULT_INJECTION_PATTERNS) > 0

    def test_config_has_injection_patterns(self):
        c = PromptConfig()
        assert len(c.injection_patterns) == len(DEFAULT_INJECTION_PATTERNS)

    def test_custom_patterns(self):
        c = PromptConfig(injection_patterns=["custom_pattern"])
        assert c.injection_patterns == ["custom_pattern"]

