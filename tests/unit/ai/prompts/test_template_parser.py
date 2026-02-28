"""
Unit Tests — Template Parser

Tests for app.ai.prompts.parser.TemplateParser:
- Variable extraction
- Syntax validation
- Edge cases (escaped braces, whitespace, empty names, nested vars)
"""

import pytest
from app.ai.prompts.parser import TemplateParser
from app.ai.prompts.errors import TemplateSyntaxError


# ============================================================================
# Variable Extraction
# ============================================================================

class TestExtractVariables:
    """Tests for TemplateParser.extract_variables()"""

    def test_simple_variables(self):
        parser = TemplateParser("Hello {{name}}, your score is {{score}}")
        variables = parser.extract_variables()
        assert variables == ["name", "score"]

    def test_single_variable(self):
        parser = TemplateParser("Welcome {{user}}")
        assert parser.extract_variables() == ["user"]

    def test_no_variables(self):
        parser = TemplateParser("Plain text with no variables")
        assert parser.extract_variables() == []

    def test_duplicate_variables_deduplicated(self):
        parser = TemplateParser("{{name}} said hello to {{name}}")
        assert parser.extract_variables() == ["name"]

    def test_whitespace_stripped(self):
        parser = TemplateParser("{{ name }} and {{  score  }}")
        assert parser.extract_variables() == ["name", "score"]

    def test_variables_sorted_alphabetically(self):
        parser = TemplateParser("{{zebra}} {{apple}} {{mango}}")
        assert parser.extract_variables() == ["apple", "mango", "zebra"]

    def test_underscore_variables(self):
        parser = TemplateParser("{{candidate_response}} and {{question_text}}")
        assert parser.extract_variables() == ["candidate_response", "question_text"]

    def test_escaped_braces_not_extracted(self):
        parser = TemplateParser("Use \\{{literal\\}} syntax and {{real_var}}")
        variables = parser.extract_variables()
        assert variables == ["real_var"]

    def test_multiline_template(self):
        template = """
Role: {{role}}
Topics: {{topics}}
Difficulty: {{difficulty}}

Previous:
{{previous_questions}}
"""
        parser = TemplateParser(template)
        assert parser.extract_variables() == [
            "difficulty", "previous_questions", "role", "topics"
        ]

    def test_empty_template(self):
        parser = TemplateParser("")
        assert parser.extract_variables() == []

    def test_variable_with_numbers(self):
        parser = TemplateParser("{{topic1}} and {{topic2}}")
        assert parser.extract_variables() == ["topic1", "topic2"]

    def test_complex_question_generation_template(self):
        """Test with a realistic question generation template."""
        template = (
            "Role: {{role}}\n"
            "Topic: {{topic}}\n"
            "Subtopic: {{subtopic}}\n"
            "Difficulty: {{difficulty}}\n"
            "Remaining Time: {{remaining_time_minutes}} minutes\n"
            "Previously Asked:\n{{previously_asked}}\n"
            "Rubric:\n{{rubric_dimensions}}\n"
        )
        parser = TemplateParser(template)
        variables = parser.extract_variables()
        assert "role" in variables
        assert "topic" in variables
        assert "rubric_dimensions" in variables
        assert len(variables) == 7


# ============================================================================
# Syntax Validation
# ============================================================================

class TestValidation:
    """Tests for TemplateParser.validate()"""

    def test_valid_template_passes(self):
        parser = TemplateParser("Hello {{name}}")
        parser.validate()  # Should not raise

    def test_plain_text_passes(self):
        parser = TemplateParser("Just plain text")
        parser.validate()  # Should not raise

    def test_empty_template_passes(self):
        parser = TemplateParser("")
        parser.validate()  # Should not raise

    def test_unclosed_brace_raises(self):
        parser = TemplateParser("Hello {{name")
        with pytest.raises(TemplateSyntaxError) as exc_info:
            parser.validate()
        assert "unclosed" in str(exc_info.value).lower() or "{{" in str(exc_info.value)

    def test_unmatched_close_raises(self):
        parser = TemplateParser("Hello name}}")
        with pytest.raises(TemplateSyntaxError) as exc_info:
            parser.validate()
        assert "}}" in str(exc_info.value)

    def test_nested_variables_rejected(self):
        parser = TemplateParser("User: {{user_{{type}}}}")
        with pytest.raises(TemplateSyntaxError) as exc_info:
            parser.validate()
        assert "nested" in str(exc_info.value).lower()

    def test_empty_variable_name_rejected(self):
        parser = TemplateParser("Hello {{}} world")
        with pytest.raises(TemplateSyntaxError):
            parser.validate()

    def test_whitespace_only_variable_rejected(self):
        parser = TemplateParser("Hello {{   }} world")
        with pytest.raises(TemplateSyntaxError):
            parser.validate()

    def test_none_template_rejected(self):
        with pytest.raises(TemplateSyntaxError):
            TemplateParser(None)

    def test_escaped_braces_valid(self):
        parser = TemplateParser("Use \\{{literal\\}} syntax")
        parser.validate()  # Should not raise

    def test_multiple_valid_variables(self):
        parser = TemplateParser("{{a}} {{b}} {{c}} {{d}}")
        parser.validate()  # Should not raise


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Edge case tests for TemplateParser"""

    def test_adjacent_variables(self):
        parser = TemplateParser("{{first}}{{second}}")
        assert parser.extract_variables() == ["first", "second"]

    def test_variable_at_start(self):
        parser = TemplateParser("{{greeting}} world")
        assert parser.extract_variables() == ["greeting"]

    def test_variable_at_end(self):
        parser = TemplateParser("Hello {{name}}")
        assert parser.extract_variables() == ["name"]

    def test_single_braces_ignored(self):
        """Single { and } should not be treated as variable delimiters."""
        parser = TemplateParser("JSON: {key: value}")
        assert parser.extract_variables() == []
        parser.validate()  # Should not raise

    def test_json_in_template(self):
        """JSON snippets in template should not confuse parser."""
        template = '{"key": "{{value}}"}'
        parser = TemplateParser(template)
        assert parser.extract_variables() == ["value"]

    def test_very_long_variable_name(self):
        long_name = "a" * 200
        parser = TemplateParser(f"{{{{{long_name}}}}}")
        assert parser.extract_variables() == [long_name]

    def test_special_chars_in_surrounding_text(self):
        parser = TemplateParser("Score: {{score}}% and <b>{{name}}</b>")
        assert parser.extract_variables() == ["name", "score"]
