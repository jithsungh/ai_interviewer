"""
Question Prompting — LLM Context Assembly

Structured prompt composition for LLM question generation.
Handles context injection, token budget management, prompt injection
prevention, and template versioning.

Public API:
- QuestionPromptAssembler: Main entry point for prompt assembly
- PromptAssemblyResult: Output DTO
- PromptConfig: Configuration dataclass
- TokenEstimator: Token budget utilities
- sanitize_text: Input sanitization
- detect_prompt_injection: Injection pattern detection

Delegates to ``app.ai.prompts`` for template loading, parsing, and rendering.

Architectural Invariants:
- Prompts ALWAYS loaded from ``prompt_templates`` table (no hardcoded prompts)
- Candidate-provided text is ALWAYS sanitized before injection into prompts
- Token budget is ALWAYS checked before sending to LLM
- Context is prioritized: essential first, optional if fits
"""

from app.question.prompting.assembler import (
    QuestionPromptAssembler,
    PromptAssemblyResult,
)
from app.question.prompting.config import PromptConfig
from app.question.prompting.context import (
    ContextPiece,
    prioritize_context,
)
from app.question.prompting.safety import (
    sanitize_text,
    detect_prompt_injection,
    PromptInjectionError,
)
from app.question.prompting.tokens import TokenEstimator

__all__ = [
    # Assembler
    "QuestionPromptAssembler",
    "PromptAssemblyResult",
    # Config
    "PromptConfig",
    # Context
    "ContextPiece",
    "prioritize_context",
    # Safety
    "sanitize_text",
    "detect_prompt_injection",
    "PromptInjectionError",
    # Tokens
    "TokenEstimator",
]
