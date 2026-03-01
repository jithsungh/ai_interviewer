"""
Unit Tests — Question State Machine

Tests the pure domain logic for exchange lifecycle state transitions.
"""

from __future__ import annotations

import pytest

from app.interview.exchanges.errors import InvalidExchangeStateTransitionError
from app.interview.exchanges.intent_classifier import (
    SemanticLevel,
    UtteranceIntent,
    UtteranceIntentClassification,
)
from app.interview.exchanges.question_state_machine import (
    ExchangeState,
    QuestionStateMachine,
    validate_exchange_transition,
)


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeState enum
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeStateEnum:
    def test_all_values_present(self):
        values = {s.value for s in ExchangeState}
        assert values == {
            "ASKED",
            "WAITING_INPUT",
            "CLARIFICATION_REQUESTED",
            "ANSWER_SUBMITTED",
            "POST_ANSWER_WINDOW",
            "EVALUATED",
            "NEXT_QUESTION",
        }

    def test_string_coercion(self):
        assert ExchangeState("ASKED") is ExchangeState.ASKED


# ═══════════════════════════════════════════════════════════════════════════
# validate_exchange_transition — allowed paths
# ═══════════════════════════════════════════════════════════════════════════


class TestAllowedExchangeTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            (ExchangeState.ASKED, ExchangeState.WAITING_INPUT),
            (ExchangeState.WAITING_INPUT, ExchangeState.CLARIFICATION_REQUESTED),
            (ExchangeState.WAITING_INPUT, ExchangeState.ANSWER_SUBMITTED),
            (ExchangeState.CLARIFICATION_REQUESTED, ExchangeState.WAITING_INPUT),
            (ExchangeState.CLARIFICATION_REQUESTED, ExchangeState.ANSWER_SUBMITTED),
            (ExchangeState.ANSWER_SUBMITTED, ExchangeState.POST_ANSWER_WINDOW),
            (ExchangeState.ANSWER_SUBMITTED, ExchangeState.EVALUATED),
            (ExchangeState.POST_ANSWER_WINDOW, ExchangeState.EVALUATED),
            (ExchangeState.EVALUATED, ExchangeState.NEXT_QUESTION),
        ],
    )
    def test_valid_transitions(self, current, target):
        validate_exchange_transition(current, target)  # no exception = pass


class TestForbiddenExchangeTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            # Backward transitions
            (ExchangeState.WAITING_INPUT, ExchangeState.ASKED),
            (ExchangeState.ANSWER_SUBMITTED, ExchangeState.WAITING_INPUT),
            (ExchangeState.EVALUATED, ExchangeState.ANSWER_SUBMITTED),
            # Skip-ahead
            (ExchangeState.ASKED, ExchangeState.ANSWER_SUBMITTED),
            (ExchangeState.ASKED, ExchangeState.EVALUATED),
            # Terminal
            (ExchangeState.NEXT_QUESTION, ExchangeState.ASKED),
            (ExchangeState.NEXT_QUESTION, ExchangeState.WAITING_INPUT),
            # Self-loops
            (ExchangeState.ASKED, ExchangeState.ASKED),
            (ExchangeState.EVALUATED, ExchangeState.EVALUATED),
        ],
    )
    def test_invalid_transitions(self, current, target):
        with pytest.raises(InvalidExchangeStateTransitionError):
            validate_exchange_transition(current, target)


