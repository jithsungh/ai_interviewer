# Proctoring Persistence - Event Storage & Retrieval

## 1. Purpose

The **persistence** subdirectory handles:

- Storing proctoring events immutably in PostgreSQL
- Preserving event ordering and timestamps
- Efficient retrieval by submission_id, severity, time range
- Supporting retention policy enforcement
- Ensuring multi-tenant isolation

**Critical responsibility:** Immutable audit trail with efficient queries for risk computation and review.

---

## 2. Responsibilities

### 2.1 Event Storage

**Provides:**

- Insert proctoring events into database
- Preserve event ordering (sequence guarantees)
- Ensure immutability (no updates after creation)
- Support batch insertions for efficiency

**Must:**

- Accept enriched events (with severity and weight from rules)
- Store all metadata in JSONB (flexible schema)
- Return inserted event IDs for reference
- Handle duplicate event attempts gracefully (idempotent)

**Must NOT:**

- Allow UPDATE operations on proctoring_events (immutable audit trail)
- Allow DELETE operations (use soft delete for retention)

---

### 2.2 Event Retrieval

**Provides:**

- Query events by submission_id (most common)
- Filter by severity, event_type, time range
- Support pagination for large result sets
- Efficient aggregation for risk computation

**Must:**

- Enforce tenant isolation (organization_id scoping)
- Return events in chronological order (occurred_at ASC)
- Support efficient queries (indexed columns)

---

### 2.3 Retention Policy Enforcement

**Provides:**

- Auto-delete events older than retention period
- Generate deletion audit reports
- Preserve aggregated risk scores (even after event deletion)

**Must:**

- Support configurable retention per tenant
- Run deletion as background job (non-blocking)
- Log deletion actions with counts

---

## 3. Database Schema

### 3.1 Table: proctoring_events

**Schema (from schema.sql):**

```sql
CREATE TABLE proctoring_events (
    id SERIAL PRIMARY KEY,
    interview_submission_id INTEGER NOT NULL REFERENCES interview_submissions(id),
    event_type VARCHAR(50) NOT NULL,
    severity proctoring_severity NOT NULL, -- low, medium, high, critical
    risk_weight NUMERIC(5, 2) NOT NULL,
    evidence JSONB,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_proctoring_events_submission
    ON proctoring_events(interview_submission_id);
CREATE INDEX idx_proctoring_events_severity
    ON proctoring_events(severity);
CREATE INDEX idx_proctoring_events_occurred
    ON proctoring_events(occurred_at);
```

**Field descriptions:**

- `id`: Auto-incrementing primary key
- `interview_submission_id`: Foreign key to interview_submissions (tenant-scoped)
- `event_type`: Event category (tab_switch, multiple_faces, etc.)
- `severity`: Enum (low, medium, high, critical) from rules
- `risk_weight`: Numeric weight contributing to total risk (from rules)
- `evidence`: JSONB metadata (device info, detection confidence, frame number, etc.)
- `occurred_at`: When event happened (client-reported or server-detected)
- `created_at`: When event was recorded in database (server time)

---

### 3.2 Indexes

**Primary index:**

- `interview_submission_id`: Most queries filter by submission

**Secondary indexes:**

- `severity`: Filter for high/critical events in review queue
- `occurred_at`: Time range queries, ordering

**Composite index (optional, for performance):**

```sql
CREATE INDEX idx_proctoring_events_submission_occurred
    ON proctoring_events(interview_submission_id, occurred_at);
```

Benefits:

- Fast retrieval of all events for submission in chronological order
- Efficient risk score recomputation

---

## 4. Repository Interface

### 4.1 ProctoringEventRepository

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ProctoringEventEntity:
    """Domain entity for proctoring event."""
    id: Optional[int]
    interview_submission_id: int
    event_type: str
    severity: str
    risk_weight: float
    evidence: dict
    occurred_at: datetime
    created_at: Optional[datetime]

