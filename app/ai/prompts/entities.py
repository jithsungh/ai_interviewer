"""
Prompt Domain Entities

Pure data classes for the prompt template domain.
No database coupling — transport-neutral business objects.

Maps to prompt_templates table in schema.sql.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PromptType(str, Enum):
    """
    Supported prompt types.

    Maps to prompt_templates.prompt_type column.
    """
    QUESTION_GENERATION = "question_generation"
    EVALUATION = "evaluation"
    RESUME_PARSING = "resume_parsing"
    JD_PARSING = "jd_parsing"
    REPORT_GENERATION = "report_generation"
    CLARIFICATION = "clarification"


@dataclass
class PromptTemplate:
    """
    Versioned prompt template definition.

    Maps to: public.prompt_templates table.

    Scope rules:
    - scope='public' + organization_id=1  → Global (visible to all orgs)
    - scope='organization' + org_id=X     → Organization-scoped (visible only to org X)
    - scope='private'                     → Private (visible only to creator)

    Invariants:
    - Only ONE active version per (prompt_type, organization_id) pair
    - Version numbers increment monotonically
    - Prompts layer is READ-ONLY — admin module manages writes
    """
    id: Optional[int]
    name: str
    prompt_type: str
    scope: str  # 'public' | 'organization' | 'private' — uses template_scope enum
    organization_id: Optional[int]
    system_prompt: str
    user_prompt: str
    model_id: Optional[int]
    model_config: Dict[str, Any]
    version: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def temperature(self) -> Optional[float]:
        """Extract temperature from model_config if present."""
        return self.model_config.get("temperature")

    @property
    def max_tokens(self) -> Optional[int]:
        """Extract max_tokens from model_config if present."""
        return self.model_config.get("max_tokens")

    @property
    def is_global(self) -> bool:
        """Whether this is a global (public) prompt template."""
        return self.scope == "public"


@dataclass
class RenderedPrompt:
    """
    Result of rendering a PromptTemplate with variable substitution.

    Returned by PromptRenderer after applying variables to template.
    Contains everything needed to make an LLM call.
    """
    text: str                                   # Rendered user prompt
    system_prompt: Optional[str] = None         # Rendered system prompt
    model_id: Optional[int] = None              # Suggested model FK
    model_config: Dict[str, Any] = field(default_factory=dict)
    version: int = 0                            # Prompt version used
    prompt_type: str = ""                       # Type of prompt rendered
    variables_used: List[str] = field(default_factory=list)
    truncated: bool = False                     # Whether content was truncated

    @property
    def temperature(self) -> Optional[float]:
        """Extract temperature from model_config."""
        return self.model_config.get("temperature")

    @property
    def max_tokens(self) -> Optional[int]:
        """Extract max_tokens from model_config."""
        return self.model_config.get("max_tokens")
