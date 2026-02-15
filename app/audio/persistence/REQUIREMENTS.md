# Audio Persistence Module

## 1. Purpose

**Why this submodule exists:**

The Audio Persistence module is the **data layer** for audio analytics. It:

- Persists audio analytics to `audio_analytics` table
- Enforces **UNIQUE constraint** on `interview_exchange_id` (one analytics record per exchange)
- Manages transcript finalization (immutability after finalization)
- Provides repository pattern for clean separation from domain logic
- Handles concurrent writes safely (race condition: silence detected while evaluation starts)

**Critical responsibility:** Once a transcript is finalized and persisted, it becomes **immutable**. This prevents race conditions where audio module tries to update a transcript while evaluation module is reading it.

---

## 2. Owned Tables / Entities

### `audio_analytics`

```sql
CREATE TABLE audio_analytics (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INT NOT NULL UNIQUE,  -- One record per exchange

    -- Transcript data
    transcript TEXT NOT NULL,
    transcript_finalized BOOLEAN DEFAULT FALSE,
    confidence_score FLOAT NOT NULL,
    language_detected VARCHAR(10),

    -- Speech characteristics
    speech_state VARCHAR(20) NOT NULL,  -- 'complete' | 'incomplete' | 'continuing'
    speech_rate_wpm FLOAT,
    pause_duration_ms INT,
    long_pause_count INT DEFAULT 0,

    -- Behavioral signals
    filler_word_count INT DEFAULT 0,
    filler_rate FLOAT DEFAULT 0.0,
    sentiment_score FLOAT,
    hesitation_detected BOOLEAN DEFAULT FALSE,
    frustration_detected BOOLEAN DEFAULT FALSE,

    -- Audio quality
    audio_quality_score FLOAT,
    background_noise_detected BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMP,

    FOREIGN KEY (interview_exchange_id) REFERENCES interview_exchanges(id) ON DELETE CASCADE,
    CONSTRAINT speech_state_check CHECK (speech_state IN ('complete', 'incomplete', 'continuing')),
    CONSTRAINT confidence_range CHECK (confidence_score BETWEEN 0.0 AND 1.0),
    CONSTRAINT sentiment_range CHECK (sentiment_score BETWEEN -1.0 AND 1.0)
);

CREATE INDEX idx_audio_analytics_exchange ON audio_analytics(interview_exchange_id);
CREATE INDEX idx_audio_analytics_finalized ON audio_analytics(transcript_finalized);
```

---

## 3. Input Contracts

### AudioAnalyticsCreate

```python
@dataclass
class AudioAnalyticsCreate:
    interview_exchange_id: int              # REQUIRED: Bind to exchange
    transcript: str                         # REQUIRED: Full transcript
    confidence_score: float                 # REQUIRED: 0.0-1.0
    speech_state: Literal["complete", "incomplete", "continuing"]

    # Optional speech characteristics
    speech_rate_wpm: Optional[float] = None
    pause_duration_ms: Optional[int] = None
    long_pause_count: Optional[int] = 0

    # Optional behavioral signals
    filler_word_count: Optional[int] = 0
    filler_rate: Optional[float] = 0.0
    sentiment_score: Optional[float] = None
    hesitation_detected: Optional[bool] = False
    frustration_detected: Optional[bool] = False

    # Optional audio quality
    audio_quality_score: Optional[float] = None
    background_noise_detected: Optional[bool] = False
    language_detected: Optional[str] = None
```

### AudioAnalyticsUpdate

```python
@dataclass
class AudioAnalyticsUpdate:
    # Only updatable before finalization
    transcript: Optional[str] = None
    confidence_score: Optional[float] = None
    speech_state: Optional[str] = None
    speech_rate_wpm: Optional[float] = None
    # ... other optional fields
```

---

## 4. Output Contracts

### AudioAnalytics (ORM Model)

