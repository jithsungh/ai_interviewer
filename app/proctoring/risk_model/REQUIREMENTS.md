# Proctoring Risk Model - Aggregated Risk Score Computation

## 1. Purpose

The **risk_model** subdirectory handles:

- Aggregating event risk weights into submission-level risk score
- Classifying risk level (low, moderate, high, critical)
- Applying optional time-decay (older events contribute less)
- Generating explainable risk breakdowns
- Supporting configurable thresholds
- Flagging submissions for human review

**Critical responsibility:** Deterministic, reproducible risk scoring with transparent computation.

---

## 2. Responsibilities

### 2.1 Risk Score Aggregation

**Provides:**

- Compute total risk score from all proctoring events for a submission
- Support multiple aggregation strategies (sum, weighted average, max)
- Apply optional time-decay factor (exponential decay)
- Cap maximum risk score (prevent unbounded growth)

**Must:**

- Return same score for same set of events (deterministic)
- Explain score breakdown (event contributions)
- Support historical score recomputation (audit)

---

### 2.2 Risk Classification

**Provides:**

- Map total risk score to risk level: low, moderate, high, critical
- Support configurable thresholds
- Support tenant-specific threshold overrides

**Example thresholds:**
| Total Risk Score | Classification | Action Required |
|------------------|----------------|-------------------------|
| 0 - 5 | Low | No action |
| 5 - 15 | Moderate | Informational flag |
| 15 - 30 | High | Admin review required |
| 30+ | Critical | Urgent review required |

---

### 2.3 Explainability

**Provides:**

- Breakdown of risk score by event type
- Top contributing events (highest weights)
- Timeline visualization data
- Rule versions applied per event

**Output format:**

```json
{
  "submission_id": 12345,
  "total_risk_score": 18.5,
  "risk_classification": "high",
  "event_count": 15,
  "breakdown_by_type": {
    "tab_switch": { "count": 10, "total_weight": 7.5 },
    "face_absent": { "count": 3, "total_weight": 4.5 },
    "multiple_faces": { "count": 2, "total_weight": 6.0 }
  },
  "top_events": [
    {
      "event_id": 101,
      "event_type": "multiple_faces",
      "weight": 3.0,
      "timestamp": "2026-02-14T10:30:15Z"
    },
    {
      "event_id": 105,
      "event_type": "multiple_faces",
      "weight": 3.0,
      "timestamp": "2026-02-14T10:35:22Z"
    }
  ],
  "computation_metadata": {
    "algorithm": "sum_with_time_decay",
    "time_decay_half_life_minutes": 30,
    "max_risk_cap": 100.0,
    "computed_at": "2026-02-14T11:00:00Z"
  }
}
```

---

## 3. Risk Aggregation Algorithms

### 3.1 Simple Sum (Default)

**Formula:**

```
total_risk = Σ(event.applied_weight)
```

**Characteristics:**

- Simplest, most transparent
- All events contribute equally
- No decay over time
- Recommended for short interviews (< 1 hour)

**Example:**

- 10 events with weight 2.0 each → total_risk = 20.0

---

### 3.2 Sum with Time Decay

**Formula:**

```
total_risk = Σ(event.applied_weight × decay_factor(event.age))

decay_factor(age) = 0.5 ^ (age_minutes / half_life_minutes)
```

**Characteristics:**

- Recent events weighted higher
- Older events progressively discounted
- Prevents early mistakes from dominating final score
- Recommended for long interviews (> 1 hour)

**Example (half_life = 30 minutes):**

- Event 10 minutes ago: weight 2.0 × 0.5^(10/30) = 2.0 × 0.794 = 1.59
- Event 30 minutes ago: weight 2.0 × 0.5^(30/30) = 2.0 × 0.5 = 1.0
- Event 60 minutes ago: weight 2.0 × 0.5^(60/30) = 2.0 × 0.25 = 0.5

---

### 3.3 Weighted Average

**Formula:**

```
total_risk = (Σ(event.applied_weight)) / event_count × normalization_factor
```

**Characteristics:**

