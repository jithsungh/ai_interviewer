"""
Template Parser

Extracts and validates {{variable}} placeholders from prompt templates.

Design:
- Uses regex to find all {{variable}} patterns
- Validates syntax (no nested vars, no unclosed braces, no empty names)
- Strips whitespace from variable names ({{ name }} → name)
- Supports escaped braces (\\{{ and \\}})
- Pure function — no DB, no IO

Syntax:
- {{variable_name}}         → Variable placeholder
- {{ variable_name }}       → Whitespace stripped
- \\{{ literal \\}}         → Escaped, treated as literal text

Not supported:
- {{user_{{type}}}}         → Nested variables (raises TemplateSyntaxError)
- {{}}                      → Empty variable name (raises TemplateSyntaxError)
"""

from __future__ import annotations

import re
from typing import List, Set

from app.ai.prompts.errors import TemplateSyntaxError

# Matches {{variable}} with optional whitespace inside
_VARIABLE_PATTERN = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")

# Matches escaped braces \\{{ and \\}}
_ESCAPED_OPEN = re.compile(r"\\\{\{")
_ESCAPED_CLOSE = re.compile(r"\\\}\}")

# Detects nested variable attempts: {{ ... {{ ... }} ... }}
_NESTED_PATTERN = re.compile(r"\{\{[^}]*\{\{")

# Detects unclosed {{ without matching }}
_UNCLOSED_OPEN = re.compile(r"\{\{(?!.*\}\})")


class TemplateParser:
    """
    Parses and validates prompt templates with {{variable}} syntax.

    Usage:
        parser = TemplateParser("Hello {{name}}, your score is {{score}}")
        parser.validate()
        variables = parser.extract_variables()
        # → {'name', 'score'}
    """

    def __init__(self, template: str) -> None:
        if template is None:
            raise TemplateSyntaxError("Template cannot be None")
        self._template = template

    @property
    def template(self) -> str:
        return self._template

    def validate(self) -> None:
        """
        Validate template syntax.

        Raises:
            TemplateSyntaxError: On invalid syntax
        """
        # Remove escaped braces before validation
        cleaned = self._remove_escaped(self._template)

        # Check for nested variables
        match = _NESTED_PATTERN.search(cleaned)
        if match:
            raise TemplateSyntaxError(
                "Nested variable references are not supported",
                position=match.start(),
                template_snippet=cleaned[match.start(): match.start() + 40],
            )

        # Check for empty variable names: {{}} or {{  }}
        for m in _VARIABLE_PATTERN.finditer(cleaned):
            var_name = m.group(1).strip()
            if not var_name:
                raise TemplateSyntaxError(
                    "Empty variable name",
                    position=m.start(),
                    template_snippet=cleaned[m.start(): m.start() + 10],
                )

        # Check for unclosed {{ that have no matching }}
        # Count opens and closes in cleaned text (after removing valid vars)
        remaining = _VARIABLE_PATTERN.sub("", cleaned)
        open_count = remaining.count("{{")
        close_count = remaining.count("}}")

        if open_count > 0:
            idx = remaining.index("{{")
            raise TemplateSyntaxError(
                "Unclosed '{{' without matching '}}'",
                position=idx,
                template_snippet=remaining[idx: idx + 30],
            )
        if close_count > 0:
            idx = remaining.index("}}")
            raise TemplateSyntaxError(
                "Unmatched '}}' without opening '{{'",
                position=idx,
                template_snippet=remaining[max(0, idx - 10): idx + 10],
            )

    def extract_variables(self) -> List[str]:
        """
        Extract all unique variable names from the template.

        Strips whitespace from names. Skips escaped braces.

        Returns:
            Sorted list of unique variable names
        """
        cleaned = self._remove_escaped(self._template)
        seen: Set[str] = set()
        result: List[str] = []
        for match in _VARIABLE_PATTERN.finditer(cleaned):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return sorted(result)

    def _remove_escaped(self, text: str) -> str:
        """Replace escaped braces with placeholders so they don't trigger validation."""
        result = _ESCAPED_OPEN.sub("\x00OPEN\x00", text)
        result = _ESCAPED_CLOSE.sub("\x00CLOSE\x00", result)
        return result