```python
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

class AudioAnalytics(Base):
    __tablename__ = "audio_analytics"

    id = Column(Integer, primary_key=True)
    interview_exchange_id = Column(Integer, ForeignKey("interview_exchanges.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Transcript
    transcript = Column(String, nullable=False)
    transcript_finalized = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=False)
    language_detected = Column(String(10))

    # Speech
    speech_state = Column(String(20), nullable=False)
    speech_rate_wpm = Column(Float)
    pause_duration_ms = Column(Integer)
    long_pause_count = Column(Integer, default=0)

    # Behavioral
    filler_word_count = Column(Integer, default=0)
    filler_rate = Column(Float, default=0.0)
    sentiment_score = Column(Float)
    hesitation_detected = Column(Boolean, default=False)
    frustration_detected = Column(Boolean, default=False)

    # Quality
    audio_quality_score = Column(Float)
    background_noise_detected = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finalized_at = Column(DateTime)

    # Relationships
    exchange = relationship("InterviewExchange", back_populates="audio_analytics")

    # Constraints
    __table_args__ = (
        CheckConstraint("speech_state IN ('complete', 'incomplete', 'continuing')", name="speech_state_check"),
        CheckConstraint("confidence_score BETWEEN 0.0 AND 1.0", name="confidence_range"),
        CheckConstraint("sentiment_score IS NULL OR sentiment_score BETWEEN -1.0 AND 1.0", name="sentiment_range"),
    )
```

---

## 5. Acceptance Criteria

### Functional Requirements

1. **Create Audio Analytics:**
   - Create new `audio_analytics` record for an exchange
   - Enforce UNIQUE constraint on `interview_exchange_id`
   - If duplicate, raise `IntegrityError`

2. **Update Audio Analytics:**
   - Update transcript and metrics **only if not finalized**
   - If finalized, raise `ImmutabilityError`

3. **Finalize Transcript:**
   - Mark transcript as finalized (`transcript_finalized=True`, `finalized_at=NOW()`)
   - After finalization, no updates allowed
   - Triggers exchange immutability (exchange cannot accept new audio)

4. **Query Analytics:**
   - Get analytics by `exchange_id`
   - Get all analytics for a submission (across all exchanges)
   - Filter by finalized status

5. **Delete Analytics:**
   - Cascade delete when exchange is deleted
   - Manual delete not allowed (preserve audit trail)

### Non-Functional Requirements

1. **Transactional Integrity:** All operations within database transactions
2. **Concurrent Writes:** Handle race condition where two threads try to create analytics for same exchange
3. **Performance:** Query by `exchange_id` must use index (<10ms p95)
4. **Audit Trail:** Preserve `created_at`, `updated_at`, `finalized_at` timestamps

---

## 6. Invariants & Constraints

### Must Hold

1. **One Analytics Per Exchange:** `interview_exchange_id` has UNIQUE constraint
2. **Finalized Transcripts Are Immutable:** Cannot update if `transcript_finalized=True`
3. **Confidence Score 0.0-1.0:** Enforced by CHECK constraint
4. **Sentiment Score -1.0 to +1.0:** Enforced by CHECK constraint
5. **Speech State Valid Values:** Only 'complete', 'incomplete', 'continuing'
6. **Exchange Must Exist:** Foreign key constraint to `interview_exchanges`

### Forbidden

- MUST NOT allow updates after finalization
- MUST NOT allow duplicate analytics for same exchange
- MUST NOT cascade delete from analytics to exchanges (delete direction is exchanges → analytics)
- MUST NOT expose raw SQL in repository methods (use ORM)

---

## 7. Repository Pattern

### AudioAnalyticsRepository

