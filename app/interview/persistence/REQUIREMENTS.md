# Interview Persistence - Repositories & Database Operations

## 1. Purpose

The **Persistence** layer is responsible for:

- Data access layer for interview_submissions and interview_exchanges
- Repository pattern implementation (clean separation of concerns)
- Transaction management (atomic operations)
- Query optimization (indexes, eager loading)
- Row-level locking (concurrency safety)
- Enforcing database constraints (immutability, uniqueness)

**Critical responsibility:** This is the **data access boundary**. It must:

- Provide clean, testable API for database operations
- Enforce business rules at repository level (no UPDATE on exchanges)
- Handle transactions correctly (commit/rollback)
- Validate foreign key constraints
- Optimize query performance
- Prevent SQL injection

---

## 2. Repository Pattern

### Philosophy

**Repository = Collection-like interface over database operations.**

**Principles:**

1. **Encapsulation:** Hide SQLAlchemy/database details from business logic
2. **Testability:** Mock repository for unit tests (no real database)
3. **Single Responsibility:** Each repository owns one entity (or aggregate)
4. **Immutability enforcement:** Disallow forbidden operations (UPDATE exchanges)
5. **Transaction management:** Atomic operations with commit/rollback

---

### Base Repository

```python
from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Type, Optional, List

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """
    Base repository with common CRUD operations.
    """
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model

    def get_by_id(self, id: int) -> Optional[T]:
        """Fetch single record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Fetch all records with pagination."""
        return self.db.query(self.model).limit(limit).offset(offset).all()

    def create(self, entity: T) -> T:
        """Insert new record."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Delete record."""
        self.db.delete(entity)
        self.db.commit()

    def commit(self) -> None:
        """Commit transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Rollback transaction."""
        self.db.rollback()
```

---

## 3. Interview Submission Repository

### Purpose

Manage interview_submissions table (CRUD + state transitions).

---

### SubmissionRepository

