"""
Unit Tests — Race Resolver

Tests distributed lock acquisition and idempotent exchange creation.
Uses mocks for DB session and Redis client.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from app.interview.orchestration.race_resolver import RaceResolver


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    # Default: lock acquisition succeeds (SET NX returns True)
    redis.set.return_value = True
    return redis


@pytest.fixture
def resolver(mock_db, mock_redis):
    return RaceResolver(mock_db, mock_redis, lock_timeout=10)


# ════════════════════════════════════════════════════════════════════════
# check_exchange_exists
# ════════════════════════════════════════════════════════════════════════


class TestCheckExchangeExists:
    def test_returns_none_when_not_exists(self, resolver, mock_db):
        """Returns None when no exchange exists for (submission, sequence)."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = resolver.check_exchange_exists(submission_id=1, sequence_order=3)
        assert result is None

    def test_returns_exchange_when_exists(self, resolver, mock_db):
        """Returns the exchange model when it exists."""
        existing = SimpleNamespace(id=42, sequence_order=3)
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = resolver.check_exchange_exists(submission_id=1, sequence_order=3)
        assert result is not None
        assert result.id == 42


# ════════════════════════════════════════════════════════════════════════
# resolve_or_create
# ════════════════════════════════════════════════════════════════════════


class TestResolveOrCreate:

    @patch("app.interview.orchestration.race_resolver.acquire_lock")
    def test_creates_when_no_existing(self, mock_acquire, resolver, mock_db):
        """Creates new exchange when none exists."""
        # No existing exchange
        mock_db.query.return_value.filter.return_value.first.return_value = None

        new_exchange = SimpleNamespace(id=99, sequence_order=3)
        create_fn = MagicMock(return_value=new_exchange)

        result = resolver.resolve_or_create(
            submission_id=1,
            sequence_order=3,
            create_fn=create_fn,
        )

        assert result.id == 99
        create_fn.assert_called_once()

    @patch("app.interview.orchestration.race_resolver.acquire_lock")
    def test_returns_existing_when_race_lost(self, mock_acquire, resolver, mock_db):
        """Returns existing exchange when race is lost (idempotent)."""
        existing = SimpleNamespace(id=42, sequence_order=3)
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        create_fn = MagicMock()

        result = resolver.resolve_or_create(
            submission_id=1,
            sequence_order=3,
            create_fn=create_fn,
        )

        assert result.id == 42
        create_fn.assert_not_called()  # Create was NOT called

    @patch("app.interview.orchestration.race_resolver.acquire_lock")
    def test_create_fn_exception_propagates(self, mock_acquire, resolver, mock_db):
        """Exceptions from create_fn propagate correctly."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        create_fn = MagicMock(side_effect=ValueError("Creation failed"))

        with pytest.raises(ValueError, match="Creation failed"):
            resolver.resolve_or_create(
                submission_id=1,
                sequence_order=3,
                create_fn=create_fn,
            )
