"""
Unit Tests — Progress Tracker

Tests progress update logic for DB and Redis.
Uses mocks for DB session and Redis client.
"""

import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from app.interview.orchestration.contracts import ProgressUpdate
from app.interview.orchestration.progress_tracker import ProgressTracker


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    db = MagicMock()
    # Default: execution returns a row (update succeeded)
    result = MagicMock()
    result.fetchone.return_value = (1,)
    db.execute.return_value = result
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = MagicMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis


@pytest.fixture
def tracker(mock_db, mock_redis):
    return ProgressTracker(mock_db, mock_redis)


# ════════════════════════════════════════════════════════════════════════
# update_progress
# ════════════════════════════════════════════════════════════════════════


class TestUpdateProgress:
    def test_returns_progress_update(self, tracker):
        """update_progress returns a ProgressUpdate with correct values."""
        result = tracker.update_progress(
            submission_id=1,
            sequence_order=3,
            total_questions=10,
        )

        assert isinstance(result, ProgressUpdate)
        assert result.submission_id == 1
        assert result.current_sequence == 3
        assert result.total_questions == 10
        assert result.progress_percentage == 30.0
        assert result.is_complete is False

    def test_progress_100_when_complete(self, tracker):
        """100% progress when all questions answered."""
        result = tracker.update_progress(
            submission_id=1,
            sequence_order=10,
            total_questions=10,
        )

        assert result.progress_percentage == 100.0
        assert result.is_complete is True

    def test_progress_percentage_rounding(self, tracker):
        """Progress percentage is rounded to 2 decimals."""
        result = tracker.update_progress(
            submission_id=1,
            sequence_order=1,
            total_questions=3,
        )

        assert result.progress_percentage == 33.33

    def test_db_update_called(self, tracker, mock_db):
        """DB update is executed for progress tracking."""
        tracker.update_progress(
            submission_id=42,
            sequence_order=5,
            total_questions=10,
        )

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["seq"] == 5
        assert params["sid"] == 42

    def test_redis_update_called(self, tracker, mock_redis):
        """Redis set is called with progress data."""
        tracker.update_progress(
            submission_id=42,
            sequence_order=5,
            total_questions=10,
        )

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        assert key == "interview_session:42"

    def test_redis_merges_existing_data(self, tracker, mock_redis):
        """Progress is merged into existing Redis session data."""
        existing = json.dumps({
            "submission_id": 42,
            "status": "in_progress",
            "candidate_id": 100,
        })
        mock_redis.get.return_value = existing

        tracker.update_progress(
            submission_id=42,
            sequence_order=3,
            total_questions=10,
        )

        set_call = mock_redis.set.call_args
        stored_data = json.loads(set_call[0][1])
        assert stored_data["current_sequence"] == 3
        assert stored_data["total_questions"] == 10
        assert stored_data["status"] == "in_progress"  # preserved
        assert stored_data["candidate_id"] == 100  # preserved

    def test_redis_failure_does_not_raise(self, tracker, mock_redis):
        """Redis failure is logged but does not raise."""
        mock_redis.set.side_effect = Exception("Redis down")

        # Should not raise
        result = tracker.update_progress(
            submission_id=1,
            sequence_order=1,
            total_questions=5,
        )
        assert result is not None


# ════════════════════════════════════════════════════════════════════════
# get_progress
# ════════════════════════════════════════════════════════════════════════


class TestGetProgress:
    def test_from_redis(self, tracker, mock_redis):
        """Reads progress from Redis when available."""
        mock_redis.get.return_value = json.dumps({
            "submission_id": 42,
            "current_sequence": 5,
            "total_questions": 10,
        })

        result = tracker.get_progress(42)

        assert result is not None
        assert result.current_sequence == 5
        assert result.total_questions == 10
        assert result.progress_percentage == 50.0

    def test_redis_miss_falls_back_to_db(self, tracker, mock_db, mock_redis):
        """Falls back to DB when Redis has no data."""
        mock_redis.get.return_value = None

        sub = SimpleNamespace(
            id=42,
            current_exchange_sequence=3,
            template_structure_snapshot={"total_questions": 5},
        )
        mock_db.query.return_value.filter.return_value.first.return_value = sub

        result = tracker.get_progress(42)

        assert result is not None
        assert result.current_sequence == 3
        assert result.total_questions == 5

    def test_not_found_returns_none(self, tracker, mock_db, mock_redis):
        """Returns None if submission doesn't exist in Redis or DB."""
        mock_redis.get.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = tracker.get_progress(99)
        assert result is None

    def test_redis_error_falls_back_to_db(self, tracker, mock_db, mock_redis):
        """Redis error falls back to DB gracefully."""
        mock_redis.get.side_effect = Exception("Connection refused")

        sub = SimpleNamespace(
            id=42,
            current_exchange_sequence=2,
            template_structure_snapshot={"total_questions": 10},
        )
        mock_db.query.return_value.filter.return_value.first.return_value = sub

        result = tracker.get_progress(42)
        assert result is not None
        assert result.current_sequence == 2
        assert result.total_questions == 10