```python
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

class SubmissionRepository(BaseRepository[InterviewSubmission]):
    def __init__(self, db: Session):
        super().__init__(db, InterviewSubmission)

    def get_by_id(
        self,
        submission_id: int,
        with_exchanges: bool = False
    ) -> Optional[InterviewSubmission]:
        """
        Fetch submission by ID.

        Args:
            with_exchanges: If True, eager load exchanges
        """
        query = self.db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        )

        if with_exchanges:
            query = query.options(
                joinedload(InterviewSubmission.exchanges)
            )

        return query.first()

    def get_by_interview_and_candidate(
        self,
        interview_id: int,
        candidate_id: int
    ) -> Optional[InterviewSubmission]:
        """
        Fetch submission by interview_id + candidate_id.

        Used for idempotency check (start interview).
        """
        return self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.interview_id == interview_id,
                InterviewSubmission.candidate_id == candidate_id
            )
        ).first()

    def list_by_candidate(
        self,
        candidate_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[InterviewSubmission]:
        """
        Fetch submissions for candidate, optionally filtered by status.
        """
        query = self.db.query(InterviewSubmission).filter(
            InterviewSubmission.candidate_id == candidate_id
        )

        if status:
            query = query.filter(InterviewSubmission.submission_status == status)

        return query.order_by(
            InterviewSubmission.created_at.desc()
        ).limit(limit).all()

    def list_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[InterviewSubmission]:
        """
        Fetch submissions by status.

        Used for batch operations (e.g., timeout monitor).
        """
        return self.db.query(InterviewSubmission).filter(
            InterviewSubmission.submission_status == status
        ).limit(limit).all()

    def list_expired(
        self,
        limit: int = 100
    ) -> List[InterviewSubmission]:
        """
        Fetch submissions that are expired (in_progress but past expires_at).

        Used by timeout monitor job.
        """
        now = datetime.utcnow()
        return self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.submission_status == 'in_progress',
                InterviewSubmission.expires_at < now
            )
        ).limit(limit).all()

    def create_submission(
        self,
        interview_id: int,
        candidate_id: int,
        template_id: int,
        template_structure_snapshot: dict
    ) -> InterviewSubmission:
        """
        Create new interview submission.

        Sets:
        - submission_status = 'pending'
        - consent_accepted = True (checked before calling)
        - template_structure_snapshot (frozen)
        """
        submission = InterviewSubmission(
            interview_id=interview_id,
            candidate_id=candidate_id,
            template_id=template_id,
            template_structure_snapshot=template_structure_snapshot,
            submission_status='pending',
            consent_accepted=True,
            created_at=datetime.utcnow()
        )
        return self.create(submission)

    def update_status(
        self,
        submission_id: int,
        new_status: str,
        expected_old_status: Optional[str] = None
    ) -> int:
        """
        Update submission status with precondition check.

        Args:
            submission_id: ID of submission
            new_status: New status value
            expected_old_status: If provided, only update if current status matches

        Returns:
            Number of rows updated (0 or 1)

        Implementation:
            UPDATE interview_submissions
            SET submission_status = new_status
            WHERE id = submission_id
              AND (expected_old_status IS NULL OR submission_status = expected_old_status)
        """
        query = self.db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        )

        if expected_old_status:
            query = query.filter(
                InterviewSubmission.submission_status == expected_old_status
            )

        rows_updated = query.update(
            {InterviewSubmission.submission_status: new_status},
            synchronize_session=False
        )

        self.db.commit()
        return rows_updated

    def start_interview(
        self,
        submission_id: int,
        duration_minutes: int
    ) -> int:
        """
        Transition submission from 'pending' to 'in_progress'.

        Sets:
        - submission_status = 'in_progress'
        - started_at = NOW()
        - expires_at = NOW() + duration_minutes

        Returns:
            Number of rows updated (0 if already started, 1 if transitioned)
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=duration_minutes)

        query = self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.id == submission_id,
                InterviewSubmission.submission_status == 'pending'
            )
        )

        rows_updated = query.update(
            {
                InterviewSubmission.submission_status: 'in_progress',
                InterviewSubmission.started_at: now,
                InterviewSubmission.expires_at: expires_at
            },
            synchronize_session=False
        )

        self.db.commit()
        return rows_updated

    def complete_interview(
        self,
        submission_id: int
    ) -> int:
        """
        Transition submission from 'in_progress' to 'completed'.

        Sets:
        - submission_status = 'completed'
        - submitted_at = NOW()

        Returns:
            Number of rows updated (0 if not in_progress, 1 if transitioned)
        """
        now = datetime.utcnow()

        query = self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.id == submission_id,
                InterviewSubmission.submission_status == 'in_progress'
            )
        )

        rows_updated = query.update(
            {
                InterviewSubmission.submission_status: 'completed',
                InterviewSubmission.submitted_at: now
            },
            synchronize_session=False
        )

        self.db.commit()
        return rows_updated

    def timeout_expired(
        self,
        submission_id: int
    ) -> int:
        """
        Transition submission from 'in_progress' to 'expired'.

        Called by timeout monitor background job.

        Returns:
            Number of rows updated (0 if not in_progress, 1 if transitioned)
        """
        now = datetime.utcnow()

        query = self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.id == submission_id,
                InterviewSubmission.submission_status == 'in_progress',
                InterviewSubmission.expires_at < now
            )
        )

        rows_updated = query.update(
            {
                InterviewSubmission.submission_status: 'expired',
                InterviewSubmission.submitted_at: now
            },
            synchronize_session=False
        )

        self.db.commit()
        return rows_updated

    def cancel_interview(
        self,
        submission_id: int,
        cancelled_by_user_id: int,
        cancellation_reason: str
    ) -> int:
        """
        Transition submission to 'cancelled' (admin action).

        Returns:
            Number of rows updated
        """
        now = datetime.utcnow()

        query = self.db.query(InterviewSubmission).filter(
            and_(
                InterviewSubmission.id == submission_id,
                InterviewSubmission.submission_status.in_(['pending', 'in_progress'])
            )
        )

        rows_updated = query.update(
            {
                InterviewSubmission.submission_status: 'cancelled',
                InterviewSubmission.submitted_at: now
                # Cancellation metadata stored separately (audit log)
            },
            synchronize_session=False
        )

        self.db.commit()
        return rows_updated

    def update_progress(
        self,
        submission_id: int,
        current_sequence: int
    ) -> None:
        """
        Update current_exchange_sequence after exchange creation.
        """
        submission = self.get_by_id(submission_id)
        if submission:
            submission.current_exchange_sequence = current_sequence
            self.db.commit()

    def lock_for_update(
        self,
        submission_id: int
    ) -> Optional[InterviewSubmission]:
        """
        Fetch submission with row-level lock (SELECT FOR UPDATE).

        Used for critical sections requiring exclusive access.
        """
        return self.db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        ).with_for_update().first()
```