- Accounts for interview duration (longer interviews = more opportunities for events)
- Normalizes risk regardless of event count
- Less intuitive than sum
- Useful for comparing across interviews of different lengths

**Example:**

- Interview A: 10 events, total weight 20 → average risk = 2.0
- Interview B: 5 events, total weight 15 → average risk = 3.0
- Interview B has higher per-event risk despite lower total

---

### 3.4 Max Risk Cap

**Applied after aggregation:**

```
capped_risk = min(total_risk, max_risk_cap)
```

**Purpose:**

- Prevent unbounded growth (e.g., 1000 tab switches → risk 500)
- Simplify risk classification (all classifications < 100)
- Default cap: 100.0

---

## 4. Risk Classification

### 4.1 Threshold Configuration

**Must support:**

- Global default thresholds
- Tenant-specific threshold overrides
- Dynamic threshold adjustment (future: ML-based)

**Configuration:**

```python
from pydantic import BaseModel, Field

class RiskThresholds(BaseModel):
    """Risk classification thresholds."""

    low_to_moderate: float = Field(5.0, ge=0.0, description="Moderate risk threshold")
    moderate_to_high: float = Field(15.0, ge=0.0, description="High risk threshold")
    high_to_critical: float = Field(30.0, ge=0.0, description="Critical risk threshold")
    max_cap: float = Field(100.0, ge=0.0, description="Maximum risk score")

    def classify(self, risk_score: float) -> str:
        """Classify risk score into category."""
        if risk_score < self.low_to_moderate:
            return "low"
        elif risk_score < self.moderate_to_high:
            return "moderate"
        elif risk_score < self.high_to_critical:
            return "high"
        else:
            return "critical"
```

---

### 4.2 Classification Logic

**Implementation:**

```python
def classify_risk(risk_score: float, thresholds: RiskThresholds) -> RiskClassification:
    """
    Classify risk score into category with action recommendation.

    Returns classification level and recommended action.
    """
    classification = thresholds.classify(risk_score)

    action_map = {
        "low": "No action required",
        "moderate": "Informational flag - no review required",
        "high": "Admin review required before decision",
        "critical": "Urgent admin review required"
    }

    return RiskClassification(
        level=classification,
        score=risk_score,
        recommended_action=action_map[classification]
    )
```

---

## 5. Risk Score Storage

### 5.1 Real-Time Cache (Redis)

**Purpose:** Fast lookup of current risk score during interview.

**Key pattern:** `proctoring:risk:{submission_id}`

**Structure:**

```python
redis.hset(f"proctoring:risk:{submission_id}", mapping={
    "total_risk": 18.5,
    "classification": "high",
    "event_count": 15,
    "last_updated": "2026-02-14T11:00:00Z"
})
redis.expire(f"proctoring:risk:{submission_id}", 86400)  # 24 hours TTL
```

**Must:**

- Update atomically on each new event
- Support concurrent updates (use Lua script)
- Expire after interview completion + retention period

---

### 5.2 Persistent Storage (PostgreSQL)

**Purpose:** Audit trail, historical analysis, report generation.

**Table:** Add columns to `interview_submissions`:

```sql
ALTER TABLE interview_submissions ADD COLUMN proctoring_risk_score NUMERIC(6, 2) DEFAULT 0.0;
ALTER TABLE interview_submissions ADD COLUMN proctoring_risk_classification VARCHAR(20);
ALTER TABLE interview_submissions ADD COLUMN proctoring_flagged BOOLEAN DEFAULT FALSE;
ALTER TABLE interview_submissions ADD COLUMN proctoring_reviewed BOOLEAN DEFAULT FALSE;
```

**Update strategy:**

- Recompute risk score after each event inserted
- Update submission record atomically
- Set `proctoring_flagged = TRUE` if risk >= high threshold

---

## 6. Risk Computation Service

### 6.1 Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RiskScore:
    """Risk score computation result."""
    submission_id: int
    total_risk: float
    classification: str  # low, moderate, high, critical
    event_count: int
    breakdown_by_type: dict[str, dict]
    top_events: list[dict]
    computation_algorithm: str
    computed_at: datetime