class ProctoringEventRepository(ABC):
    """Abstract repository for proctoring events."""

    @abstractmethod
    def create(self, event: ProctoringEventEntity) -> ProctoringEventEntity:
        """Insert single event."""
        pass

    @abstractmethod
    def create_batch(self, events: list[ProctoringEventEntity]) -> list[int]:
        """Insert multiple events efficiently."""
        pass

    @abstractmethod
    def get_by_submission(
        self,
        submission_id: int,
        severity_filter: Optional[str] = None,
        time_range: Optional[tuple[datetime, datetime]] = None
    ) -> list[ProctoringEventEntity]:
        """Get all events for submission (most common query)."""
        pass

    @abstractmethod
    def count_by_submission(
        self,
        submission_id: int,
        event_type: Optional[str] = None
    ) -> int:
        """Count events for submission (for clustering detection)."""
        pass

    @abstractmethod
    def get_events_in_window(
        self,
        submission_id: int,
        event_type: str,
        window_start: datetime,
        window_end: datetime
    ) -> list[ProctoringEventEntity]:
        """Get events in time window (for clustering detection)."""
        pass

    @abstractmethod
    def delete_older_than(
        self,
        retention_date: datetime,
        organization_id: int
    ) -> int:
        """Delete events older than retention date (for retention policy)."""
        pass
```

---

## 5. Implementation

### 5.1 Create Event

**Method:** `create(event: ProctoringEventEntity) -> ProctoringEventEntity`

**SQL:**

```sql
INSERT INTO proctoring_events (
    interview_submission_id,
    event_type,
    severity,
    risk_weight,
    evidence,
    occurred_at
) VALUES (
    :submission_id,
    :event_type,
    :severity,
    :risk_weight,
    :evidence,
    :occurred_at
)
RETURNING id, created_at;
```

**Implementation:**

```python
def create(self, event: ProctoringEventEntity) -> ProctoringEventEntity:
    """Insert single proctoring event."""

    result = self.db.execute(
        """
        INSERT INTO proctoring_events (
            interview_submission_id,
            event_type,
            severity,
            risk_weight,
            evidence,
            occurred_at
        ) VALUES (
            :submission_id,
            :event_type,
            :severity,
            :risk_weight,
            :evidence::jsonb,
            :occurred_at
        )
        RETURNING id, created_at
        """,
        {
            "submission_id": event.interview_submission_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "risk_weight": event.risk_weight,
            "evidence": json.dumps(event.evidence),
            "occurred_at": event.occurred_at
        }
    ).fetchone()

    event.id = result.id
    event.created_at = result.created_at

    self.db.commit()
    return event
```

---

### 5.2 Batch Insert

**Method:** `create_batch(events: list[ProctoringEventEntity]) -> list[int]`

**SQL (PostgreSQL-specific, efficient):**

```sql
INSERT INTO proctoring_events (
    interview_submission_id,
    event_type,
    severity,
    risk_weight,
    evidence,
    occurred_at
) VALUES
    (:submission_id_1, :event_type_1, :severity_1, :risk_weight_1, :evidence_1, :occurred_at_1),
    (:submission_id_2, :event_type_2, :severity_2, :risk_weight_2, :evidence_2, :occurred_at_2),
    ...
RETURNING id;
```

**Implementation:**

```python
def create_batch(self, events: list[ProctoringEventEntity]) -> list[int]:
    """Insert multiple events efficiently."""

    if not events:
        return []

    # Use executemany for batch insert
    values = [
        {
            "submission_id": e.interview_submission_id,
            "event_type": e.event_type,
            "severity": e.severity,
            "risk_weight": e.risk_weight,
            "evidence": json.dumps(e.evidence),
            "occurred_at": e.occurred_at
        }
        for e in events
    ]

    result = self.db.execute(
        """
        INSERT INTO proctoring_events (
            interview_submission_id,
            event_type,
            severity,
            risk_weight,
            evidence,
            occurred_at
        ) VALUES (
            :submission_id,
            :event_type,
            :severity,
            :risk_weight,
            :evidence::jsonb,
            :occurred_at
        )
        RETURNING id
        """,
        values
    )

    event_ids = [row.id for row in result.fetchall()]
    self.db.commit()

    return event_ids
```

---

### 5.3 Get Events by Submission

**Method:** `get_by_submission(submission_id, severity_filter, time_range)`

**SQL:**

```sql
SELECT * FROM proctoring_events
WHERE interview_submission_id = :submission_id
  AND (:severity_filter IS NULL OR severity = :severity_filter)
  AND (:start_time IS NULL OR occurred_at >= :start_time)
  AND (:end_time IS NULL OR occurred_at <= :end_time)
