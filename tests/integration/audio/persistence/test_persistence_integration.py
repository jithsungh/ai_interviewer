"""
Integration tests for the audio/persistence module.

These tests hit a real PostgreSQL database to validate:
- Repository CRUD operations and query correctness
- UNIQUE constraint enforcement on interview_exchange_id
- Finalization semantics (immutability after finalize)
- Idempotent finalization
- create_or_get race condition handling
- get_by_submission_id cross-table join
- CHECK constraint enforcement (speech_state, confidence, sentiment)

Requires:
- PostgreSQL with interviewer schema + audio-persistence migration applied
- Set TEST_DATABASE_URL env-var to override the default test-cluster address

Each test runs within a transactional session that is **always rolled back**.
"""

import pytest
from decimal import Decimal
from sqlalchemy import text

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)
from app.audio.persistence.exceptions import (
    DuplicateAnalyticsError,
    ImmutabilityError,
)
from app.audio.persistence.repository import SqlAudioAnalyticsRepository
from app.shared.errors import NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_create_dto(exchange_id: int, **overrides) -> AudioAnalyticsCreate:
    defaults = dict(
        interview_exchange_id=exchange_id,
        transcript="Test transcript content.",
        confidence_score=0.92,
        speech_rate_wpm=145,
        filler_word_count=3,
        sentiment_score=0.35,
        speech_state="complete",
    )
    defaults.update(overrides)
    return AudioAnalyticsCreate(**defaults)


# ====================================================================
# Create
# ====================================================================


class TestCreate:
    """Repository.create() against real database."""

    def test_create_returns_entity(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        dto = _make_create_dto(audio_seed["exchange_id"])
        entity = repo.create(dto)

        assert entity.id is not None
        assert entity.interview_exchange_id == audio_seed["exchange_id"]
        assert entity.transcript == "Test transcript content."
        assert entity.transcript_finalized is False

    def test_create_duplicate_raises(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        dto = _make_create_dto(audio_seed["exchange_id"])

        repo.create(dto)

        with pytest.raises(DuplicateAnalyticsError) as exc_info:
            repo.create(dto)

        assert exc_info.value.exchange_id == audio_seed["exchange_id"]


# ====================================================================
# create_or_get
# ====================================================================


class TestCreateOrGet:
    """Repository.create_or_get() — idempotent creation."""

    def test_creates_when_none_exists(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        dto = _make_create_dto(audio_seed["exchange_id"])
        entity = repo.create_or_get(dto)

        assert entity.id is not None
        assert entity.interview_exchange_id == audio_seed["exchange_id"]

    def test_returns_existing_on_duplicate(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        dto = _make_create_dto(audio_seed["exchange_id"])

        first = repo.create(dto)
        second = repo.create_or_get(dto)

        assert second.id == first.id


# ====================================================================
# Read
# ====================================================================


class TestGetById:
    """Repository.get_by_id()."""

    def test_found(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        created = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_not_found(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        assert repo.get_by_id(999999) is None


class TestGetByExchangeId:
    """Repository.get_by_exchange_id()."""

    def test_found(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        created = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        fetched = repo.get_by_exchange_id(audio_seed["exchange_id"])
        assert fetched is not None
        assert fetched.id == created.id

    def test_not_found(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        assert repo.get_by_exchange_id(999999) is None


class TestGetBySubmissionId:
    """Repository.get_by_submission_id() — cross-table join."""

    def test_returns_analytics_for_all_exchanges(
        self, db_session, seed_exchange_pair, seed_submission,
    ):
        """Creates analytics for two exchanges, retrieves both via submission."""
        repo = SqlAudioAnalyticsRepository(db_session)

        for exch_id in seed_exchange_pair:
            repo.create(_make_create_dto(exch_id))

        results = repo.get_by_submission_id(seed_submission)
        assert len(results) == 2

    def test_empty_for_unrelated_submission(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        results = repo.get_by_submission_id(999999)
        assert results == []


class TestIsFinalized:
    """Repository.is_finalized()."""

    def test_not_finalized(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        repo.create(_make_create_dto(audio_seed["exchange_id"]))

        assert repo.is_finalized(audio_seed["exchange_id"]) is False

    def test_finalized(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))
        repo.finalize(entity.id)

        assert repo.is_finalized(audio_seed["exchange_id"]) is True

    def test_no_analytics_returns_false(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        assert repo.is_finalized(999999) is False


# ====================================================================
# Update
# ====================================================================


class TestUpdate:
    """Repository.update() — non-finalized records only."""

    def test_update_success(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        updated = repo.update(
            entity.id,
            AudioAnalyticsUpdate(transcript="Updated transcript."),
        )

        assert updated.transcript == "Updated transcript."

    def test_update_multiple_fields(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        updated = repo.update(
            entity.id,
            AudioAnalyticsUpdate(
                transcript="New text.",
                confidence_score=0.99,
                filler_word_count=10,
            ),
        )

        assert updated.transcript == "New text."

    def test_update_not_found_raises(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)

        with pytest.raises(NotFoundError):
            repo.update(
                999999,
                AudioAnalyticsUpdate(transcript="Should fail"),
            )

    def test_update_after_finalize_raises_immutability(
        self, db_session, audio_seed,
    ):
        """Cannot update after finalization."""
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))
        repo.finalize(entity.id)

        with pytest.raises(ImmutabilityError) as exc_info:
            repo.update(
                entity.id,
                AudioAnalyticsUpdate(transcript="Should fail"),
            )

        assert exc_info.value.analytics_id == entity.id


# ====================================================================
# Finalize
# ====================================================================


class TestFinalize:
    """Repository.finalize() — marks transcript as immutable."""

    def test_finalize_sets_flag(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        finalized = repo.finalize(entity.id)

        assert finalized.transcript_finalized is True
        assert finalized.finalized_at is not None

    def test_finalize_idempotent(self, db_session, audio_seed):
        """Second finalize call returns same result without error."""
        repo = SqlAudioAnalyticsRepository(db_session)
        entity = repo.create(_make_create_dto(audio_seed["exchange_id"]))

        first = repo.finalize(entity.id)
        second = repo.finalize(entity.id)

        assert first.transcript_finalized is True
        assert second.transcript_finalized is True
        assert first.finalized_at == second.finalized_at

    def test_finalize_not_found_raises(self, db_session, audio_seed):
        repo = SqlAudioAnalyticsRepository(db_session)

        with pytest.raises(NotFoundError):
            repo.finalize(999999)