class RiskModelService(ABC):
    """Abstract interface for risk score computation."""

    @abstractmethod
    def compute_risk_score(self, submission_id: int) -> RiskScore:
        """Compute current risk score for submission."""
        pass

    @abstractmethod
    def recompute_risk_score(self, submission_id: int) -> RiskScore:
        """Recompute risk score from scratch (for audit)."""
        pass

    @abstractmethod
    def get_risk_breakdown(self, submission_id: int) -> dict:
        """Get detailed risk breakdown for explainability."""
        pass
```

---

### 6.2 Implementation Example

```python
class ProctoringRiskModelService(RiskModelService):
    """Concrete implementation of risk scoring."""

    def __init__(self, db: Session, redis: Redis, config: ProctoringConfig):
        self.db = db
        self.redis = redis
        self.config = config
        self.thresholds = RiskThresholds(
            low_to_moderate=config.risk_threshold_moderate,
            moderate_to_high=config.risk_threshold_high,
            high_to_critical=config.risk_threshold_critical,
            max_cap=config.max_risk_cap
        )

    def compute_risk_score(self, submission_id: int) -> RiskScore:
        """Compute risk score using configured algorithm."""

        # Fetch all events for submission
        events = self.db.query(ProctoringEvent).filter_by(
            interview_submission_id=submission_id
        ).order_by(ProctoringEvent.occurred_at).all()

        if not events:
            return RiskScore(
                submission_id=submission_id,
                total_risk=0.0,
                classification="low",
                event_count=0,
                breakdown_by_type={},
                top_events=[],
                computation_algorithm="sum",
                computed_at=datetime.utcnow()
            )

        # Apply algorithm
        if self.config.enable_time_decay:
            total_risk = self._compute_with_decay(events)
            algorithm = "sum_with_time_decay"
        else:
            total_risk = sum(e.risk_weight for e in events)
            algorithm = "sum"

        # Apply cap
        total_risk = min(total_risk, self.config.max_risk_cap)

        # Classify
        classification = self.thresholds.classify(total_risk)

        # Generate breakdown
        breakdown = self._compute_breakdown(events)
        top_events = self._get_top_events(events, limit=5)

        result = RiskScore(
            submission_id=submission_id,
            total_risk=total_risk,
            classification=classification,
            event_count=len(events),
            breakdown_by_type=breakdown,
            top_events=top_events,
            computation_algorithm=algorithm,
            computed_at=datetime.utcnow()
        )

        # Cache result
        self._cache_risk_score(result)

        # Update submission record
        self._update_submission_risk(submission_id, result)

        return result

    def _compute_with_decay(self, events: list[ProctoringEvent]) -> float:
        """Apply exponential time decay."""
        now = datetime.utcnow()
        half_life_minutes = self.config.decay_half_life_minutes

        total = 0.0
        for event in events:
            age_minutes = (now - event.occurred_at).total_seconds() / 60
            decay_factor = 0.5 ** (age_minutes / half_life_minutes)
            total += event.risk_weight * decay_factor

        return total

    def _compute_breakdown(self, events: list[ProctoringEvent]) -> dict:
        """Group events by type with counts and weights."""
        breakdown = {}
        for event in events:
            if event.event_type not in breakdown:
                breakdown[event.event_type] = {
                    "count": 0,
                    "total_weight": 0.0
                }
            breakdown[event.event_type]["count"] += 1
            breakdown[event.event_type]["total_weight"] += event.risk_weight

        return breakdown

    def _get_top_events(self, events: list[ProctoringEvent], limit: int = 5) -> list[dict]:
        """Get top N events by weight."""
        sorted_events = sorted(events, key=lambda e: e.risk_weight, reverse=True)

        return [
            {
                "event_id": e.id,
                "event_type": e.event_type,
                "weight": e.risk_weight,
                "timestamp": e.occurred_at.isoformat()
            }
            for e in sorted_events[:limit]
        ]

    def _cache_risk_score(self, risk_score: RiskScore):
        """Store risk score in Redis cache."""
        key = f"proctoring:risk:{risk_score.submission_id}"

        self.redis.hset(key, mapping={
            "total_risk": risk_score.total_risk,
            "classification": risk_score.classification,
            "event_count": risk_score.event_count,
            "last_updated": risk_score.computed_at.isoformat()
        })
        self.redis.expire(key, 86400)  # 24 hours

    def _update_submission_risk(self, submission_id: int, risk_score: RiskScore):
        """Update interview_submissions with risk data."""
        flagged = risk_score.classification in ["high", "critical"]

        self.db.execute(
            """
            UPDATE interview_submissions
            SET proctoring_risk_score = :score,
                proctoring_risk_classification = :classification,
                proctoring_flagged = :flagged
            WHERE id = :id
            """,
            {
                "score": risk_score.total_risk,
                "classification": risk_score.classification,
                "flagged": flagged,
                "id": submission_id
            }
        )
        self.db.commit()