ORDER BY occurred_at ASC;
```

**Implementation:**

```python
def get_by_submission(
    self,
    submission_id: int,
    severity_filter: Optional[str] = None,
    time_range: Optional[tuple[datetime, datetime]] = None
) -> list[ProctoringEventEntity]:
    """Get all events for submission with optional filters."""

    query = """
        SELECT * FROM proctoring_events
        WHERE interview_submission_id = :submission_id
    """

    params = {"submission_id": submission_id}

    if severity_filter:
        query += " AND severity = :severity"
        params["severity"] = severity_filter

    if time_range:
        query += " AND occurred_at >= :start_time AND occurred_at <= :end_time"
        params["start_time"] = time_range[0]
        params["end_time"] = time_range[1]

    query += " ORDER BY occurred_at ASC"

    results = self.db.execute(query, params).fetchall()

    return [self._map_to_entity(row) for row in results]
```

---

### 5.4 Count Events (for Clustering Detection)

**Method:** `count_by_submission(submission_id, event_type)`

**SQL:**

```sql
SELECT COUNT(*) FROM proctoring_events
WHERE interview_submission_id = :submission_id
  AND (:event_type IS NULL OR event_type = :event_type);
```

**Implementation:**

```python
def count_by_submission(
    self,
    submission_id: int,
    event_type: Optional[str] = None
) -> int:
    """Count events for submission (optionally filtered by type)."""

    query = """
        SELECT COUNT(*) FROM proctoring_events
        WHERE interview_submission_id = :submission_id
    """

    params = {"submission_id": submission_id}

    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type

    return self.db.execute(query, params).scalar()
```

---

### 5.5 Get Events in Time Window

**Method:** `get_events_in_window(submission_id, event_type, window_start, window_end)`

**SQL:**

```sql
SELECT * FROM proctoring_events
WHERE interview_submission_id = :submission_id
  AND event_type = :event_type
  AND occurred_at >= :window_start
  AND occurred_at <= :window_end
ORDER BY occurred_at ASC;
```

**Implementation:**

```python
def get_events_in_window(
    self,
    submission_id: int,
    event_type: str,
    window_start: datetime,
    window_end: datetime
) -> list[ProctoringEventEntity]:
    """Get events in time window (for clustering detection)."""

    results = self.db.execute(
        """
        SELECT * FROM proctoring_events
        WHERE interview_submission_id = :submission_id
          AND event_type = :event_type
          AND occurred_at >= :window_start
          AND occurred_at <= :window_end
        ORDER BY occurred_at ASC
        """,
        {
            "submission_id": submission_id,
            "event_type": event_type,
            "window_start": window_start,
            "window_end": window_end
        }
    ).fetchall()

    return [self._map_to_entity(row) for row in results]
```

---

## 6. Retention Policy Enforcement

### 6.1 Deletion Strategy

**Policy:**

- Events older than retention period → deleted
- Aggregated risk scores → preserved in interview_submissions
- Deletion audit log → generated

**Background job:**

- Runs daily at off-peak hours (e.g., 2 AM UTC)
- Deletes events in batches (e.g., 1000 at a time)
- Logs deletion count per organization

---

### 6.2 Delete Older Than

**Method:** `delete_older_than(retention_date, organization_id)`

**SQL:**

```sql
DELETE FROM proctoring_events
WHERE id IN (
    SELECT pe.id
    FROM proctoring_events pe
    JOIN interview_submissions isub ON pe.interview_submission_id = isub.id
    WHERE isub.organization_id = :organization_id
      AND pe.occurred_at < :retention_date
    LIMIT :batch_size
)
RETURNING id;
```

**Implementation:**

```python
def delete_older_than(
    self,
    retention_date: datetime,
    organization_id: int,
    batch_size: int = 1000
) -> int:
    """
    Delete events older than retention date for organization.

    Returns count of deleted events.
    """

    deleted_ids = []

    while True:
        # Delete in batches to avoid long-running transaction
        result = self.db.execute(
            """
            DELETE FROM proctoring_events
            WHERE id IN (
                SELECT pe.id
                FROM proctoring_events pe
                JOIN interview_submissions isub
                    ON pe.interview_submission_id = isub.id
                WHERE isub.organization_id = :organization_id
                  AND pe.occurred_at < :retention_date
                LIMIT :batch_size
            )
            RETURNING id
            """,
            {
                "organization_id": organization_id,
                "retention_date": retention_date,
                "batch_size": batch_size
            }
        )

        batch_ids = [row.id for row in result.fetchall()]

        if not batch_ids:
            break

        deleted_ids.extend(batch_ids)
        self.db.commit()

        # Brief pause between batches to avoid overwhelming DB
        time.sleep(0.1)

    return len(deleted_ids)