---

## 4. Interview Exchange Repository

### Purpose

Manage interview_exchanges table (CREATE only, NO UPDATE).

---

### ExchangeRepository

```python
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

class ExchangeRepository(BaseRepository[InterviewExchange]):
    def __init__(self, db: Session):
        super().__init__(db, InterviewExchange)

    def get_by_id(
        self,
        exchange_id: int
    ) -> Optional[InterviewExchange]:
        """Fetch exchange by ID."""
        return self.db.query(InterviewExchange).filter(
            InterviewExchange.id == exchange_id
        ).first()

    def list_by_submission(
        self,
        submission_id: int,
        order_by: str = "sequence_order"
    ) -> List[InterviewExchange]:
        """
        Fetch all exchanges for submission, ordered by sequence.
        """
        return self.db.query(InterviewExchange).filter(
            InterviewExchange.interview_submission_id == submission_id
        ).order_by(InterviewExchange.sequence_order).all()

    def list_by_section(
        self,
        submission_id: int,
        section_name: str
    ) -> List[InterviewExchange]:
        """
        Fetch exchanges for specific section (e.g., 'coding').
        """
        return self.db.query(InterviewExchange).filter(
            and_(
                InterviewExchange.interview_submission_id == submission_id,
                InterviewExchange.section_name == section_name
            )
        ).order_by(InterviewExchange.sequence_order).all()

    def get_by_sequence(
        self,
        submission_id: int,
        sequence_order: int
    ) -> Optional[InterviewExchange]:
        """
        Fetch exchange by submission_id + sequence_order.

        Used for idempotency checks.
        """
        return self.db.query(InterviewExchange).filter(
            and_(
                InterviewExchange.interview_submission_id == submission_id,
                InterviewExchange.sequence_order == sequence_order
            )
        ).first()

    def exists_for_sequence(
        self,
        submission_id: int,
        sequence_order: int
    ) -> bool:
        """
        Check if exchange exists for given sequence.

        Used for race condition handling.
        """
        return self.db.query(
            self.db.query(InterviewExchange)
            .filter(
                and_(
                    InterviewExchange.interview_submission_id == submission_id,
                    InterviewExchange.sequence_order == sequence_order
                )
            )
            .exists()
        ).scalar()

    def exists_for_question(
        self,
        submission_id: int,
        question_id: int
    ) -> bool:
        """
        Check if exchange exists for given question.

        Enforces UNIQUE(submission_id, question_id).
        """
        return self.db.query(
            self.db.query(InterviewExchange)
            .filter(
                and_(
                    InterviewExchange.interview_submission_id == submission_id,
                    InterviewExchange.question_id == question_id
                )
            )
            .exists()
        ).scalar()

    def count_by_submission(
        self,
        submission_id: int
    ) -> int:
        """
        Count total exchanges for submission.
        """
        return self.db.query(InterviewExchange).filter(
            InterviewExchange.interview_submission_id == submission_id
        ).count()

    def create_exchange(
        self,
        submission_id: int,
        sequence_order: int,
        question_id: int,
        question_text: str,
        question_type: str,
        question_difficulty: str,
        section_name: str,
        expected_answer: Optional[str],
        response_text: Optional[str],
        response_code: Optional[str],
        response_language: Optional[str],
        response_time_ms: int,
        code_submission_id: Optional[int],
        audio_recording_id: Optional[int],
        ai_followup_message: Optional[str] = None
    ) -> InterviewExchange:
        """
        Create immutable exchange with complete snapshot.

        Validation performed before calling this method:
        - Submission exists and in_progress
        - Sequence order valid (no gaps, no duplicates)
        - Response completeness validated

        Raises:
            IntegrityError: UNIQUE constraint violation (duplicate sequence/question)
        """
        exchange = InterviewExchange(
            interview_submission_id=submission_id,
            sequence_order=sequence_order,
            question_id=question_id,
            question_text=question_text,
            question_type=question_type,
            question_difficulty=question_difficulty,
            expected_answer=expected_answer,
            section_name=section_name,
            response_text=response_text,
            response_code=response_code,
            response_language=response_language,
            response_time_ms=response_time_ms,
            code_submission_id=code_submission_id,
            audio_recording_id=audio_recording_id,
            ai_followup_message=ai_followup_message,
            responded_at=datetime.utcnow()
        )

        return self.create(exchange)

    def update(self, exchange_id: int, updates: dict) -> None:
        """
        UPDATE IS FORBIDDEN.

        Exchanges are immutable after creation.

        Raises:
            ImmutabilityViolationError
        """
        raise ImmutabilityViolationError(
            "interview_exchanges are immutable. Cannot update after creation."
        )

    def delete(self, exchange_id: int) -> None:
        """
        DELETE IS FORBIDDEN (except CASCADE).

        Exchanges only deleted via CASCADE when submission deleted.

        Raises:
            ImmutabilityViolationError
        """
        raise ImmutabilityViolationError(
            "interview_exchanges cannot be deleted individually. "
            "Only deleted via CASCADE when submission deleted."
        )
```