```

---

## 7. Flagging & Review Queue

### 7.1 Automatic Flagging

**Trigger:** Risk classification = high or critical

**Action:**

1. Set `proctoring_flagged = TRUE` on submission
2. Add submission to review queue (Redis sorted set)
3. Send notification to admins (optional: email, Slack)

**Redis review queue:**

```python
# Add to queue (score = risk_score for sorting)
redis.zadd(
    "proctoring:review_queue",
    {str(submission_id): risk_score.total_risk}
)

# Get submissions sorted by risk (highest first)
flagged_submissions = redis.zrevrange(
    "proctoring:review_queue",
    0, 99,  # Top 100
    withscores=True
)
```

---

### 7.2 Review Queue API

**Endpoint:** `GET /api/admin/proctoring/review-queue`

**Query params:**

- `organization_id` (required for tenant isolation)
- `risk_level` (optional filter: high, critical)
- `limit` (default: 50)
- `offset` (default: 0)

**Response:**

```json
{
  "total": 15,
  "submissions": [
    {
      "submission_id": 12345,
      "candidate_name": "Alice Johnson",
      "total_risk": 35.5,
      "classification": "critical",
      "event_count": 20,
      "flagged_at": "2026-02-14T11:00:00Z",
      "reviewed": false
    },
    {
      "submission_id": 12346,
      "candidate_name": "Bob Smith",
      "total_risk": 22.0,
      "classification": "high",
      "event_count": 12,
      "flagged_at": "2026-02-14T10:45:00Z",
      "reviewed": false
    }
  ]
}
```

---

## 8. Advisory-Only Enforcement

### 8.1 MustNOT Actions

**Risk score must NEVER:**

- Auto-fail interview (change submission status to failed)
- Auto-reject candidate (change recommendation to no_hire)
- Modify evaluation scores (reduce scores based on risk)
- Block interview progress (prevent question delivery)
- Cancel interview session (terminate WebSocket)

**SRS Compliance:**

- NR-1: "The system shall not make autonomous hiring or pass/fail decisions."
- NFR-14: "Automated scoring and proctoring outputs shall be advisory only."

---

### 8.2 Allowed Actions

**Risk score MAY:**

- Add informational flag to submission record
- Display warning badge in admin UI
- Include risk score in supplementary report
- Trigger human review requirement
- Send notification to admin for review

**All consequential decisions require human approval.**

---

## 9. Historical Score Recomputation

### 9.1 Use Case

**Scenario:** Rule weights updated, admin wants to recompute historical scores.

**Requirement:**

- Recompute risk scores using historical rule versions (not current)
- Preserve original computation metadata
- Generate comparison report (old vs new scores)

---

### 9.2 Implementation

```python
def recompute_historical_scores(
    submission_ids: list[int],
    use_historical_rules: bool = True
) -> list[RiskScoreComparison]:
    """
    Recompute risk scores for historical submissions.

    Args:
        submission_ids: List of submission IDs to recompute
        use_historical_rules: If True, use rule version from event time
                              If False, use current rules

    Returns:
        List of comparisons showing old vs new scores
    """
    results = []

    for submission_id in submission_ids:
        # Get current stored score
        old_score = get_stored_risk_score(submission_id)

        # Recompute
        if use_historical_rules:
            new_score = recompute_with_historical_rules(submission_id)
        else:
            new_score = compute_risk_score(submission_id)

        results.append(RiskScoreComparison(
            submission_id=submission_id,
            old_score=old_score.total_risk,
            new_score=new_score.total_risk,
            old_classification=old_score.classification,
            new_classification=new_score.classification,
            delta=new_score.total_risk - old_score.total_risk
        ))

    return results
