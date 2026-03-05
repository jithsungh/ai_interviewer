# Audio Persistence — Human Testing Guide

**Module:** `app/audio/persistence`  
**Purpose:** Verify the audio analytics repository (ORM, CRUD, finalization, immutability)  
**Prerequisites:** Running PostgreSQL with schema + migration applied  

---

## Quick Start

### 1. Apply Migration

```bash
psql -U postgres -d interviewer -f \
  app/persistence/postgres/migrations/DEV-49_audio-persistence-schema-additions.sql
```

### 2. Verify Migration

```sql
-- Check new columns exist
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'audio_analytics'
ORDER BY ordinal_position;
```

Expected new columns: `transcript_finalized`, `language_detected`, `speech_state`, `pause_duration_ms`, `long_pause_count`, `filler_rate`, `hesitation_detected`, `frustration_detected`, `audio_quality_score`, `background_noise_detected`, `updated_at`, `finalized_at`.

### 3. Verify Constraints

```sql
-- Check constraints exist
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name LIKE '%audio_analytics%';
```

Expected constraints:
- `chk_audio_analytics_speech_state` — `speech_state IN ('complete', 'partial', 'silence')`
- `chk_audio_analytics_confidence` — `confidence_score BETWEEN 0 AND 1`
- `chk_audio_analytics_sentiment` — `sentiment_score BETWEEN -1 AND 1`

---

## Repository Testing (Python REPL)

Start a Python session with the app context:

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
python
```

### Test 1: Create Analytics

```python
from app.persistence.postgres import init_postgres
from app.persistence.postgres.session import init_session_factory, get_session_factory
from app.config.settings import get_settings

settings = get_settings()
init_postgres(settings.database)
init_session_factory()

from app.audio.persistence.repository import SqlAudioAnalyticsRepository
from app.audio.persistence.entities import AudioAnalyticsCreate, AudioAnalyticsUpdate

session = get_session_factory()()

repo = SqlAudioAnalyticsRepository(session)

# Use an existing exchange_id from your database
EXCHANGE_ID = 1  # <-- replace with a real exchange ID

dto = AudioAnalyticsCreate(
    interview_exchange_id=EXCHANGE_ID,
    transcript="The candidate discussed binary search approach.",
    confidence_score=0.95,
    speech_rate_wpm=140,
    filler_word_count=2,
    sentiment_score=0.3,
    speech_state="complete",
)

entity = repo.create(dto)
session.commit()
print(f"Created analytics ID: {entity.id}")
print(f"Finalized: {entity.transcript_finalized}")
```

### Test 2: Duplicate Rejection

```python
from app.audio.persistence.exceptions import DuplicateAnalyticsError

try:
    repo.create(dto)  # same exchange_id
    session.commit()
    print("ERROR: Should have raised DuplicateAnalyticsError!")
except DuplicateAnalyticsError as e:
    print(f"Correctly raised: {e}")
```

### Test 3: create_or_get (Idempotent)

```python
result = repo.create_or_get(dto)
print(f"Got existing ID: {result.id}")  # Same as Test 1
```

### Test 4: Update

```python
update_dto = AudioAnalyticsUpdate(
    transcript="Updated transcript with more detail.",
    filler_word_count=5,
)
updated = repo.update(entity.id, update_dto)
session.commit()
print(f"Updated transcript: {updated.transcript}")
print(f"Updated filler_word_count: {updated.filler_word_count}")
```

### Test 5: Finalize

```python
finalized = repo.finalize(entity.id)
session.commit()
print(f"Finalized: {finalized.transcript_finalized}")
print(f"Finalized at: {finalized.finalized_at}")
```

### Test 6: Immutability After Finalize

```python
from app.audio.persistence.exceptions import ImmutabilityError

try:
    repo.update(entity.id, AudioAnalyticsUpdate(transcript="Should fail"))
    print("ERROR: Should have raised ImmutabilityError!")
except ImmutabilityError as e:
    print(f"Correctly raised: {e}")
```

### Test 7: Finalize Idempotent

```python
second = repo.finalize(entity.id)
print(f"Still finalized: {second.transcript_finalized}")
print(f"Same finalized_at: {second.finalized_at == finalized.finalized_at}")
```

### Test 8: Get By Submission ID

```python
# Get the interview_submission_id for this exchange
from sqlalchemy import text
row = session.execute(
    text("SELECT interview_submission_id FROM interview_exchanges WHERE id = :eid"),
    {"eid": EXCHANGE_ID},
).fetchone()
SUB_ID = row[0]

results = repo.get_by_submission_id(SUB_ID)
print(f"Found {len(results)} analytics for submission {SUB_ID}")
```

### Cleanup

```python
session.close()
```

---

## CHECK Constraint Verification

### speech_state constraint

```sql
INSERT INTO audio_analytics (interview_exchange_id, transcript, speech_state)
VALUES (99999, 'test', 'invalid_state');
-- Expected: CHECK constraint violation
```

### confidence_score range

```sql
UPDATE audio_analytics SET confidence_score = 1.5 WHERE id = 1;
-- Expected: CHECK constraint violation (must be 0..1)
```

### sentiment_score range

```sql
UPDATE audio_analytics SET sentiment_score = -2.0 WHERE id = 1;
-- Expected: CHECK constraint violation (must be -1..1)
```

---

## Automated Tests

### Unit Tests

```bash
pytest tests/unit/audio/persistence/ -v
```

### Integration Tests (requires PostgreSQL)

```bash
pytest tests/integration/audio/persistence/ -v
```

---

## Rollback

```bash
psql -U postgres -d interviewer -f \
  app/persistence/postgres/migrations/DEV-49_audio-persistence-schema-additions_rollback.sql
```

This drops all 12 added columns, the 3 CHECK constraints, and the finalized index.