---

## 5. Transaction Patterns

### Atomic State Transition + Redis Update

```python
from sqlalchemy.orm import Session
from redis import Redis

def start_interview_atomic(
    db: Session,
    redis: Redis,
    submission_id: int,
    duration_minutes: int
) -> InterviewSubmission:
    """
    Atomic start interview: DB update + Redis sync.

    Steps:
    1. Update submission status to 'in_progress'
    2. Update Redis session state
    3. Commit transaction

    Rollback on error.
    """
    submission_repo = SubmissionRepository(db)

    try:
        # Step 1: Update database
        rows_updated = submission_repo.start_interview(submission_id, duration_minutes)

        if rows_updated == 0:
            # Already started (idempotent)
            submission = submission_repo.get_by_id(submission_id)
            if submission.submission_status == 'in_progress':
                return submission
            else:
                raise InvalidStateError(
                    f"Cannot start interview in '{submission.submission_status}' state"
                )

        # Step 2: Update Redis
        submission = submission_repo.get_by_id(submission_id)
        redis.hset(
            f"interview_session:{submission_id}",
            mapping={
                "status": "in_progress",
                "started_at": submission.started_at.isoformat(),
                "expires_at": submission.expires_at.isoformat(),
                "current_sequence": 0
            }
        )
        redis.expire(f"interview_session:{submission_id}", duration_minutes * 60 + 300)

        return submission

    except Exception as e:
        db.rollback()
        raise
```

---

### Atomic Exchange Creation + Progress Update

```python
def create_exchange_atomic(
    db: Session,
    redis: Redis,
    exchange_data: dict,
    submission_id: int
) -> InterviewExchange:
    """
    Atomic exchange creation: Insert exchange + update submission progress.

    Steps:
    1. Create exchange
    2. Update submission.current_exchange_sequence
    3. Update Redis session progress
    4. Commit transaction

    Rollback on error.
    """
    exchange_repo = ExchangeRepository(db)
    submission_repo = SubmissionRepository(db)

    try:
        # Step 1: Create exchange
        exchange = exchange_repo.create_exchange(**exchange_data)

        # Step 2: Update submission progress
        submission_repo.update_progress(
            submission_id,
            exchange.sequence_order
        )

        # Step 3: Update Redis
        redis.hset(
            f"interview_session:{submission_id}",
            "current_sequence",
            exchange.sequence_order
        )

        return exchange

    except Exception as e:
        db.rollback()
        raise
```

---

## 6. Row-Level Locking

### When to Use SELECT FOR UPDATE

**Use case:** Prevent concurrent state transitions.

**Example: Start interview**

```python
def start_interview_with_lock(
    db: Session,
    submission_id: int
) -> InterviewSubmission:
    """
    Start interview with row-level lock.

    Prevents race condition:
    - Two concurrent requests to start same interview
    - First acquires lock, transitions state
    - Second waits for lock, finds state already changed
    """
    submission_repo = SubmissionRepository(db)

    # Acquire lock
    submission = submission_repo.lock_for_update(submission_id)

    if not submission:
        raise NotFoundError(f"Submission {submission_id} not found")

    if submission.submission_status != 'pending':
        raise InvalidStateError(f"Cannot start interview in '{submission.submission_status}' state")

    # Update state (lock held until commit)
    submission.submission_status = 'in_progress'
    submission.started_at = datetime.utcnow()
    submission.expires_at = submission.started_at + timedelta(minutes=60)

    db.commit()
    return submission
```

---

## 7. Query Optimization

### Eager Loading

**Problem:** N+1 queries when fetching submission + exchanges.

**Solution:** Use `joinedload` or `selectinload`.