# ═══════════════════════════════════════════════════════════════════════════
# QuestionStateMachine — full lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestQuestionStateMachineLifecycle:
    def test_happy_path_no_clarifications(self):
        """ASKED → WAITING → ANSWER_SUBMITTED → POST_ANSWER → EVALUATED → NEXT."""
        sm = QuestionStateMachine()
        assert sm.current_state == ExchangeState.ASKED
        assert sm.response_locked is False

        sm.transition_to(ExchangeState.WAITING_INPUT)
        assert sm.current_state == ExchangeState.WAITING_INPUT

        sm.submit_answer()
        assert sm.current_state == ExchangeState.ANSWER_SUBMITTED
        assert sm.response_locked is True

        sm.transition_to(ExchangeState.POST_ANSWER_WINDOW)
        sm.transition_to(ExchangeState.EVALUATED)
        sm.transition_to(ExchangeState.NEXT_QUESTION)
        assert sm.current_state == ExchangeState.NEXT_QUESTION

    def test_with_clarification(self):
        """One clarification then answer."""
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)

        # Request clarification
        granted = sm.request_clarification()
        assert granted is True
        assert sm.current_state == ExchangeState.CLARIFICATION_REQUESTED
        assert sm.clarification_count == 1

        # Provide clarification
        sm.provide_clarification_response()
        assert sm.current_state == ExchangeState.WAITING_INPUT

        # Now answer
        sm.submit_answer()
        assert sm.current_state == ExchangeState.ANSWER_SUBMITTED

    def test_max_clarifications_auto_skip(self):
        """After 3 clarifications, auto-skip to ANSWER_SUBMITTED."""
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)

        # Exhaust clarifications
        for i in range(3):
            granted = sm.request_clarification()
            assert granted is True
            sm.provide_clarification_response()

        # Fourth request → auto-skip
        granted = sm.request_clarification()
        assert granted is False
        assert sm.clarification_limit_exceeded is True
        assert sm.current_state == ExchangeState.ANSWER_SUBMITTED

    def test_clarification_count_tracks(self):
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)

        sm.request_clarification()
        assert sm.clarification_count == 1
        sm.provide_clarification_response()

        sm.request_clarification()
        assert sm.clarification_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# QuestionStateMachine — intent recording
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentRecording:
    def test_record_and_retrieve(self):
        sm = QuestionStateMachine()
        intent = UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=0.9,
            contains_solution_attempt=True,
            semantic_level=SemanticLevel.DEEP,
        )
        sm.record_intent(intent)

        assert len(sm.intent_sequence) == 1
        assert sm.last_intent is intent

    def test_last_intent_none_when_empty(self):
        sm = QuestionStateMachine()
        assert sm.last_intent is None

    def test_multiple_intents_ordered(self):
        sm = QuestionStateMachine()
        intents = [
            UtteranceIntentClassification(
                intent=UtteranceIntent.CLARIFICATION,
                confidence=0.95,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.SURFACE,
            ),
            UtteranceIntentClassification(
                intent=UtteranceIntent.ANSWER,
                confidence=0.88,
                contains_solution_attempt=True,
                semantic_level=SemanticLevel.DEEP,
            ),
        ]
        for ic in intents:
            sm.record_intent(ic)

        assert len(sm.intent_sequence) == 2
        assert sm.last_intent.intent == UtteranceIntent.ANSWER


# ═══════════════════════════════════════════════════════════════════════════
# QuestionStateMachine — snapshot serialization
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotSerialization:
    def test_to_snapshot_dict(self):
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)

        intent = UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=0.85,
            contains_solution_attempt=True,
            semantic_level=SemanticLevel.DEEP,
        )
        sm.record_intent(intent)
        sm.submit_answer()

        snapshot = sm.to_snapshot_dict()
        assert snapshot["clarification_count"] == 0
        assert snapshot["clarification_limit_exceeded"] is False
        assert snapshot["final_intent"] == "ANSWER"
        assert snapshot["final_intent_confidence"] == 0.85
        assert len(snapshot["intent_sequence"]) == 1

    def test_snapshot_with_clarifications(self):
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)
        sm.request_clarification()
        sm.provide_clarification_response()

        snapshot = sm.to_snapshot_dict()
        assert snapshot["clarification_count"] == 1
        assert snapshot["clarification_limit_exceeded"] is False


# ═══════════════════════════════════════════════════════════════════════════
# QuestionStateMachine — error cases
# ═══════════════════════════════════════════════════════════════════════════


class TestStateMachineErrors:
    def test_cannot_answer_from_asked(self):
        sm = QuestionStateMachine()
        with pytest.raises(InvalidExchangeStateTransitionError):
            sm.submit_answer()

    def test_cannot_clarify_after_answer(self):
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)
        sm.submit_answer()

        with pytest.raises(InvalidExchangeStateTransitionError):
            sm.request_clarification()

    def test_terminal_state_no_transitions(self):
        sm = QuestionStateMachine()
        sm.transition_to(ExchangeState.WAITING_INPUT)
        sm.submit_answer()
        sm.transition_to(ExchangeState.EVALUATED)
        sm.transition_to(ExchangeState.NEXT_QUESTION)

        with pytest.raises(InvalidExchangeStateTransitionError):
            sm.transition_to(ExchangeState.ASKED)