```python
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

class AudioAnalyticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
        """Create new audio analytics record"""
        try:
            analytics = AudioAnalytics(
                interview_exchange_id=data.interview_exchange_id,
                transcript=data.transcript,
                confidence_score=data.confidence_score,
                speech_state=data.speech_state,
                speech_rate_wpm=data.speech_rate_wpm,
                pause_duration_ms=data.pause_duration_ms,
                long_pause_count=data.long_pause_count,
                filler_word_count=data.filler_word_count,
                filler_rate=data.filler_rate,
                sentiment_score=data.sentiment_score,
                hesitation_detected=data.hesitation_detected,
                frustration_detected=data.frustration_detected,
                audio_quality_score=data.audio_quality_score,
                background_noise_detected=data.background_noise_detected,
                language_detected=data.language_detected
            )

            self.db.add(analytics)
            self.db.commit()
            self.db.refresh(analytics)

            return analytics

        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise DuplicateAnalyticsError(f"Analytics already exists for exchange_id={data.interview_exchange_id}")
            raise

    def get_by_exchange_id(self, exchange_id: int) -> Optional[AudioAnalytics]:
        """Get analytics for specific exchange"""
        return self.db.query(AudioAnalytics).filter(
            AudioAnalytics.interview_exchange_id == exchange_id
        ).first()

    def update(self, analytics_id: int, data: AudioAnalyticsUpdate) -> AudioAnalytics:
        """Update analytics (only if not finalized)"""
        analytics = self.db.query(AudioAnalytics).filter(AudioAnalytics.id == analytics_id).first()

        if not analytics:
            raise NotFoundError(f"Analytics not found: {analytics_id}")

        if analytics.transcript_finalized:
            raise ImmutabilityError(f"Cannot update finalized analytics: {analytics_id}")

        # Update fields
        for field, value in data.__dict__.items():
            if value is not None:
                setattr(analytics, field, value)

        analytics.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(analytics)

        return analytics

    def finalize(self, analytics_id: int) -> AudioAnalytics:
        """Mark transcript as finalized (immutable)"""
        analytics = self.db.query(AudioAnalytics).filter(AudioAnalytics.id == analytics_id).first()

        if not analytics:
            raise NotFoundError(f"Analytics not found: {analytics_id}")

        if analytics.transcript_finalized:
            # Already finalized, idempotent
            return analytics

        analytics.transcript_finalized = True
        analytics.finalized_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(analytics)

        return analytics

    def get_by_submission_id(self, submission_id: int) -> List[AudioAnalytics]:
        """Get all analytics for a submission (across all exchanges)"""
        return self.db.query(AudioAnalytics).join(
            InterviewExchange,
            AudioAnalytics.interview_exchange_id == InterviewExchange.id
        ).filter(
            InterviewExchange.submission_id == submission_id
        ).all()

    def is_finalized(self, exchange_id: int) -> bool:
        """Check if analytics for exchange is finalized"""
        analytics = self.get_by_exchange_id(exchange_id)
        return analytics.transcript_finalized if analytics else False
```

---

## 8. Concurrency & Race Conditions

### Race Condition: Duplicate Create

**Scenario:**

1. Thread A: Check if analytics exists for exchange_id=123 → Not found
2. Thread B: Check if analytics exists for exchange_id=123 → Not found
3. Thread A: Create analytics for exchange_id=123 → Success
4. Thread B: Create analytics for exchange_id=123 → **IntegrityError** (UNIQUE constraint)

**Solution:**

- Database enforces UNIQUE constraint
- Repository catches `IntegrityError` and raises domain-specific `DuplicateAnalyticsError`
- Caller can retry or fetch existing record

```python
def create_or_get(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
    """Create analytics or return existing"""
    try:
        return self.create(data)
    except DuplicateAnalyticsError:
        # Already exists, fetch and return
        return self.get_by_exchange_id(data.interview_exchange_id)
```

### Race Condition: Update During Finalization

**Scenario:**

1. Thread A: Start updating transcript
2. Thread B: Finalize transcript
3. Thread A: Commit update → Should fail

**Solution:**

- Use optimistic locking or SELECT FOR UPDATE
- Check `transcript_finalized` flag within transaction

```python
def update_with_lock(self, analytics_id: int, data: AudioAnalyticsUpdate) -> AudioAnalytics:
    """Update with row-level lock"""
    # SELECT FOR UPDATE prevents concurrent modifications
    analytics = self.db.query(AudioAnalytics).filter(
        AudioAnalytics.id == analytics_id
    ).with_for_update().first()

    if analytics.transcript_finalized:
        raise ImmutabilityError("Cannot update finalized analytics")

    # Update within locked transaction
    for field, value in data.__dict__.items():
        if value is not None:
            setattr(analytics, field, value)

    self.db.commit()
    return analytics
```