```python
from sqlalchemy.orm import joinedload

def get_submission_with_exchanges(
    db: Session,
    submission_id: int
) -> Optional[InterviewSubmission]:
    """
    Fetch submission with exchanges in single query.
    """
    return db.query(InterviewSubmission).filter(
        InterviewSubmission.id == submission_id
    ).options(
        joinedload(InterviewSubmission.exchanges)
    ).first()
```

---

### Indexes

**Required indexes:**

```sql
-- Submissions
CREATE INDEX idx_submissions_candidate ON interview_submissions(candidate_id);
CREATE INDEX idx_submissions_status ON interview_submissions(submission_status);
CREATE INDEX idx_submissions_expired ON interview_submissions(submission_status, expires_at);

-- Exchanges
CREATE INDEX idx_exchanges_submission ON interview_exchanges(interview_submission_id);
CREATE INDEX idx_exchanges_sequence ON interview_exchanges(interview_submission_id, sequence_order);
CREATE INDEX idx_exchanges_question ON interview_exchanges(question_id);
```

---

## 8. Error Handling

### Custom Exceptions

```python
class RepositoryError(Exception):
    """Base exception for repository errors."""
    pass

class NotFoundError(RepositoryError):
    """Entity not found."""
    pass

class InvalidStateError(RepositoryError):
    """Invalid state transition."""
    pass

class ImmutabilityViolationError(RepositoryError):
    """Attempted to modify immutable entity."""
    pass

class SequenceGapError(RepositoryError):
    """Gap in exchange sequence."""
    pass

class DuplicateSequenceError(RepositoryError):
    """Duplicate exchange sequence."""
    pass
```

---

### Exception Mapping

```python
from sqlalchemy.exc import IntegrityError

def handle_integrity_error(e: IntegrityError) -> RepositoryError:
    """
    Map SQLAlchemy IntegrityError to domain exception.
    """
    error_message = str(e.orig)

    if "unique constraint" in error_message.lower():
        if "submission_id, sequence_order" in error_message:
            return DuplicateSequenceError("Exchange already exists for this sequence")
        elif "submission_id, question_id" in error_message:
            return DuplicateSequenceError("Question already answered in this interview")

    elif "foreign key constraint" in error_message.lower():
        return NotFoundError("Referenced entity does not exist")

    return RepositoryError(f"Database integrity error: {error_message}")
```

---

## 9. Testing Requirements

### Unit Tests

1. **Create submission:** Valid data → submission created
2. **Start interview:** Pending → in_progress (atomic)
3. **Double start:** Second request → idempotent (0 rows updated)
4. **Complete interview:** In_progress → completed
5. **Timeout expired:** Expired submission → status updated
6. **Create exchange:** Valid data → exchange created
7. **Update exchange:** Raises ImmutabilityViolationError
8. **Delete exchange:** Raises ImmutabilityViolationError
9. **Duplicate sequence:** IntegrityError raised
10. **Sequence gap:** SequenceGapError raised

### Integration Tests

1. **Atomic state transition:** DB + Redis updated together, rollback on error
2. **Row-level locking:** Concurrent start requests, only one succeeds
3. **Eager loading:** Submission with exchanges fetched in single query (no N+1)
4. **Expired submission query:** list_expired() returns only expired submissions

---

## 10. Critical Risks

1. **No transaction management:** Partial updates (DB updated, Redis failed)
2. **No row-level locking:** Race conditions on state transitions
3. **N+1 queries:** Performance degradation with large result sets
4. **Missing indexes:** Slow queries on status/candidate lookups
5. **Allow UPDATE on exchanges:** Immutability violated
6. **No error mapping:** Generic database errors leak to API layer

---

## 11. Configuration

```python
from pydantic import BaseModel

class RepositoryConfig(BaseModel):
    """Repository configuration."""

    # Connection pool
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Query optimization
    default_page_size: int = 50
    max_page_size: int = 100
    enable_query_logging: bool = False

    # Transaction management
    autocommit: bool = False
    autoflush: bool = True
    expire_on_commit: bool = True
```

---

## 12. Future Enhancements

1. **Soft delete:** Mark submissions as deleted (deleted_at timestamp)
2. **Archiving:** Move old submissions to archive table (S3)
3. **Read replicas:** Route read queries to replica database
4. **Query caching:** Cache frequently accessed submissions (Redis)
5. **Bulk operations:** Batch insert/update for performance
6. **Audit logging:** Track all repository operations (who, when, what)

---

**End of Interview Persistence Requirements**
