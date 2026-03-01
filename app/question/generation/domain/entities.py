"""
Generation Domain Entities

Pure data classes with no DB or framework coupling.
Used internally by the generation domain layer and returned
to callers (selection module, service orchestrator).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GeneratedQuestionOutput:
    """
    Parsed and validated output from LLM generation.

    Created by parsing the JSON response from the LLM.
    Validated before being promoted to a GenerationResult.
    """

    question_text: str
    expected_answer: str
    difficulty: str
    topic: str
    subtopic: Optional[str] = None
    skill_tags: List[str] = field(default_factory=list)
    expected_answer_type: Optional[str] = None
    estimated_time_seconds: int = 120
    followup_suggestions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    """
    Outcome of post-generation validation checks.

    Aggregates all check results so retry logic can decide
    whether to accept or reject the generated question.
    """

    passed: bool
    failures: List[str] = field(default_factory=list)
    similarity_score: float = 0.0
    difficulty_match: bool = True
    topic_allowed: bool = True
    not_empty: bool = True

    @property
    def failure_summary(self) -> str:
        return "; ".join(self.failures) if self.failures else "none"


@dataclass(frozen=True)
class GenerationMetadata:
    """
    Audit metadata for a single generation attempt.

    Stored in the question snapshot JSONB for full traceability.
    """

    source_type: str  # "generated" | "fallback_generic"
    prompt_hash: str  # SHA-256 of system_prompt + user_prompt
    llm_model: str
    llm_provider: str
    llm_temperature: Optional[float]
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    generated_at: datetime
    validation_passed: bool
    validation_failures: List[str]
    similarity_score: float
    prompt_version: Optional[int]
    attempts: int
    total_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for JSONB storage."""
        return {
            "source_type": self.source_type,
            "prompt_hash": self.prompt_hash,
            "llm_model": self.llm_model,
            "llm_provider": self.llm_provider,
            "llm_temperature": self.llm_temperature,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "generated_at": self.generated_at.isoformat(),
            "validation_passed": self.validation_passed,
            "validation_failures": self.validation_failures,
            "similarity_score": self.similarity_score,
            "prompt_version": self.prompt_version,
            "attempts": self.attempts,
            "total_latency_ms": self.total_latency_ms,
        }