```

---

### 6.3 Retention Job

**Scheduled job (e.g., using Celery):**

```python
from celery import Celery
from datetime import datetime, timedelta

app = Celery('proctoring_jobs')

@app.task(name='proctoring.enforce_retention')
def enforce_retention_policy():
    """
    Daily job to delete events older than retention period.

    Runs at 2 AM UTC daily.
    """
    db = get_db_session()
    repo = ProctoringEventRepository(db)
    config = get_proctoring_config()

    # Get all organizations
    organizations = db.query(Organization).all()

    total_deleted = 0

    for org in organizations:
        # Get org-specific retention or use default
        retention_days = org.proctoring_retention_days or config.event_retention_days
        retention_date = datetime.utcnow() - timedelta(days=retention_days)

        # Delete events
        deleted_count = repo.delete_older_than(retention_date, org.id)

        if deleted_count > 0:
            logger.info(
                f"Deleted {deleted_count} proctoring events for org {org.id} "
                f"(retention: {retention_days} days)"
            )
            total_deleted += deleted_count

    logger.info(f"Retention enforcement complete. Total deleted: {total_deleted}")

    # Generate audit report
    generate_deletion_audit_report(total_deleted)

    db.close()
```

**Celery schedule (celerybeat):**

```python
app.conf.beat_schedule = {
    'enforce-proctoring-retention': {
        'task': 'proctoring.enforce_retention',
        'schedule': crontab(hour=2, minute=0),  # 2 AM UTC daily
    },
}
```

---

## 7. Multi-Tenant Isolation

### 7.1 Query Scoping

**Must enforce:**

- All queries join through interview_submissions.organization_id
- Admins can only query events for own organization
- No direct event_id lookup without org verification

**Example (secure query):**

```python
def get_events_for_admin(submission_id: int, admin_org_id: int) -> list:
    """Get events with tenant isolation check."""

    # Verify submission belongs to admin's organization
    submission = db.query(InterviewSubmission).filter_by(
        id=submission_id,
        organization_id=admin_org_id
    ).first()

    if not submission:
        raise ValueError("Submission not found or access denied")

    # Now safe to query events
    return repo.get_by_submission(submission_id)
```

---

### 7.2 Deletion Isolation

**Must ensure:**

- Retention job runs per organization independently
- Delete query includes organization_id filter
- No cross-tenant deletion possible

---

## 8. Immutability Enforcement

### 8.1 Repository Constraints

**Must prohibit:**

- UPDATE operations on proctoring_events
- DELETE operations (except retention job)

**Implementation:**

```python
class ProctoringEventRepository:
    """Repository with immutability enforcement."""

    def update(self, event_id: int, updates: dict):
        """UPDATE prohibited - raises error."""
        raise ImmutabilityViolationError(
            "Proctoring events are immutable. Cannot update event after creation."
        )

    def delete(self, event_id: int):
        """DELETE prohibited - raises error."""
        raise ImmutabilityViolationError(
            "Proctoring events are immutable. Use retention policy for deletion."
        )
```

---

### 8.2 Database Constraints

**Optional (PostgreSQL row-level security):**

```sql
-- Create policy preventing updates
CREATE POLICY proctoring_events_no_update ON proctoring_events
    FOR UPDATE USING (false);

-- Create policy preventing manual deletes (except retention job role)
CREATE POLICY proctoring_events_no_delete ON proctoring_events
    FOR DELETE USING (current_user = 'proctoring_retention_job');

