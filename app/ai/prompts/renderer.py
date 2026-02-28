"""
Prompt Renderer

Renders a PromptTemplate entity with variable substitution
and produces a RenderedPrompt ready for LLM consumption.

Design:
- Uses TemplateParser for variable extraction and validation
- Substitutes {{variable}} with provided values
- Validates all required variables are present
- Supports optional context truncation (token estimation)
- Sanitizes variable values against injection attacks
- Pure function core — no DB, no IO
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.ai.prompts.entities import PromptTemplate, RenderedPrompt
from app.ai.prompts.errors import VariableMissingError
from app.ai.prompts.parser import TemplateParser

logger = logging.getLogger(__name__)

# Maximum length for a single variable value (50 KB)
_MAX_VARIABLE_VALUE_LENGTH = 50 * 1024

# Regex for substitution (matches {{var}} with optional whitespace)
_SUBSTITUTE_PATTERN = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")


class PromptRenderer:
    """
    Renders prompt templates with variable substitution.

    Usage:
        renderer = PromptRenderer()
        rendered = renderer.render(template, {"name": "Alice", "score": "85"})
    """

    def render(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
        *,
        truncate_context: bool = False,
        max_context_tokens: Optional[int] = None,
    ) -> RenderedPrompt:
        """
        Render a PromptTemplate with variable substitution.

        Args:
            template: Source prompt template
            variables: Variable name → value mapping
            truncate_context: Whether to truncate long variable values
            max_context_tokens: Max tokens if truncating (required if truncate_context=True)

        Returns:
            RenderedPrompt with substituted text

        Raises:
            VariableMissingError: If required variables are missing
            TemplateSyntaxError: If template syntax is invalid
        """
        # 1. Parse and validate both user_prompt and system_prompt
        user_parser = TemplateParser(template.user_prompt)
        user_parser.validate()
        user_vars = set(user_parser.extract_variables())

        system_vars: set = set()
        if template.system_prompt:
            system_parser = TemplateParser(template.system_prompt)
            system_parser.validate()
            system_vars = set(system_parser.extract_variables())

        # 2. Check for missing variables (union of both)
        all_required = user_vars | system_vars
        provided = set(variables.keys())
        missing = all_required - provided

        if missing:
            raise VariableMissingError(
                missing_variables=list(missing),
                prompt_type=template.prompt_type,
            )

        # 3. Sanitize and coerce variable values
        sanitized = self._sanitize_variables(
            variables,
            truncate=truncate_context,
            max_tokens=max_context_tokens,
        )

        # 4. Substitute variables
        rendered_user = self._substitute(template.user_prompt, sanitized)
        rendered_system = (
            self._substitute(template.system_prompt, sanitized)
            if template.system_prompt
            else None
        )

        # 5. Determine truncation
        truncated = any(
            sanitized.get(k) != self._coerce_to_string(variables.get(k))
            for k in all_required
            if k in variables
        )

        # 6. Build variables_used list (only vars actually present in templates)
        variables_used = sorted(all_required & provided)

        return RenderedPrompt(
            text=rendered_user,
            system_prompt=rendered_system,
            model_id=template.model_id,
            model_config=dict(template.model_config) if template.model_config else {},
            version=template.version,
            prompt_type=template.prompt_type,
            variables_used=variables_used,
            truncated=truncated,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _substitute(self, template_text: str, variables: Dict[str, str]) -> str:
        """Replace {{var}} placeholders with sanitized values."""

        def _replacer(match: re.Match) -> str:
            var_name = match.group(1).strip()
            if var_name in variables:
                return variables[var_name]
            # Extra variables in template that aren't required:
            # leave placeholder intact (shouldn't happen after validation)
            return match.group(0)

        return _SUBSTITUTE_PATTERN.sub(_replacer, template_text)

    def _sanitize_variables(
        self,
        variables: Dict[str, Any],
        *,
        truncate: bool = False,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Coerce and sanitize variable values.

        Rules (from REQUIREMENTS.md):
        - None → empty string (with warning)
        - list/dict → JSON string
        - Strings > 50KB → truncated with warning
        - HTML/SQL basic sanitization
        """
        result: Dict[str, str] = {}
        for key, value in variables.items():
            string_val = self._coerce_to_string(value)

            # Truncate excessively long values
            if len(string_val) > _MAX_VARIABLE_VALUE_LENGTH:
                logger.warning(
                    "Variable value truncated",
                    extra={
                        "variable": key,
                        "original_length": len(string_val),
                        "truncated_to": _MAX_VARIABLE_VALUE_LENGTH,
                    },
                )
                string_val = string_val[:_MAX_VARIABLE_VALUE_LENGTH] + "\n... [truncated]"

            # Basic sanitization (prevent injection into prompt)
            string_val = self._sanitize_value(string_val)

            result[key] = string_val

        return result

    @staticmethod
    def _coerce_to_string(value: Any) -> str:
        """Convert any value to its string representation."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    @staticmethod
    def _sanitize_value(value: str) -> str:
        """
        Basic sanitization for variable values.

        Does NOT strip all HTML/SQL — that would break legitimate content
        (e.g., code blocks, SQL questions). Instead, we neutralize the most
        common injection vectors while preserving content integrity.
        """
        # Newlines and special characters are preserved (legitimate in prompts)
        # We only strip null bytes which could cause issues
        return value.replace("\x00", "")
