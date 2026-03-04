"""
Prompting Configuration

Pydantic-free config dataclass for prompt assembly settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# Default prompt injection patterns to detect.
DEFAULT_INJECTION_PATTERNS: List[str] = [
    r"ignore\s+(previous|all|the)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(previous|all|the)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+now\s+\w+",
    r"new\s+instructions?\s+follow",
    r"forget\s+(everything|all|previous)",
    r"system\s*:\s*",
    r"assistant\s*:\s*",
]


@dataclass(frozen=True)
class PromptConfig:
    """
    Configuration for prompt assembly.

    Defaults are tuned for GPT-4 class models but callers can override.
    """

    # Template type key used to look up prompt templates.
    prompt_type: str = "question_generation"

    # Token budget
    max_context_tokens: int = 7500
    llm_max_output_tokens: int = 500
    safety_margin_tokens: int = 192

    # Truncation
    truncate_strategy: str = "tail"  # 'tail' → remove from end

    # Safety
    enable_injection_detection: bool = True
    injection_patterns: List[str] = field(
        default_factory=lambda: list(DEFAULT_INJECTION_PATTERNS),
    )
    enable_sanitization: bool = True

    # Token estimation
    token_model: str = "gpt-4"

    # Context limits
    max_previous_exchanges: int = 5
    max_resume_chars: int = 50_000  # ~12 500 tokens
    max_jd_chars: int = 20_000

    @property
    def available_context_tokens(self) -> int:
        """Tokens available for context (model max minus output + safety)."""
        return self.max_context_tokens - self.llm_max_output_tokens - self.safety_margin_tokens
