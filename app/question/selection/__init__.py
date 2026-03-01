"""
Question Selection Module — Rule-Based Filtering & Adaptive Difficulty

Provides:
- Deterministic next question selection based on template structure
- Adaptive difficulty progression based on candidate performance (FR-3.2, FR-4.3)
- Repetition prevention via embedding similarity (FR-4.5)
- Topic and constraint filtering
- Fallback strategies when no match found
- Adaptation decision logging (FR-4.4)

Public API:
- QuestionSelectionService: Main orchestrator
- SelectionContext, SelectionResult, QuestionSnapshot: DTOs
- AdaptationDecision: Audit record
- adapt_difficulty: Pure difficulty logic

Consumed by: interview module.

Invariants:
- Returns QuestionSnapshot; does NOT persist exchanges
- Does NOT orchestrate interviews
- Template snapshot read from submission (frozen, never re-resolved)
- Stateless — safe for concurrent calls
"""

from .contracts import (
    AdaptationDecision,
    CandidateProfile,
    DifficultyAdaptationConfig,
    ExchangeHistoryEntry,
    FallbackType,
    QuestionSnapshot,
    RepetitionConfig,
    SectionConfig,
    SelectionContext,
    SelectionResult,
    SelectionStrategy,
)
from .domain.difficulty import (
    adapt_difficulty,
    build_adaptation_decision,
    decrease_difficulty,
    increase_difficulty,
)
from .domain.template_parser import (
    SectionCompleteError,
    TemplateSnapshotError,
    find_section,
    parse_adaptation_config,
    validate_template_snapshot,
)
from .domain.repetition import (
    check_repetition,
    is_exact_match,
)
from .domain.fallback import (
    FallbackLevel,
    get_fallback_type,
    get_relaxed_difficulties,
)
from .service import (
    NoQuestionAvailableError,
    QuestionSelectionService,
)

__all__ = [
    # Service
    "QuestionSelectionService",
    "NoQuestionAvailableError",
    # Contracts
    "SelectionContext",
    "SelectionResult",
    "QuestionSnapshot",
    "AdaptationDecision",
    "DifficultyAdaptationConfig",
    "RepetitionConfig",
    "SectionConfig",
    "ExchangeHistoryEntry",
    "CandidateProfile",
    "SelectionStrategy",
    "FallbackType",
    # Domain — Difficulty
    "adapt_difficulty",
    "build_adaptation_decision",
    "increase_difficulty",
    "decrease_difficulty",
    # Domain — Template
    "TemplateSnapshotError",
    "SectionCompleteError",
    "find_section",
    "validate_template_snapshot",
    "parse_adaptation_config",
    # Domain — Repetition
    "check_repetition",
    "is_exact_match",
    # Domain — Fallback
    "FallbackLevel",
    "get_fallback_type",
    "get_relaxed_difficulties",
]