```

---

## 10. Observability

### 10.1 Metrics

**Must expose:**

- `proctoring_risk_scores` (histogram) - Distribution of risk scores
- `proctoring_risk_classification` (gauge with label: classification) - Count per classification
- `proctoring_flagged_submissions` (gauge) - Submissions in review queue
- `proctoring_risk_computation_duration_seconds` (histogram) - Computation latency

---

### 10.2 Logging

**Must log (INFO level):**

- Risk score computed (submission_id, total_risk, classification)
- Submission flagged (submission_id, risk_score, event_count)
- Review queue updated (submission added/removed)

**Must log (WARN level):**

- Risk score exceeds critical threshold (submission_id, risk_score)
- Recomputation differs significantly from cached value (> 10% delta)

---

## 11. Testing Requirements

### 11.1 Unit Tests

1. **Simple sum:** 10 events with weight 2.0 each → total_risk = 20.0
2. **Time decay:** Event 30 min ago with weight 2.0 and half_life 30 min → decayed_weight = 1.0
3. **Risk classification:** Risk 18.5 → classified as "high"
4. **Risk cap:** Risk 120 → capped at 100.0
5. **Breakdown by type:** Events with types [A, A, B] → breakdown = {A: 2, B: 1}

---

### 11.2 Integration Tests

1. **End-to-end:** Events inserted → risk score computed → submission flagged
2. **Redis cache:** Risk score computed → cached in Redis → retrievable
3. **Review queue:** High risk submission → added to review queue → admin can retrieve
4. **Tenant isolation:** Org 1 review queue does not show Org 2 submissions
5. **Historical recomputation:** Old score = 20.0, rules changed, new score = 18.0 → comparison generated

---

### 11.3 Edge Case Tests

1. **Zero risk:** No events → risk_score = 0.0, classification = "low"
2. **Single high-risk event:** 1 event with weight 35.0 → flagged
3. **Many low-risk events:** 100 events with weight 0.5 each → risk = 50.0 (capped)
4. **Time decay extreme:** Event 5 hours ago with half_life 30 min → decayed to near-zero
5. **Concurrent updates:** 2 events inserted simultaneously → both contribute to final score

---

## 12. Critical Risks

1. **Non-deterministic scoring:** Same events produce different scores (floating point rounding, time-of-day effects)
2. **Score inflation:** No max cap → unbounded growth → scores lose meaning
3. **Threshold drift:** Thresholds changed without recomputing historical scores → classification inconsistency
4. **Cache staleness:** Redis cache not updated → admin sees outdated risk score
5. **Advisory violation:** Risk score used to auto-fail candidate (prohibited by SRS)

---

## 13. Acceptance Criteria

**Risk model module is complete when:**

✅ Risk score aggregation working (sum, sum_with_decay)
✅ Risk classification accurate (low, moderate, high, critical)
✅ Configurable thresholds with tenant overrides
✅ Explainable risk breakdown generated
✅ Top contributing events identified
✅ Redis caching implemented (fast lookup)
✅ PostgreSQL storage updated (audit trail)
✅ Review queue working (sorted by risk score)
✅ Automatic flagging on high/critical risk
✅ Advisory-only enforcement (no auto-fail)
✅ Historical recomputation supported
✅ Metrics exposed (risk scores, flagged count)
✅ Logging complete (INFO + WARN levels)
✅ All tests passing (unit + integration + edge cases)

---

**End of Proctoring Risk Model Requirements**
