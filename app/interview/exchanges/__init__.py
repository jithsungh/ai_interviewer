"""
Interview Exchanges — Immutable Exchange Creation & Snapshot Persistence

This module is the immutability enforcement boundary for interview exchanges.
Exchanges are created ONCE with complete snapshot data and NEVER modified.

Public API:
- Repository: InterviewExchangeRepository (create + read only)
- Contracts: ExchangeCreationData, ContentMetadata
- Validators: validate_sequence_order, validate_response_completeness
- State Machine: QuestionStateMachine, ExchangeState
- Intent Classifier: UtteranceIntentClassifier, UtteranceIntentClassification
- Clarification Policy: ClarificationPolicy, ClarificationRequest, ClarificationResponse
- Errors: SequenceGapError, DuplicateSequenceError, IncompleteResponseError, etc.

Architectural Invariants:
- Exchanges are IMMUTABLE after creation
- Exchanges are SNAPSHOTS (copy data, don't reference)
- Exchanges are SEQUENCED (no gaps, no duplicates)
- One exchange = one evaluation
"""

from app.interview.exchanges.repository import InterviewExchangeRepository
from app.interview.exchanges.contracts import ExchangeCreationData, ContentMetadata
from app.interview.exchanges.validators import (
    validate_sequence_order,
    validate_response_completeness,
)
from app.interview.exchanges.question_state_machine import (
    ExchangeState,
    QuestionStateMachine,
)
from app.interview.exchanges.intent_classifier import (
    UtteranceIntent,
    SemanticLevel,
    UtteranceIntentClassification,
    UtteranceIntentClassifier,
)
from app.interview.exchanges.clarification_policy import (
    ClarificationPolicy,
    ClarificationRequest,
    ClarificationResponse,
    CLARIFICATION_PROMPT_CONSTRAINTS,
)
from app.interview.exchanges.errors import (
    SequenceGapError,
    DuplicateSequenceError,
    IncompleteResponseError,
    ClassificationError,
    ClarificationLimitExceededError,
    InvalidExchangeStateTransitionError,
)

__all__ = [
    # Repository
    "InterviewExchangeRepository",
    # Contracts
    "ExchangeCreationData",
    "ContentMetadata",
    # Validators
    "validate_sequence_order",
    "validate_response_completeness",
    # State Machine
    "ExchangeState",
    "QuestionStateMachine",
    # Intent Classification
    "UtteranceIntent",
    "SemanticLevel",
    "UtteranceIntentClassification",
    "UtteranceIntentClassifier",
    # Clarification Policy
    "ClarificationPolicy",
    "ClarificationRequest",
    "ClarificationResponse",
    "CLARIFICATION_PROMPT_CONSTRAINTS",
    # Errors
    "SequenceGapError",
    "DuplicateSequenceError",
    "IncompleteResponseError",
    "ClassificationError",
    "ClarificationLimitExceededError",
    "InvalidExchangeStateTransitionError",
]
