"""
Unit Tests — Prompt Renderer

Tests for app.ai.prompts.renderer.PromptRenderer:
- Simple variable substitution
- Missing variable detection
- Variable coercion (None, list, dict)
- Truncation of large values
- Sanitization
- System prompt rendering
"""

import pytest
from app.ai.prompts.entities import PromptTemplate, RenderedPrompt
from app.ai.prompts.renderer import PromptRenderer
from app.ai.prompts.errors import VariableMissingError, TemplateSyntaxError


# ============================================================================
# Helpers
# ============================================================================

def _make_template(
    user_prompt: str = "Hello {{name}}",
    system_prompt: str = "System",
    prompt_type: str = "test",
    model_config: dict = None,
    version: int = 1,
) -> PromptTemplate:
    """Factory for test PromptTemplate instances."""
    return PromptTemplate(
        id=1,
        name="test_template",
        prompt_type=prompt_type,
        scope="public",
        organization_id=1,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_id=None,
        model_config=model_config or {"temperature": 0.7},
        version=version,
        is_active=True,
    )


# ============================================================================
# Simple Substitution
# ============================================================================

class TestSimpleSubstitution:
    """Tests for basic variable substitution."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_single_variable(self):
        template = _make_template(user_prompt="Hello {{name}}")
        result = self.renderer.render(template, {"name": "Alice"})
        assert result.text == "Hello Alice"

    def test_multiple_variables(self):
        template = _make_template(
            user_prompt="{{role}} interview about {{topic}}"
        )
        result = self.renderer.render(template, {"role": "Backend", "topic": "SQL"})
        assert result.text == "Backend interview about SQL"

    def test_repeated_variable(self):
        template = _make_template(
            user_prompt="{{name}} said hello. {{name}} left."
        )
        result = self.renderer.render(template, {"name": "Bob"})
        assert result.text == "Bob said hello. Bob left."

    def test_no_variables_template(self):
        template = _make_template(user_prompt="No variables here")
        result = self.renderer.render(template, {})
        assert result.text == "No variables here"

    def test_system_prompt_rendered(self):
        template = _make_template(
            user_prompt="Question: {{question}}",
            system_prompt="You evaluate {{dimension}}.",
        )
        result = self.renderer.render(
            template, {"question": "What is SQL?", "dimension": "correctness"}
        )
        assert result.text == "Question: What is SQL?"
        assert result.system_prompt == "You evaluate correctness."

    def test_system_prompt_none(self):
        template = _make_template(
            user_prompt="Hello {{name}}",
            system_prompt="",
        )
        result = self.renderer.render(template, {"name": "Alice"})
        assert result.system_prompt is None or result.system_prompt == ""

    def test_whitespace_in_variable_name(self):
        template = _make_template(user_prompt="Hello {{ name }}")
        result = self.renderer.render(template, {"name": "Alice"})
        assert result.text == "Hello Alice"


# ============================================================================
# RenderedPrompt Metadata
# ============================================================================

class TestRenderedPromptMetadata:
    """Tests for RenderedPrompt field population."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_version_carried_through(self):
        template = _make_template(user_prompt="{{x}}", version=5)
        result = self.renderer.render(template, {"x": "val"})
        assert result.version == 5

    def test_prompt_type_carried_through(self):
        template = _make_template(user_prompt="{{x}}", prompt_type="evaluation")
        result = self.renderer.render(template, {"x": "val"})
        assert result.prompt_type == "evaluation"

    def test_model_config_carried_through(self):
        config = {"temperature": 0.0, "max_tokens": 2000, "deterministic": True}
        template = _make_template(user_prompt="{{x}}", model_config=config)
        result = self.renderer.render(template, {"x": "val"})
        assert result.model_config == config
        assert result.temperature == 0.0
        assert result.max_tokens == 2000

    def test_variables_used_populated(self):
        template = _make_template(user_prompt="{{a}} and {{b}}")
        result = self.renderer.render(template, {"a": "1", "b": "2"})
        assert result.variables_used == ["a", "b"]

    def test_truncated_default_false(self):
        template = _make_template(user_prompt="{{x}}")
        result = self.renderer.render(template, {"x": "short"})
        assert result.truncated is False


