# Audio Persistence Module Testing Guide

## Testing Philosophy

Persistence testing focuses on **data integrity** and **concurrency**. Tests use:

- **Real database** (PostgreSQL test instance or SQLite in-memory)
- **Database transactions** (rollback after each test)
- **Concurrent threads** (test race conditions)

Most critical tests:

1. **UNIQUE constraint enforcement** (duplicate exchange_id)
2. **Immutability after finalization** (cannot update finalized transcript)
3. **Concurrent create race condition** (two threads create for same exchange)

---

## Test Structure

```
tests/
├── unit/
│   └── audio/
│       └── persistence/
│           ├── test_repository_basic_crud.py
│           ├── test_finalization.py
│           └── test_constraints.py
└── integration/
    └── audio/
        └── persistence/
            ├── test_concurrent_writes.py
            ├── test_cascade_delete.py
            └── test_transaction_rollback.py
```

---

## 1. Unit Tests (Database Required)

### Basic CRUD Tests

```python
# tests/unit/audio/persistence/test_repository_basic_crud.py

import pytest
from sqlalchemy.exc import IntegrityError
from app.audio.persistence.repository import AudioAnalyticsRepository
from app.audio.persistence.exceptions import DuplicateAnalyticsError, NotFoundError, ImmutabilityError

@pytest.fixture
def db_with_exchange(db_session):
    """Create test exchange"""
    from app.persistence.models import InterviewExchange

    exchange = InterviewExchange(
        submission_id=1,
        question_snapshot={"text": "Test question"},
        stage="responding"
    )
    db_session.add(exchange)
    db_session.commit()
    return db_session, exchange.id

def test_create_audio_analytics(db_with_exchange):
    """Create audio analytics record"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="The answer is dynamic programming.",
        confidence_score=0.92,
        speech_state="complete",
        speech_rate_wpm=145,
        filler_word_count=2,
        sentiment_score=0.35
    ))

    assert analytics.id is not None
    assert analytics.transcript == "The answer is dynamic programming."
    assert analytics.confidence_score == 0.92
    assert analytics.transcript_finalized is False

def test_create_duplicate_raises_error(db_with_exchange):
    """Cannot create duplicate analytics for same exchange"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Create first
    repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="First",
        confidence_score=0.9,
        speech_state="complete"
    ))

    # Attempt duplicate
    with pytest.raises(DuplicateAnalyticsError):
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id,
            transcript="Second",
            confidence_score=0.8,
            speech_state="complete"
        ))

def test_get_by_exchange_id(db_with_exchange):
    """Get analytics by exchange ID"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    created = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete"
    ))

    fetched = repo.get_by_exchange_id(exchange_id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.transcript == "Test"

def test_get_non_existent_returns_none(db_session):
    """Get non-existent analytics returns None"""
    repo = AudioAnalyticsRepository(db_session)

    result = repo.get_by_exchange_id(exchange_id=99999)

    assert result is None

def test_update_analytics(db_with_exchange):
    """Update analytics before finalization"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Original transcript",
        confidence_score=0.9,
        speech_state="complete"
    ))

    updated = repo.update(
        analytics_id=analytics.id,
        data=AudioAnalyticsUpdate(
            transcript="Updated transcript",
            confidence_score=0.95
        )
    )

    assert updated.transcript == "Updated transcript"
    assert updated.confidence_score == 0.95
    assert updated.updated_at > updated.created_at

def test_update_non_existent_raises_error(db_session):
    """Update non-existent analytics raises error"""
    repo = AudioAnalyticsRepository(db_session)

    with pytest.raises(NotFoundError):
        repo.update(
            analytics_id=99999,
            data=AudioAnalyticsUpdate(transcript="Test")
        )

def test_get_by_submission_id(db_session):
    """Get all analytics for a submission"""
    from app.persistence.models import InterviewExchange

    # Create submission with multiple exchanges
    submission_id = 1

    exchange1 = InterviewExchange(submission_id=submission_id, question_snapshot={}, stage="responding")
    exchange2 = InterviewExchange(submission_id=submission_id, question_snapshot={}, stage="responding")
    db_session.add_all([exchange1, exchange2])
    db_session.commit()

    repo = AudioAnalyticsRepository(db_session)

    # Create analytics for both exchanges
    repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange1.id,
        transcript="First",
        confidence_score=0.9,
        speech_state="complete"
    ))

    repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange2.id,
        transcript="Second",
        confidence_score=0.85,
        speech_state="complete"
    ))

    # Get all analytics for submission
    all_analytics = repo.get_by_submission_id(submission_id)

    assert len(all_analytics) == 2
    assert set(a.transcript for a in all_analytics) == {"First", "Second"}
```

### Finalization Tests

