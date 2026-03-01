"""
Question State Machine — Exchange Lifecycle States

Pure domain logic — no I/O, no framework dependencies.

State diagram::

    ASKED → WAITING_INPUT →┬→ CLARIFICATION_REQUESTED →┐
                           │                            │
                           │  (loop up to 3 times)      │
                           │← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
                           │
                           ├→ ANSWER_SUBMITTED → POST_ANSWER_WINDOW → EVALUATED → NEXT_QUESTION
                           │
                           └→ AUTO_SKIPPED (clarification limit exceeded)
                                    ↓
                              ANSWER_SUBMITTED → ...
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

from app.interview.exchanges.errors import InvalidExchangeStateTransitionError
from app.interview.exchanges.intent_classifier import UtteranceIntentClassification


class ExchangeState(str, enum.Enum):
    """All valid states in the exchange lifecycle."""

    ASKED = "ASKED"
    """Question presented to candidate."""

    WAITING_INPUT = "WAITING_INPUT"
    """Listening for candidate response."""

    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    """Candidate requested clarification; generating response."""

    ANSWER_SUBMITTED = "ANSWER_SUBMITTED"
    """Response received and recorded."""

    POST_ANSWER_WINDOW = "POST_ANSWER_WINDOW"
    """5–10 second window after answer; speech recorded but not scored."""

    EVALUATED = "EVALUATED"
    """Exchange immutably persisted and evaluation complete or pending."""

    NEXT_QUESTION = "NEXT_QUESTION"
    """Terminal: prepare next question or end interview."""


# ════════════════════════════════════════════════════════════════════════
# Transition table
# ════════════════════════════════════════════════════════════════════════

_ALLOWED_TRANSITIONS: Dict[ExchangeState, FrozenSet[ExchangeState]] = {
    ExchangeState.ASKED: frozenset({
        ExchangeState.WAITING_INPUT,
    }),
    ExchangeState.WAITING_INPUT: frozenset({
        ExchangeState.CLARIFICATION_REQUESTED,
        ExchangeState.ANSWER_SUBMITTED,
    }),
    ExchangeState.CLARIFICATION_REQUESTED: frozenset({
        ExchangeState.WAITING_INPUT,  # loop back after clarification given
        ExchangeState.ANSWER_SUBMITTED,  # auto-skip if limit exceeded
    }),
    ExchangeState.ANSWER_SUBMITTED: frozenset({
        ExchangeState.POST_ANSWER_WINDOW,
        ExchangeState.EVALUATED,  # skip post-answer window if not applicable
    }),
    ExchangeState.POST_ANSWER_WINDOW: frozenset({
        ExchangeState.EVALUATED,
    }),
    ExchangeState.EVALUATED: frozenset({
        ExchangeState.NEXT_QUESTION,
    }),
    ExchangeState.NEXT_QUESTION: frozenset(),  # terminal
}


def validate_exchange_transition(current: ExchangeState, target: ExchangeState) -> None:
    """
    Validate that *current → target* is a legal state transition.

    Raises:
        InvalidExchangeStateTransitionError: If the transition is not allowed.
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidExchangeStateTransitionError(
            current_state=current.value,
            target_state=target.value,
        )


# ════════════════════════════════════════════════════════════════════════
# State Machine
# ════════════════════════════════════════════════════════════════════════


@dataclass
class QuestionStateMachine:
    """
    Tracks the lifecycle state of a single exchange/question.

    This is an in-memory state tracker used during the interview flow.
    State is NOT persisted to DB — the exchange record is only created
    after ANSWER_SUBMITTED, at which point it's immutable.

    Attributes:
        exchange_id: Optional exchange ID (set after creation).
        current_state: Current lifecycle state.
        clarification_count: Number of clarifications requested (max 3).
        clarification_limit_exceeded: True if limit reached.
        intent_sequence: Ordered list of all intent classifications.
        response_locked: True after ANSWER_SUBMITTED.
    """

    exchange_id: Optional[int] = None
    current_state: ExchangeState = ExchangeState.ASKED
    clarification_count: int = 0
    clarification_limit_exceeded: bool = False
    intent_sequence: List[UtteranceIntentClassification] = field(default_factory=list)
    response_locked: bool = False

    MAX_CLARIFICATIONS: int = 3

    def transition_to(self, target: ExchangeState) -> None:
        """
        Transition to a new state.

        Validates the transition is allowed, then updates state.
        Also updates derived flags (response_locked, etc.).

        Args:
            target: Target state.

        Raises:
            InvalidExchangeStateTransitionError: If transition is not allowed.
        """
        validate_exchange_transition(self.current_state, target)
        self.current_state = target

        # Update derived flags
        if target == ExchangeState.ANSWER_SUBMITTED:
            self.response_locked = True

    def record_intent(self, classification: UtteranceIntentClassification) -> None:
        """Record an intent classification in the audit sequence."""
        self.intent_sequence.append(classification)

    def request_clarification(self) -> bool:
        """
        Process a clarification request.

        Increments clarification count and transitions state.
        If limit exceeded, auto-transitions to ANSWER_SUBMITTED.

        Returns:
            True if clarification was granted, False if limit exceeded.

        Raises:
            InvalidExchangeStateTransitionError: If not in WAITING_INPUT state.
        """
        if self.clarification_count >= self.MAX_CLARIFICATIONS:
            self.clarification_limit_exceeded = True
            # Auto-skip: transition directly to ANSWER_SUBMITTED
            self.transition_to(ExchangeState.ANSWER_SUBMITTED)
            return False

        self.clarification_count += 1
        self.transition_to(ExchangeState.CLARIFICATION_REQUESTED)
        return True

    def provide_clarification_response(self) -> None:
        """
        After clarification response is generated, transition back to WAITING_INPUT.

        Raises:
            InvalidExchangeStateTransitionError: If not in CLARIFICATION_REQUESTED.
        """
        self.transition_to(ExchangeState.WAITING_INPUT)

    def submit_answer(self) -> None:
        """
        Transition to ANSWER_SUBMITTED.

        Raises:
            InvalidExchangeStateTransitionError: If not in WAITING_INPUT
                or CLARIFICATION_REQUESTED.
        """
        self.transition_to(ExchangeState.ANSWER_SUBMITTED)

    @property
    def last_intent(self) -> Optional[UtteranceIntentClassification]:
        """Most recent intent classification, or None."""
        return self.intent_sequence[-1] if self.intent_sequence else None

    def to_snapshot_dict(self) -> dict:
        """
        Serialize state for content_metadata JSONB storage.

        Used when creating the immutable exchange record.
        """
        return {
            "clarification_count": self.clarification_count,
            "clarification_limit_exceeded": self.clarification_limit_exceeded,
            "intent_sequence": [ic.to_audit_dict() for ic in self.intent_sequence],
            "final_intent": self.last_intent.intent.value if self.last_intent else None,
            "final_intent_confidence": (
                self.last_intent.confidence if self.last_intent else None
            ),
        }
