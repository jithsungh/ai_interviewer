"""
AI Prompts Layer

Versioned prompt template management with scope resolution and variable interpolation.

Core responsibilities:
- Retrieve active prompt templates from prompt_templates table (read-only)
- Resolve scope priority: organization-scoped → global fallback
- Render prompts with variable interpolation ({{variable}} syntax)
- Support system/user prompt separation
- Track prompt version in telemetry

Design principle: Prompts are data, not code.
All prompts stored in database for versioning and A/B testing.
"""

from .entities import (
    PromptTemplate,
    RenderedPrompt,
    PromptType,
)

from .errors import (
    PromptNotFoundError,
    VariableMissingError,
    TemplateSyntaxError,
)

from .parser import TemplateParser

from .renderer import PromptRenderer

from .service import PromptService

__all__ = [
    # Entities
    "PromptTemplate",
    "RenderedPrompt",
    "PromptType",

    # Errors
    "PromptNotFoundError",
    "VariableMissingError",
    "TemplateSyntaxError",

    # Parser
    "TemplateParser",

    # Renderer
    "PromptRenderer",

    # Service
    "PromptService",
]