```python
# tests/unit/audio/persistence/test_finalization.py

def test_finalize_analytics(db_with_exchange):
    """Finalize analytics marks as immutable"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete"
    ))

    assert analytics.transcript_finalized is False
    assert analytics.finalized_at is None

    finalized = repo.finalize(analytics.id)

    assert finalized.transcript_finalized is True
    assert finalized.finalized_at is not None

def test_cannot_update_after_finalization(db_with_exchange):
    """Cannot update finalized analytics"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Original",
        confidence_score=0.9,
        speech_state="complete"
    ))

    # Finalize
    repo.finalize(analytics.id)

    # Attempt update
    with pytest.raises(ImmutabilityError):
        repo.update(
            analytics_id=analytics.id,
            data=AudioAnalyticsUpdate(transcript="Modified")
        )

def test_finalize_idempotent(db_with_exchange):
    """Finalizing already finalized analytics is idempotent"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete"
    ))

    # Finalize twice
    finalized1 = repo.finalize(analytics.id)
    finalized2 = repo.finalize(analytics.id)

    # Both should succeed
    assert finalized1.transcript_finalized is True
    assert finalized2.transcript_finalized is True
    assert finalized1.finalized_at == finalized2.finalized_at

def test_is_finalized_check(db_with_exchange):
    """Check if analytics is finalized"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Before creation
    assert repo.is_finalized(exchange_id) is False

    # After creation
    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete"
    ))

    assert repo.is_finalized(exchange_id) is False

    # After finalization
    repo.finalize(analytics.id)

    assert repo.is_finalized(exchange_id) is True
```

### Constraint Tests

```python
# tests/unit/audio/persistence/test_constraints.py

def test_confidence_score_constraint(db_with_exchange):
    """Confidence score must be 0.0-1.0"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Valid: 0.0-1.0
    repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.5,
        speech_state="complete"
    ))

    # Invalid: >1.0
    with pytest.raises(IntegrityError):
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id + 1,
            transcript="Test",
            confidence_score=1.5,
            speech_state="complete"
        ))

def test_sentiment_score_constraint(db_with_exchange):
    """Sentiment score must be -1.0 to +1.0"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Valid: -1.0 to +1.0
    repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete",
        sentiment_score=0.0
    ))

    # Invalid: >+1.0
    with pytest.raises(IntegrityError):
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id + 1,
            transcript="Test",
            confidence_score=0.9,
            speech_state="complete",
            sentiment_score=1.5
        ))

def test_speech_state_constraint(db_with_exchange):
    """Speech state must be valid value"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Valid states
    for state in ["complete", "incomplete", "continuing"]:
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id + ["complete", "incomplete", "continuing"].index(state),
            transcript="Test",
            confidence_score=0.9,
            speech_state=state
        ))

    # Invalid state
    with pytest.raises(IntegrityError):
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id + 100,
            transcript="Test",
            confidence_score=0.9,
            speech_state="invalid_state"
        ))

def test_foreign_key_constraint(db_session):
    """Cannot create analytics for non-existent exchange"""
    repo = AudioAnalyticsRepository(db_session)

    with pytest.raises(IntegrityError):
        repo.create(AudioAnalyticsCreate(
            interview_exchange_id=99999,  # Non-existent
            transcript="Test",
            confidence_score=0.9,
            speech_state="complete"
        ))
```

---

## 2. Integration Tests (Concurrency & Transactions)

### Concurrent Writes Tests

```python
# tests/integration/audio/persistence/test_concurrent_writes.py

import threading
import pytest

def test_concurrent_create_race_condition(db_with_exchange):
    """Two threads creating analytics for same exchange"""
    db_session, exchange_id = db_with_exchange

    results = {"created": [], "errors": []}

    def create_analytics():
        try:
            # Each thread gets its own session
            from app.persistence.database import SessionLocal
            session = SessionLocal()

            repo = AudioAnalyticsRepository(session)
            analytics = repo.create(AudioAnalyticsCreate(
                interview_exchange_id=exchange_id,
                transcript="Concurrent test",
                confidence_score=0.9,
                speech_state="complete"
            ))
            results["created"].append(analytics.id)
            session.close()
        except DuplicateAnalyticsError as e:
            results["errors"].append(str(e))

    # Run two threads
    t1 = threading.Thread(target=create_analytics)
    t2 = threading.Thread(target=create_analytics)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # One should succeed, one should fail
    assert len(results["created"]) == 1
    assert len(results["errors"]) == 1

def test_create_or_get_handles_race(db_with_exchange):
    """create_or_get handles concurrent creates gracefully"""
    db_session, exchange_id = db_with_exchange

    results = []

    def create_or_get():
        from app.persistence.database import SessionLocal
        session = SessionLocal()

        repo = AudioAnalyticsRepository(session)
        analytics = repo.create_or_get(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id,
            transcript="Test",
            confidence_score=0.9,
            speech_state="complete"
        ))
        results.append(analytics.id)
        session.close()

    # Run two threads
    threads = [threading.Thread(target=create_or_get) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Both should succeed, both should get same ID
    assert len(results) == 2
    assert results[0] == results[1]

def test_concurrent_update_and_finalize(db_with_exchange):
    """Update and finalize happening concurrently"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)
    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="Original",
        confidence_score=0.9,
        speech_state="complete"
    ))

    results = {"update": None, "finalize": None}

    def update():
        from app.persistence.database import SessionLocal
        session = SessionLocal()
        repo = AudioAnalyticsRepository(session)
        try:
            repo.update(analytics.id, AudioAnalyticsUpdate(transcript="Updated"))
            results["update"] = "success"
        except ImmutabilityError:
            results["update"] = "immutable"
        session.close()

    def finalize():
        from app.persistence.database import SessionLocal
        session = SessionLocal()
        repo = AudioAnalyticsRepository(session)
        repo.finalize(analytics.id)
        results["finalize"] = "success"
        session.close()

    # Run concurrently
    t1 = threading.Thread(target=update)
    t2 = threading.Thread(target=finalize)

    t2.start()  # Finalize first
    time.sleep(0.01)  # Small delay
    t1.start()  # Then update

    t1.join()
    t2.join()

    # Finalize should succeed, update should fail (or vice versa depending on timing)
    assert results["finalize"] == "success"
    # Update might succeed or fail depending on race timing
```