---

## 9. Integration Points

### Upstream (Callers)

1. **Parent Audio Module (`app.audio`):**
   - Creates `audio_analytics` after transcription + analysis
   - Finalizes analytics when silence detected and transcript complete

### Downstream (Dependencies)

1. **Database (PostgreSQL):**
   - SQLAlchemy ORM for queries
   - Enforces UNIQUE, CHECK, and FK constraints

2. **Interview Module (`app.interview`):**
   - Reads finalized transcripts for evaluation
   - Checks if transcript finalized before starting evaluation

---

## 10. Edge Cases to Handle

1. **Create Analytics for Non-Existent Exchange:**
   - Raises `ForeignKeyError` (exchange must exist)

2. **Finalize Already Finalized Analytics:**
   - Idempotent: No error, return existing record

3. **Update Non-Existent Analytics:**
   - Raises `NotFoundError`

4. **Delete Exchange with Analytics:**
   - Cascade delete: Analytics deleted automatically

5. **Null Sentiment Score:**
   - Allowed (sentiment analysis optional)
   - CHECK constraint allows NULL

6. **Confidence Score Out of Range:**
   - Raises `CheckConstraintViolation` (database enforces 0.0-1.0)

7. **Speech State Typo ("completed" instead of "complete"):**
   - Raises `CheckConstraintViolation` (database enforces valid values)

---

## 11. Example Usage

### Create Analytics

```python
from app.audio.persistence import AudioAnalyticsRepository

repo = AudioAnalyticsRepository(db_session)

analytics = repo.create(AudioAnalyticsCreate(
    interview_exchange_id=123,
    transcript="The answer is dynamic programming.",
    confidence_score=0.92,
    speech_state="complete",
    speech_rate_wpm=145,
    filler_word_count=2,
    sentiment_score=0.35
))

print(analytics.id)  # 1
print(analytics.transcript_finalized)  # False
```

### Update Analytics

```python
# Update before finalization
repo.update(
    analytics_id=1,
    data=AudioAnalyticsUpdate(
        transcript="The answer is definitely dynamic programming.",
        confidence_score=0.94
    )
)
```

### Finalize Analytics

```python
# Mark as finalized (immutable)
repo.finalize(analytics_id=1)

# Attempt to update after finalization
try:
    repo.update(analytics_id=1, data=AudioAnalyticsUpdate(transcript="New text"))
except ImmutabilityError:
    print("Cannot update finalized transcript")
```

### Query Analytics

```python
# Get by exchange ID
analytics = repo.get_by_exchange_id(exchange_id=123)

# Get all analytics for a submission
all_analytics = repo.get_by_submission_id(submission_id=1)

# Check if finalized
is_final = repo.is_finalized(exchange_id=123)
```

---

## 12. Configuration

### Environment Variables

```bash
# Database connection (inherited from main app)
DATABASE_URL=postgresql://user:pass@localhost/ai_interviewer

# Connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

---

## 13. Future Enhancements

1. **Versioning:**
   - Store transcript versions with timestamps
   - Allow rollback to previous version (before finalization)

2. **Soft Delete:**
   - Add `deleted_at` column for soft deletes
   - Preserve analytics even if exchange deleted

3. **Analytics Snapshots:**
   - Store raw audio metadata (segments, word timestamps) in JSONB column
   - Useful for re-analysis or debugging

4. **Multi-Tenancy Isolation:**
   - Add `tenant_id` column for row-level security
   - Prevent cross-tenant access

5. **Archive Old Analytics:**
   - Move finalized analytics >90 days old to cold storage
   - Reduce database size

6. **Analytics Aggregation:**
   - Pre-compute aggregate metrics (avg speech rate, avg sentiment) per candidate
   - Store in separate `candidate_audio_stats` table

---

**End of Audio Persistence Module Requirements**