# ============================================================================
# Missing Variables
# ============================================================================

class TestMissingVariables:
    """Tests for VariableMissingError raising."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_single_missing_variable(self):
        template = _make_template(user_prompt="{{name}} {{age}}")
        with pytest.raises(VariableMissingError) as exc_info:
            self.renderer.render(template, {"name": "Alice"})
        assert "age" in exc_info.value.missing_variables

    def test_multiple_missing_variables(self):
        template = _make_template(user_prompt="{{a}} {{b}} {{c}}")
        with pytest.raises(VariableMissingError) as exc_info:
            self.renderer.render(template, {"a": "1"})
        assert set(exc_info.value.missing_variables) == {"b", "c"}

    def test_all_missing(self):
        template = _make_template(user_prompt="{{x}} {{y}}")
        with pytest.raises(VariableMissingError) as exc_info:
            self.renderer.render(template, {})
        assert set(exc_info.value.missing_variables) == {"x", "y"}

    def test_extra_variables_ignored(self):
        """Extra variables in dict that aren't in template should be fine."""
        template = _make_template(user_prompt="{{name}}")
        result = self.renderer.render(
            template, {"name": "Alice", "extra": "ignored"}
        )
        assert result.text == "Hello Alice" or "Alice" in result.text

    def test_missing_in_system_prompt(self):
        """Missing variable in system_prompt should also raise."""
        template = _make_template(
            user_prompt="Hello",
            system_prompt="Mode: {{mode}}",
        )
        with pytest.raises(VariableMissingError) as exc_info:
            self.renderer.render(template, {})
        assert "mode" in exc_info.value.missing_variables


# ============================================================================
# Variable Coercion
# ============================================================================

class TestVariableCoercion:
    """Tests for automatic type coercion of variable values."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_none_coerced_to_empty_string(self):
        template = _make_template(user_prompt="Value: {{val}}")
        result = self.renderer.render(template, {"val": None})
        assert result.text == "Value: "

    def test_int_coerced_to_string(self):
        template = _make_template(user_prompt="Score: {{score}}")
        result = self.renderer.render(template, {"score": 85})
        assert result.text == "Score: 85"

    def test_float_coerced_to_string(self):
        template = _make_template(user_prompt="Temp: {{temp}}")
        result = self.renderer.render(template, {"temp": 0.7})
        assert result.text == "Temp: 0.7"

    def test_list_coerced_to_json(self):
        template = _make_template(user_prompt="Skills: {{skills}}")
        result = self.renderer.render(template, {"skills": ["Python", "SQL"]})
        assert "Python" in result.text
        assert "SQL" in result.text

    def test_dict_coerced_to_json(self):
        template = _make_template(user_prompt="Data: {{data}}")
        result = self.renderer.render(
            template, {"data": {"key": "value"}}
        )
        assert "key" in result.text
        assert "value" in result.text

    def test_bool_coerced_to_string(self):
        template = _make_template(user_prompt="Flag: {{flag}}")
        result = self.renderer.render(template, {"flag": True})
        assert result.text == "Flag: True"


# ============================================================================
# Large Value Truncation
# ============================================================================

class TestTruncation:
    """Tests for large variable value handling."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_large_value_truncated(self):
        """Values > 50KB should be truncated."""
        template = _make_template(user_prompt="Text: {{content}}")
        large_text = "x" * (60 * 1024)  # 60KB
        result = self.renderer.render(template, {"content": large_text})
        assert "truncated" in result.text.lower()
        assert len(result.text) < len(large_text)

    def test_normal_value_not_truncated(self):
        template = _make_template(user_prompt="Text: {{content}}")
        result = self.renderer.render(template, {"content": "short text"})
        assert "truncated" not in result.text.lower()


# ============================================================================
# Sanitization
# ============================================================================