ALTER TABLE proctoring_events ENABLE ROW LEVEL SECURITY;
```

---

## 9. Performance Optimization

### 9.1 Index Usage

**Most common query:** Get all events for submission

```sql
-- Uses index: idx_proctoring_events_submission
SELECT * FROM proctoring_events
WHERE interview_submission_id = 12345
ORDER BY occurred_at ASC;
```

**Query plan:**

```
Index Scan using idx_proctoring_events_submission on proctoring_events
  Index Cond: (interview_submission_id = 12345)
  Order By: occurred_at
```

---

### 9.2 Batch Operations

**Use batch insert for multiple events:**

- Single transaction overhead
- Reduced network round trips
- Better throughput (10x faster for 50 events)

**Example:**

```python
# Slow: 50 individual inserts
for event in events:
    repo.create(event)  # 50 round trips

# Fast: 1 batch insert
repo.create_batch(events)  # 1 round trip
```

---

### 9.3 Pagination

**For large result sets (admin review queue):**

```python
def get_events_paginated(
    submission_id: int,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[ProctoringEventEntity], int]:
    """Get events with pagination."""

    # Count total
    total = db.execute(
        "SELECT COUNT(*) FROM proctoring_events WHERE interview_submission_id = :id",
        {"id": submission_id}
    ).scalar()

    # Fetch page
    events = db.execute(
        """
        SELECT * FROM proctoring_events
        WHERE interview_submission_id = :id
        ORDER BY occurred_at ASC
        LIMIT :limit OFFSET :offset
        """,
        {"id": submission_id, "limit": limit, "offset": offset}
    ).fetchall()

    return ([_map_to_entity(e) for e in events], total)
```

---

## 10. Observability

### 10.1 Metrics

**Must expose:**

- `proctoring_events_stored_total` (counter with label: event_type) - Total events stored
- `proctoring_events_deleted_total` (counter) - Events deleted by retention job
- `proctoring_storage_query_duration_seconds` (histogram with label: query_type) - Query latency

---

### 10.2 Logging

**Must log (INFO level):**

- Event stored (submission_id, event_type, severity)
- Batch inserted (count)
- Retention job executed (deleted_count, organization_id)

**Must log (ERROR level):**

- Event insert failed (error message, event data sanitized)
- Retention job failed (error message, organization_id)

---

## 11. Testing Requirements

### 11.1 Unit Tests

1. **Create event:** Event inserted → returns ID and created_at
2. **Batch insert:** 50 events → all inserted in 1 transaction
3. **Get by submission:** Query → returns events in chronological order
4. **Count events:** Submission with 10 events → count = 10
5. **Time window query:** Events in [T1, T2] → only matching events returned

---

### 11.2 Integration Tests

1. **End-to-end:** Event inserted → retrievable by submission_id
2. **Tenant isolation:** Org 1 admin queries Org 2 submission → access denied
3. **Retention policy:** Events older than 365 days → deleted by job
4. **Immutability:** Attempt UPDATE → raises ImmutabilityViolationError
5. **Pagination:** 100 events → fetch page 1 (50) then page 2 (50)

---

### 11.3 Performance Tests

1. **Batch insert:** 1000 events → completes in < 5 seconds
2. **Query by submission:** 500 events → retrieval in < 200ms
3. **Retention deletion:** Delete 10,000 events → completes in < 60 seconds (batched)

---

## 12. Critical Risks

1. **Event loss:** Transaction rollback without retry → events never stored
2. **Query timeout:** Submission with 10,000 events → retrieval times out (need pagination)
3. **Retention cascade:** Events deleted → risk score references broken (must preserve aggregated scores)
4. **Index bloat:** No vacuuming → query performance degrades over time
5. **Immutability violation:** Developer bypasses repository → direct UPDATE breaks audit trail

---

## 13. Acceptance Criteria

**Persistence module is complete when:**

✅ Event insertion working (single + batch)
✅ Event retrieval by submission working with filters
✅ Count and time window queries working (for clustering)
✅ Retention policy enforcement working (background job)
✅ Multi-tenant isolation enforced (organization_id scoping)
✅ Immutability enforced (UPDATE/DELETE prohibited)
✅ Indexes created (submission_id, severity, occurred_at)
✅ Pagination support for large result sets
✅ Batch operations optimized (10x faster than individual)
✅ Metrics exposed (events stored, deleted, query latency)
✅ Logging complete (INFO + ERROR levels)
✅ All tests passing (unit + integration + performance)

---

**End of Proctoring Persistence Requirements**
