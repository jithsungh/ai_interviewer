"""
Integration Tests — Interview Exchange Service

Tests the exchange module with mocked DB session and Redis, simulating
end-to-end flows through the repository and domain layers.

Verifies:
  1. Exchange creation flow (validation → persistence)
  2. Immutability enforcement (update/delete forbidden)
  3. Sequence integrity enforcement
  4. Response completeness enforcement
  5. State machine + clarification policy integration
  6. Intent classification + state machine integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.interview.exchanges.clarification_policy import (
    ClarificationPolicy,
    ClarificationResponse,
)
from app.interview.exchanges.contracts import (
    ContentMetadata,
    ExchangeCreationData,
    ExchangeQuestionType,
)
from app.interview.exchanges.errors import (
    IncompleteResponseError,
    SequenceGapError,
)
from app.interview.exchanges.intent_classifier import (
    InterviewContext,
    RuleBasedIntentClassifier,
    SemanticLevel,
    UtteranceIntent,
    UtteranceIntentClassification,
)
from app.interview.exchanges.question_state_machine import (
    ExchangeState,
    QuestionStateMachine,
)
from app.interview.exchanges.repository import InterviewExchangeRepository
from app.shared.errors import (
    ExchangeImmutabilityViolation,
    InterviewNotActiveError,
    NotFoundError,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_submission(**overrides):
    defaults = dict(id=1, candidate_id=100, status="in_progress")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_exchange(**overrides):
    defaults = dict(
        id=1,
        interview_submission_id=1,
        sequence_order=1,
        question_id=101,
        coding_problem_id=None,
        question_text="What is polymorphism?",
        expected_answer=None,
        difficulty_at_time="medium",
        response_text="Polymorphism is...",
        response_code=None,
        response_time_ms=45000,
        ai_followup_message=None,
        content_metadata={"question_type": "text"},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_creation_data(**overrides) -> ExchangeCreationData:
    defaults = dict(
        submission_id=1,
        sequence_order=1,
        question_id=101,
        question_text="What is polymorphism?",
        difficulty_at_time="medium",
        response_text="Polymorphism is...",
        response_time_ms=45000,
        content_metadata=ContentMetadata(
            question_type=ExchangeQuestionType.TEXT,
            section_name="technical",
        ),
    )
    defaults.update(overrides)
    return ExchangeCreationData(**defaults)


def _mock_db_for_create(submission=None, exchange_count=0, existing_orders=None):
    """Build mock DB session that handles submission + exchange queries."""
    db = MagicMock()
    existing_orders = existing_orders or set()

    def _query_side_effect(model_or_col):
        mock = MagicMock()
        filter_mock = MagicMock()

        model_name = ""
        if hasattr(model_or_col, "__tablename__"):
            model_name = model_or_col.__tablename__

        if "interview_submissions" in str(model_or_col) or model_name == "interview_submissions":
            filter_mock.first.return_value = submission
        else:
            filter_mock.count.return_value = exchange_count
            filter_mock.all.return_value = [(s,) for s in existing_orders]
            filter_mock.first.return_value = None

        mock.filter.return_value = filter_mock
        return mock

    db.query.side_effect = _query_side_effect
    return db


# ═══════════════════════════════════════════════════════════════════════════
# Full Exchange Creation Flow
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeCreationFlow:
    def test_create_first_exchange_succeeds(self):
        """First exchange (seq=1) with valid data succeeds."""
        sub = _make_submission()
        db = _mock_db_for_create(submission=sub, exchange_count=0, existing_orders=set())
        repo = InterviewExchangeRepository(db)

        data = _make_creation_data()
        # The actual add + flush is mocked, so we verify no exception
        exchange = repo.create(data)
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_create_rejects_completed_submission(self):
        """Cannot create exchange for completed submission."""
        sub = _make_submission(status="completed")
        db = _mock_db_for_create(submission=sub)
        repo = InterviewExchangeRepository(db)

        with pytest.raises(InterviewNotActiveError):
            repo.create(_make_creation_data())

    def test_create_rejects_pending_submission(self):
        """Cannot create exchange for pending submission."""
        sub = _make_submission(status="pending")
        db = _mock_db_for_create(submission=sub)
        repo = InterviewExchangeRepository(db)

        with pytest.raises(InterviewNotActiveError):
            repo.create(_make_creation_data())

    def test_create_rejects_missing_submission(self):
        """Cannot create exchange for non-existent submission."""
        db = _mock_db_for_create(submission=None)
        repo = InterviewExchangeRepository(db)

        with pytest.raises(NotFoundError):
            repo.create(_make_creation_data())


# ═══════════════════════════════════════════════════════════════════════════
# Immutability Enforcement (End-to-End)
# ═══════════════════════════════════════════════════════════════════════════


class TestImmutabilityEnforcement:
    def test_update_always_raises(self):
        db = MagicMock()
        repo = InterviewExchangeRepository(db)

        with pytest.raises(ExchangeImmutabilityViolation) as exc_info:
            repo.update(42, response_text="modified answer")

        assert exc_info.value.error_code == "EXCHANGE_IMMUTABLE"
        assert exc_info.value.metadata["exchange_id"] == 42

    def test_delete_always_raises(self):
        db = MagicMock()
        repo = InterviewExchangeRepository(db)

        with pytest.raises(ExchangeImmutabilityViolation) as exc_info:
            repo.delete(42)

        assert exc_info.value.error_code == "EXCHANGE_IMMUTABLE"


# ═══════════════════════════════════════════════════════════════════════════
# State Machine + Clarification Policy Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestStateMachineClarificationIntegration:
    def test_full_flow_with_one_clarification(self):
        """
        Question lifecycle:
        ASKED → WAITING → CLARIFICATION_REQUESTED → WAITING →
        ANSWER_SUBMITTED → EVALUATED → NEXT_QUESTION
        """
        sm = QuestionStateMachine()
        policy = ClarificationPolicy()
        classifier = RuleBasedIntentClassifier()

        # Question asked
        sm.transition_to(ExchangeState.WAITING_INPUT)

        # Candidate asks clarification
        ctx = InterviewContext(
            question_text="Implement binary search",
            question_type="coding",
            exchange_state=sm.current_state.value,
        )
        intent = classifier.classify("Can you clarify what you mean by sorted?", ctx)
        sm.record_intent(intent)
        assert intent.intent == UtteranceIntent.CLARIFICATION

        # Process clarification
        req = policy.request_clarification("What do you mean by sorted?")
        assert req is not None
        granted = sm.request_clarification()
        assert granted is True
        assert sm.current_state == ExchangeState.CLARIFICATION_REQUESTED

        # Provide clarification response and validate
        resp = ClarificationResponse(
            clarification_text="Sorted means the array elements are in ascending order.",
            contains_hint=False,
            contains_analogy=False,
            violates_policy=False,
        )
        validated = policy.validate_response(resp)
        assert validated.violates_policy is False
        sm.provide_clarification_response()
        assert sm.current_state == ExchangeState.WAITING_INPUT

        # Candidate provides answer
        answer_intent = classifier.classify(
            "I would use a binary search approach with two pointers",
            InterviewContext(
                question_text="Implement binary search",
                question_type="coding",
                exchange_state=sm.current_state.value,
            ),
        )
        sm.record_intent(answer_intent)
        assert answer_intent.intent == UtteranceIntent.ANSWER

        sm.submit_answer()
        assert sm.current_state == ExchangeState.ANSWER_SUBMITTED
        assert sm.response_locked is True

        # Evaluate
        sm.transition_to(ExchangeState.EVALUATED)
        sm.transition_to(ExchangeState.NEXT_QUESTION)

        # Verify audit trail
        snapshot = sm.to_snapshot_dict()
        assert snapshot["clarification_count"] == 1
        assert snapshot["final_intent"] == "ANSWER"
        assert len(snapshot["intent_sequence"]) == 2

        # Verify policy audit
        audit = policy.to_audit_dict()
        assert audit["clarification_count"] == 1
        assert len(audit["clarifications"]) == 1

    def test_clarification_limit_auto_skip(self):
        """
        After 3 clarifications, 4th auto-transitions to ANSWER_SUBMITTED.
        """
        sm = QuestionStateMachine()
        policy = ClarificationPolicy()

        sm.transition_to(ExchangeState.WAITING_INPUT)

        for i in range(3):
            sm.request_clarification()
            policy.request_clarification(f"Question {i}")
            resp = ClarificationResponse(
                clarification_text=f"Answer {i}",
                contains_hint=False,
                contains_analogy=False,
                violates_policy=False,
            )
            policy.validate_response(resp)
            sm.provide_clarification_response()

        assert sm.clarification_count == 3
        assert policy.limit_exceeded is True
        assert policy.can_clarify is False

        # 4th attempt
        granted = sm.request_clarification()
        assert granted is False
        assert sm.current_state == ExchangeState.ANSWER_SUBMITTED
        assert sm.clarification_limit_exceeded is True


# ═══════════════════════════════════════════════════════════════════════════
# Intent Classification + Context Awareness
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentClassificationIntegration:
    def test_post_answer_window_overrides_intent(self):
        """In POST_ANSWER_WINDOW, everything is classified as POST_ANSWER."""
        classifier = RuleBasedIntentClassifier()
        ctx = InterviewContext(
            question_text="Implement sorting",
            question_type="coding",
            exchange_state="POST_ANSWER_WINDOW",
        )

        # Even an answer-like utterance is POST_ANSWER
        result = classifier.classify("I would use merge sort", ctx)
        assert result.intent == UtteranceIntent.POST_ANSWER

    def test_conservative_answer_default(self):
        """Ambiguous text defaults to ANSWER."""
        classifier = RuleBasedIntentClassifier()
        ctx = InterviewContext(
            question_text="Explain OOP",
            question_type="text",
            exchange_state="WAITING_INPUT",
        )

        result = classifier.classify(
            "Well, object oriented programming involves objects and classes",
            ctx,
        )
        assert result.intent == UtteranceIntent.ANSWER


# ═══════════════════════════════════════════════════════════════════════════
# Sequence Validation Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestSequenceValidationIntegration:
    def test_gap_rejected_at_repository_level(self):
        """Creating exchange with sequence gap is rejected."""
        sub = _make_submission()
        db = _mock_db_for_create(
            submission=sub,
            exchange_count=1,
            existing_orders={1},
        )
        repo = InterviewExchangeRepository(db)

        # Skip sequence 2, try 3
        with pytest.raises(SequenceGapError):
            repo.create(_make_creation_data(sequence_order=3))

    def test_incomplete_response_rejected_at_repository_level(self):
        """Creating coding exchange without code_submission_id is rejected."""
        sub = _make_submission()
        db = _mock_db_for_create(
            submission=sub,
            exchange_count=0,
            existing_orders=set(),
        )
        repo = InterviewExchangeRepository(db)

        with pytest.raises(IncompleteResponseError):
            repo.create(
                _make_creation_data(
                    response_text=None,
                    response_code="def solve(): pass",
                    content_metadata=ContentMetadata(
                        question_type=ExchangeQuestionType.CODING,
                    ),
                )
            )