class TestSanitization:
    """Tests for variable value sanitization."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_null_bytes_stripped(self):
        template = _make_template(user_prompt="{{val}}")
        result = self.renderer.render(template, {"val": "hello\x00world"})
        assert "\x00" not in result.text

    def test_newlines_preserved(self):
        template = _make_template(user_prompt="{{val}}")
        result = self.renderer.render(template, {"val": "line1\nline2"})
        assert "line1\nline2" in result.text

    def test_unicode_preserved(self):
        template = _make_template(user_prompt="{{val}}")
        result = self.renderer.render(template, {"val": "日本語テスト"})
        assert "日本語テスト" in result.text

    def test_code_block_preserved(self):
        template = _make_template(user_prompt="{{code}}")
        code = "def foo():\n    return 42"
        result = self.renderer.render(template, {"code": code})
        assert code in result.text


# ============================================================================
# Realistic Agent Templates
# ============================================================================

class TestQuestionGenerationTemplate:
    """Test with realistic question generation agent variables."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_full_question_generation_render(self):
        template = _make_template(
            user_prompt=(
                "Role: {{role}}\n"
                "Topic: {{topic}}\n"
                "Subtopic: {{subtopic}}\n"
                "Difficulty: {{difficulty}}\n"
                "Remaining Time: {{remaining_time_minutes}} minutes\n"
                "Exchange: {{exchange_number}} of {{total_exchanges}}\n"
                "Candidate Context:\n{{candidate_context}}\n"
                "Last Score: {{last_score_percent}}%\n"
                "Trend: {{performance_trend}}\n"
                "Previously Asked:\n{{previously_asked}}\n"
                "Rubric:\n{{rubric_dimensions}}\n"
            ),
            system_prompt="You are an expert interviewer.",
            prompt_type="question_generation",
            model_config={"temperature": 0.7, "max_tokens": 1500},
        )

        variables = {
            "role": "Backend Engineer",
            "topic": "Databases",
            "subtopic": "SQL Joins",
            "difficulty": "medium",
            "remaining_time_minutes": 25,
            "exchange_number": 3,
            "total_exchanges": 8,
            "candidate_context": "3 years Python, familiar with PostgreSQL",
            "last_score_percent": 72,
            "performance_trend": "improving",
            "previously_asked": "1. What is a primary key?\n2. Explain normalization.",
            "rubric_dimensions": '[{"name": "correctness", "max_score": 10}]',
        }

        result = self.renderer.render(template, variables)
        assert "Backend Engineer" in result.text
        assert "SQL Joins" in result.text
        assert "medium" in result.text
        assert "25 minutes" in result.text
        assert result.version == 1
        assert result.prompt_type == "question_generation"
        assert len(result.variables_used) == 12


class TestEvaluationTemplate:
    """Test with realistic evaluation agent variables."""

    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_full_evaluation_render(self):
        template = _make_template(
            user_prompt=(
                "Question:\n{{question_text}}\n\n"
                "Response:\n{{candidate_response}}\n\n"
                "Difficulty: {{difficulty}}\n"
                "Skill: {{skill_tag}}\n"
                "Type: {{question_type}}\n"
                "Rubric:\n{{rubric_dimensions}}\n"
                "Instructions:\n{{evaluation_instructions}}\n"
            ),
            system_prompt="You are an objective evaluator.",
            prompt_type="evaluation",
            model_config={"temperature": 0.0, "max_tokens": 2000, "deterministic": True},
        )

        variables = {
            "question_text": "Explain the difference between INNER JOIN and LEFT JOIN.",
            "candidate_response": (
                "INNER JOIN returns only matching rows from both tables. "
                "LEFT JOIN returns all rows from the left table and matching "
                "rows from the right table, with NULL for non-matches."
            ),
            "difficulty": "medium",
            "skill_tag": "sql_joins",
            "question_type": "technical",
            "rubric_dimensions": [
                {"name": "correctness", "criteria": "Factual accuracy", "max_score": 10},
                {"name": "completeness", "criteria": "Covers all aspects", "max_score": 5},
            ],
            "evaluation_instructions": "Score each dimension independently.",
        }

        result = self.renderer.render(template, variables)
        assert "INNER JOIN" in result.text
        assert "LEFT JOIN" in result.text
        assert result.temperature == 0.0
        assert result.model_config.get("deterministic") is True
        assert result.prompt_type == "evaluation"
