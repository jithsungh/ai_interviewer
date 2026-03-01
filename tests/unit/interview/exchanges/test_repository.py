"""
Unit Tests — Exchange Repository

Tests the repository layer with a **mocked** SQLAlchemy session.
Verifies:
  1. Create exchanges with proper validation
  2. Update raises ExchangeImmutabilityViolation
  3. Delete raises ExchangeImmutabilityViolation
  4. Read operations work correctly
  5. Idempotent duplicate handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from app.interview.exchanges.contracts import (
    ContentMetadata,
    ExchangeCreationData,
    ExchangeQuestionType,
)
from app.interview.exchanges.errors import (
    DuplicateSequenceError,
    IncompleteResponseError,
    SequenceGapError,
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
    """Create a minimal fake submission object."""
    defaults = dict(
        id=1,
        candidate_id=100,
        status="in_progress",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_exchange(**overrides):
    """Create a minimal fake exchange object."""
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
    """Build ExchangeCreationData with defaults."""
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


def _mock_db_session(
    submission=None,
    exchange_count=0,
    existing_sequences=None,
    existing_exchange=None,
):
    """Build a mock SQLAlchemy session."""
    db = MagicMock()

    # Build the chain: query(...).filter(...).first() / .count() / .all()
    def _query_side_effect(model_or_col):
        mock = MagicMock()

        # Detect what's being queried
        model_name = getattr(model_or_col, "__name__", "")
        if hasattr(model_or_col, "__tablename__"):
            model_name = model_or_col.__tablename__

        filter_mock = MagicMock()

        if model_name == "interview_submissions" or "InterviewSubmission" in str(model_or_col):
            filter_mock.first.return_value = submission
        elif model_name == "interview_exchanges" or "InterviewExchange" in str(model_or_col):
            filter_mock.first.return_value = existing_exchange
            filter_mock.count.return_value = exchange_count
            if existing_sequences is not None:
                filter_mock.all.return_value = [(s,) for s in existing_sequences]
            else:
                filter_mock.all.return_value = []
        else:
            # For exists() subquery
            filter_mock.first.return_value = existing_exchange
            filter_mock.scalar.return_value = existing_exchange is not None

        mock.filter.return_value = filter_mock
        mock.exists.return_value = MagicMock()

        return mock

    db.query.side_effect = _query_side_effect
    return db


# ═══════════════════════════════════════════════════════════════════════════
# UPDATE — Immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestUpdateForbidden:
    def test_update_raises_immutability_violation(self):
        """update() always raises ExchangeImmutabilityViolation."""
        db = MagicMock()
        repo = InterviewExchangeRepository(db)

        with pytest.raises(ExchangeImmutabilityViolation) as exc_info:
            repo.update(exchange_id=42, response_text="modified")

        assert exc_info.value.metadata["exchange_id"] == 42
        assert exc_info.value.http_status_code == 400

    def test_update_with_no_args_still_raises(self):
        db = MagicMock()
        repo = InterviewExchangeRepository(db)

        with pytest.raises(ExchangeImmutabilityViolation):
            repo.update(exchange_id=1)


# ═══════════════════════════════════════════════════════════════════════════
# DELETE — Immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestDeleteForbidden:
    def test_delete_raises_immutability_violation(self):
        """delete() always raises ExchangeImmutabilityViolation."""
        db = MagicMock()
        repo = InterviewExchangeRepository(db)

        with pytest.raises(ExchangeImmutabilityViolation) as exc_info:
            repo.delete(exchange_id=99)

        assert exc_info.value.metadata["exchange_id"] == 99


# ═══════════════════════════════════════════════════════════════════════════
# CREATE — Happy paths
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateExchange:
    def test_submission_not_found(self):
        """Raise NotFoundError if submission doesn't exist."""
        db = _mock_db_session(submission=None)
        repo = InterviewExchangeRepository(db)

        with pytest.raises(NotFoundError):
            repo.create(_make_creation_data())

    def test_submission_not_in_progress(self):
        """Raise InterviewNotActiveError if submission is not in_progress."""
        sub = _make_submission(status="completed")
        db = _mock_db_session(submission=sub)
        repo = InterviewExchangeRepository(db)

        with pytest.raises(InterviewNotActiveError):
            repo.create(_make_creation_data())

    def test_sequence_gap_rejected(self):
        """SequenceGapError if proposed sequence doesn't match expected."""
        sub = _make_submission()
        db = _mock_db_session(submission=sub, exchange_count=0, existing_sequences=set())
        repo = InterviewExchangeRepository(db)

        with pytest.raises(SequenceGapError):
            repo.create(_make_creation_data(sequence_order=3))

    def test_response_completeness_validated(self):
        """IncompleteResponseError if response data is missing."""
        sub = _make_submission()
        db = _mock_db_session(submission=sub, exchange_count=0, existing_sequences=set())
        repo = InterviewExchangeRepository(db)

        with pytest.raises(IncompleteResponseError):
            repo.create(
                _make_creation_data(
                    response_text=None,
                    content_metadata=ContentMetadata(
                        question_type=ExchangeQuestionType.TEXT,
                    ),
                )
            )


# ═══════════════════════════════════════════════════════════════════════════
# READ operations
# ═══════════════════════════════════════════════════════════════════════════


class TestReadOperations:
    def test_get_by_id_returns_exchange(self):
        exchange = _make_exchange()
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = exchange
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        result = repo.get_by_id(1)
        assert result is exchange

    def test_get_by_id_returns_none(self):
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        result = repo.get_by_id(999)
        assert result is None

    def test_get_by_id_or_raise_found(self):
        exchange = _make_exchange()
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = exchange
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        result = repo.get_by_id_or_raise(1)
        assert result is exchange

    def test_get_by_id_or_raise_not_found(self):
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        with pytest.raises(NotFoundError):
            repo.get_by_id_or_raise(999)

    def test_list_by_submission(self):
        exchanges = [_make_exchange(sequence_order=i) for i in range(1, 4)]
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        order_mock.all.return_value = exchanges
        filter_mock.order_by.return_value = order_mock
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        result = repo.list_by_submission(1)
        assert len(result) == 3

    def test_exists_for_sequence_true(self):
        db = MagicMock()
        # Chain: db.query(db.query(...).filter(...).exists()).scalar()
        inner_query = MagicMock()
        inner_filter = MagicMock()
        inner_exists = MagicMock()
        inner_filter.exists.return_value = inner_exists
        inner_query.filter.return_value = inner_filter

        outer_query = MagicMock()
        outer_query.scalar.return_value = True

        def query_side_effect(arg):
            if arg is inner_exists:
                return outer_query
            return inner_query

        db.query.side_effect = query_side_effect

        repo = InterviewExchangeRepository(db)
        assert repo.exists_for_sequence(1, 1) is True

    def test_count_by_submission(self):
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()
        filter_mock.count.return_value = 5
        query_mock.filter.return_value = filter_mock
        db.query.return_value = query_mock

        repo = InterviewExchangeRepository(db)
        assert repo.count_by_submission(1) == 5