### Cascade Delete Tests

```python
# tests/integration/audio/persistence/test_cascade_delete.py

def test_cascade_delete_exchange_deletes_analytics(db_session):
    """Deleting exchange cascades to analytics"""
    from app.persistence.models import InterviewExchange

    exchange = InterviewExchange(
        submission_id=1,
        question_snapshot={},
        stage="responding"
    )
    db_session.add(exchange)
    db_session.commit()

    repo = AudioAnalyticsRepository(db_session)
    analytics = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange.id,
        transcript="Test",
        confidence_score=0.9,
        speech_state="complete"
    ))

    # Delete exchange
    db_session.delete(exchange)
    db_session.commit()

    # Analytics should be deleted
    fetched = repo.get_by_exchange_id(exchange.id)
    assert fetched is None
```

### Transaction Rollback Tests

```python
# tests/integration/audio/persistence/test_transaction_rollback.py

def test_transaction_rollback_on_error(db_with_exchange):
    """Transaction rolled back on error"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    try:
        # Start transaction
        analytics = repo.create(AudioAnalyticsCreate(
            interview_exchange_id=exchange_id,
            transcript="Test",
            confidence_score=0.9,
            speech_state="complete"
        ))

        # Trigger error (e.g., invalid update)
        raise Exception("Simulated error")

        db_session.commit()
    except:
        db_session.rollback()

    # Analytics should not exist
    fetched = repo.get_by_exchange_id(exchange_id)
    assert fetched is None

def test_partial_rollback_within_transaction(db_with_exchange):
    """Savepoint rollback within transaction"""
    db_session, exchange_id = db_with_exchange

    repo = AudioAnalyticsRepository(db_session)

    # Create first analytics
    analytics1 = repo.create(AudioAnalyticsCreate(
        interview_exchange_id=exchange_id,
        transcript="First",
        confidence_score=0.9,
        speech_state="complete"
    ))

    # Savepoint
    db_session.begin_nested()

    try:
        # Attempt invalid operation
        repo.update(analytics1.id, AudioAnalyticsUpdate(confidence_score=1.5))  # Out of range
    except:
        db_session.rollback()  # Rollback to savepoint

    # First analytics should still exist
    fetched = repo.get_by_exchange_id(exchange_id)
    assert fetched is not None
    assert fetched.confidence_score == 0.9
```

---

## Test Coverage Requirements

- **Unit Tests:** >95% code coverage (persistence is critical)
- **Integration Tests:** All concurrent scenarios + cascade deletes
- **Constraint Tests:** All CHECK constraints enforced

---

## Running Tests

```bash
# Unit tests (requires test database)
pytest tests/unit/audio/persistence/ -v

# Integration tests (concurrency)
pytest tests/integration/audio/persistence/ -v

# Specific race condition test
pytest tests/integration/audio/persistence/test_concurrent_writes.py::test_concurrent_create_race_condition -v

# Coverage
pytest tests/audio/persistence/ --cov=app/audio/persistence --cov-report=html
```

---

## Critical Tests (Must Pass)

- [ ] UNIQUE constraint prevents duplicate analytics per exchange
- [ ] Cannot update finalized analytics (ImmutabilityError)
- [ ] Concurrent creates handled gracefully (one succeeds, one fails)
- [ ] Confidence score constraint enforced (0.0-1.0)
- [ ] Sentiment score constraint enforced (-1.0 to +1.0)
- [ ] Speech state constraint enforced (valid values only)
- [ ] Foreign key constraint enforced (exchange must exist)
- [ ] Cascade delete works (deleting exchange deletes analytics)
- [ ] Finalize is idempotent (can call multiple times)
- [ ] Transaction rollback works correctly

---

**End of Audio Persistence Module Testing Guide**
