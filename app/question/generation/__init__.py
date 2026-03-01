"""
Question Generation Module — AI-Powered Question Creation

Generates interview questions via LLM when retrieval fails or
when the template requires dynamic, context-aware generation.

Responsibilities:
- LLM-based question creation with structured output enforcement
- Post-generation validation (similarity, difficulty, topic, substance)
- Source tracking and audit metadata
- Fallback to cached generic questions on failure
- Cost tracking for LLM usage

Public API:
- QuestionGenerationService: Main orchestrator
- GenerationRequest, GenerationResult: DTOs
- GeneratedQuestionOutput, GenerationMetadata: Domain entities

Consumes:
- app.ai.llm (BaseLLMProvider, LLMRequest, LLMResponse)
- app.ai.prompts (PromptService, RenderedPrompt)
- app.question.retrieval (similarity checking)

Invariants:
- Returns QuestionSnapshot; does NOT persist exchanges
- Does NOT orchestrate interviews
- Does NOT mutate templates or submissions
- Template snapshot read from submission (frozen, never re-resolved)
"""

from .contracts import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
)
from .domain.entities import (
    GeneratedQuestionOutput,
    GenerationMetadata,
    ValidationResult,
)
from .service import QuestionGenerationService

__all__ = [
    # Service
    "QuestionGenerationService",
    # Contracts
    "GenerationRequest",
    "GenerationResult",
    "GenerationStatus",
    # Domain
    "GeneratedQuestionOutput",
    "GenerationMetadata",
    "ValidationResult",
]
