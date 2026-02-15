# Proctoring Module - Advisory Integrity Signal Collection & Risk Scoring

## 1. Purpose

The **Proctoring** module provides:

- Runtime integrity signal collection (tab switches, face detection, audio anomalies)
- Timestamped event logging with metadata
- Deterministic risk score computation
- Session flagging for administrative review
- Audit-safe, explainable proctoring reports

**Critical responsibility:** This is an **ADVISORY-ONLY** system. It must:

- Collect integrity signals during live interviews
- Log events with timestamps and severity
- Compute aggregated risk scores deterministically
- Flag sessions for human review
- **NEVER block candidates automatically**
- **NEVER auto-fail interviews**
- **NEVER modify evaluation scores**

**Architectural philosophy:**

> **Proctoring OBSERVES. It does NOT DECIDE.**
> **Signals are ADVISORY. Humans make consequential decisions.**
> **Transparency and explainability are mandatory.**

---

## 2. What This Module IS

**Advisory signal collection:**

- Tab/window switching detection (FR-9.1)
- Screen recording support (FR-9.2)
- Face presence/absence detection (FR-9.3)
- Multiple face detection (FR-9.4)
- Audio anomaly detection (FR-9.5)
- Camera/microphone disable detection
- Device change detection

**Deterministic risk scoring:**

- Event-based risk weight assignment
- Configurable severity levels (low, medium, high, critical)
- Aggregated submission-level risk score
- Time-decay and clustering multipliers (optional)
- Threshold-based risk classification

**Human review integration:**

- Flagged session queue for admins
- Audit trail with event evidence
- Explainable risk breakdowns

---

## 3. What This Module IS NOT

**FORBIDDEN - This module must NEVER:**

❌ **Autonomous rejection** - No auto-fail, no auto-block candidates (NR-1)
❌ **Emotion recognition** - Explicitly prohibited by FR-5.5, FR-9.10, NR-3
❌ **Eye-tracking** - Explicitly prohibited by FR-5.5, FR-9.10
❌ **Psychological inference** - No behavioral trait inference (NR-3)
❌ **Score modification** - Cannot alter evaluation scores directly
❌ **Exchange modification** - Cannot change interview content
❌ **Autonomous decisions** - All consequential actions require human review (NFR-14)

**SRS Compliance:**

- FR-9.10: "The system shall not perform emotion recognition or eye-tracking."
- NR-1: "The system shall not make autonomous hiring or pass/fail decisions."
- NR-3: "The system shall not infer psychological, medical, or behavioral traits."
- NFR-14: "Automated scoring and proctoring outputs shall be advisory only."

---

## 4. Module Structure

```
proctoring/
├── REQUIREMENTS.md         # This file (core module)
├── ingestion/
│   └── REQUIREMENTS.md     # Event intake & validation
├── rules/
│   └── REQUIREMENTS.md     # Severity & weight assignment
├── risk_model/
│   └── REQUIREMENTS.md     # Aggregated risk computation
└── persistence/
    └── REQUIREMENTS.md     # Event storage & retrieval
```

---

## 5. Core Responsibilities

### 5.1 Event Ingestion (ingestion/)

**Provides:**

- Validate and ingest proctoring events from live sessions
- Support WebSocket, REST, and streaming ingestion
- Attach organization_id for tenant isolation
- Handle burst events safely (rate limiting)
- Reject malformed events

**See:** [ingestion/REQUIREMENTS.md](ingestion/REQUIREMENTS.md)

---

### 5.2 Severity & Weight Rules (rules/)

**Provides:**

- Map event types to severity levels (low, medium, high, critical)
- Assign base risk weights per event type
- Apply clustering multipliers (repeated events escalate)
- Support configurable, tenant-specific rule overrides
- Version rule changes for auditability

**See:** [rules/REQUIREMENTS.md](rules/REQUIREMENTS.md)

---

### 5.3 Risk Score Computation (risk_model/)

**Provides:**

- Aggregate event risk weights into submission-level score
- Apply time-decay (optional, for progressive risk reduction)
- Classify risk (low, moderate, high, critical)
- Generate explainable risk breakdowns
- Support threshold configuration

**See:** [risk_model/REQUIREMENTS.md](risk_model/REQUIREMENTS.md)

---

### 5.4 Event Persistence (persistence/)

**Provides:**

- Store proctoring events immutably
- Preserve event ordering and timestamps
- Index by submission_id for efficient retrieval
- Support retention policy enforcement (DR-7)
- Never update events after creation

**See:** [persistence/REQUIREMENTS.md](persistence/REQUIREMENTS.md)

---

## 6. Owned Entity

### proctoring_events

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

**Fields:**

- `interview_submission_id`: Foreign key to interview (tenant-scoped)
- `event_type`: Event category (tab_switch, multiple_faces, etc.)
- `severity`: Enum (low, medium, high, critical)
- `risk_weight`: Numeric weight contributing to total risk
- `evidence`: JSONB metadata (timestamps, device info, frame snapshots metadata)
- `occurred_at`: When event happened (client-reported or server-detected)
- `created_at`: When event was recorded in database

---

## 7. Supported Event Types

### 7.1 Tab/Window Events (FR-9.1)

| Event Type          | Description                     | Severity | Base Weight |
| ------------------- | ------------------------------- | -------- | ----------- |
| `tab_switch`        | Candidate switched browser tab  | low      | 0.5         |
| `window_blur`       | Window lost focus               | low      | 0.5         |
| `window_focus_lost` | Browser window minimized/hidden | low      | 0.5         |

**Clustering rule:** 10+ tab switches in 1 minute → escalate to medium severity.

---

### 7.2 Screen Recording Events (FR-9.2)

| Event Type                 | Description                | Severity | Base Weight |
| -------------------------- | -------------------------- | -------- | ----------- |
| `screen_recording_started` | Screen recording initiated | info     | 0.0         |
| `screen_recording_stopped` | Screen recording ended     | info     | 0.0         |

**Note:** Informational only, no risk impact.

---

### 7.3 Face Detection Events (FR-9.3, FR-9.4)

| Event Type       | Description               | Severity | Base Weight |
| ---------------- | ------------------------- | -------- | ----------- |
| `face_absent`    | No face detected in frame | medium   | 1.5         |
| `multiple_faces` | Multiple faces detected   | high     | 3.0         |

**Clustering rule:** 3+ consecutive `face_absent` → escalate to high severity.

---

### 7.4 Audio Anomaly Events (FR-9.5)

| Event Type               | Description                      | Severity | Base Weight |
| ------------------------ | -------------------------------- | -------- | ----------- |
| `multiple_voices`        | Multiple voices detected         | high     | 3.0         |
| `background_noise_spike` | Sudden background noise increase | medium   | 1.5         |

---

### 7.5 Device Events

| Event Type            | Description                     | Severity | Base Weight |
| --------------------- | ------------------------------- | -------- | ----------- |
| `camera_disabled`     | Camera turned off mid-interview | medium   | 2.0         |
| `microphone_disabled` | Microphone muted mid-interview  | low      | 1.0         |
| `device_change`       | Camera/mic device switched      | low      | 1.0         |

---

## 8. Risk Score Computation

### 8.1 Aggregation Formula

**Base risk score:**

```
total_risk = Σ(event.risk_weight)
```

**Optional enhancements:**

- **Time decay:** Recent events weighted higher (exponential decay)
- **Clustering multiplier:** Repeated events in short window → 1.5x weight
- **Max cap:** Cap total risk at 100 (prevents unbounded growth)

---

### 8.2 Risk Classification

**Thresholds (configurable):**

| Total Risk | Classification | Action                 |
| ---------- | -------------- | ---------------------- |
| 0 - 5      | Low            | No action required     |
| 5 - 15     | Moderate       | Informational flag     |
| 15 - 30    | High           | Requires admin review  |
| 30+        | Critical       | Urgent review required |

---

### 8.3 Advisory-Only Enforcement

**Risk score MUST:**

- Be visible to admins in review queue
- Generate warning badge in UI
- Trigger review requirement flag
- Be included in audit report

**Risk score MUST NOT:**

- Auto-fail interview (forbidden by NR-1)
- Modify evaluation scores (separation of concerns)
- Block candidate from submitting (forbidden)
- Change interview_results.recommendation automatically

---

## 9. Human Review Integration

### 9.1 Review Queue (FR-9.8)

**Must provide:**

- List of flagged submissions (risk >= high threshold)
- Sort by risk score (descending)
- Filter by severity, event type, date range
- Display event timeline per submission
- Show aggregated risk breakdown

---

### 9.2 Admin Actions

**Available actions:**

1. **Acknowledge flag:** Admin reviewed, no action needed
2. **Request re-evaluation:** Human override of evaluation score
3. **Mark as suspicious:** Escalate to organization admin
4. **Dismiss flag:** False positive (log reason)

**All actions must be logged:**

- Admin user_id
- Action taken
- Justification (free text)
- Timestamp

---

## 10. Retention Policies (DR-7, FR-9.9)

**Must support:**

- Configurable retention period per tenant
- Shorter default for proctoring media (30 days)
- Longer default for event metadata (1 year)
- Automatic deletion workflows
- Deletion audit reports

**Example retention:**

- Proctoring events: 1 year
- Screen recording media: 30 days
- Video snapshots (if captured): 30 days
- Risk scores (aggregated): Permanent (audit trail)

---

## 11. Multi-Tenant Isolation

**Must enforce:**

- Events scoped to organization_id (via interview_submission)
- Admins can only view events for own organization
- Risk aggregation per submission only (no cross-tenant)
- Review queue filtered by organization

**Verification:**

```sql
-- Query must always include organization filter
SELECT * FROM proctoring_events pe
JOIN interview_submissions isub ON pe.interview_submission_id = isub.id
WHERE isub.organization_id = ?
```

---

## 12. Explainability & Auditability

### 12.1 Event Evidence

**Each event must include:**

- Timestamp (occurred_at with millisecond precision)
- Event type and severity
- Risk weight assigned
- Rule version applied
- Metadata (device info, detection confidence, etc.)

**Example evidence JSONB:**

```json
{
  "detected_at": "2026-02-14T10:30:15.234Z",
  "client_timestamp": "2026-02-14T10:30:14.987Z",
  "device_info": {
    "browser": "Chrome 120",
    "os": "Windows 11",
    "camera_model": "Logitech C920"
  },
  "detection_details": {
    "faces_detected": 2,
    "confidence": 0.95,
    "frame_timestamp": "00:15:23"
  },
  "rule_version": "v1.2.0"
}
```

---

### 12.2 Risk Breakdown Report

**Must generate per submission:**

- Total risk score
- Event count by severity
- Top contributing events (highest weights)
- Timeline visualization data
- Rule versions applied

**Export formats:**

- JSON (API response)
- PDF (admin download)
- CSV (bulk analysis)

---

## 13. Integration with Other Modules

### 13.1 Interview Module

**Interview module sends events:**

- WebSocket: Real-time tab switch, blur events
- REST API: Batch event ingestion (post-interview)

**Proctoring module provides:**

- Event ingestion endpoints
- Risk score query API

**Proctoring NEVER:**

- Modifies interview state
- Cancels interviews
- Blocks question delivery

---

### 13.2 Evaluation Module

**Evaluation module MAY read:**

- Submission risk score (advisory context only)
- Risk classification (low/moderate/high/critical)

**Evaluation module MAY:**

- Include risk score in supplementary report
- Add proctoring flag to interview_results

**Evaluation module MUST NOT:**

- Auto-reduce scores based on risk
- Change recommendation based on risk alone
- Require human override to be triggered automatically

---

### 13.3 Admin Module

**Admin module consumes:**

- Review queue (flagged submissions)
- Risk score reports
- Event timelines
- Aggregated statistics

**Admin module provides:**

- Review workflow UI
- Flag acknowledgment
- Human override triggers

---

## 14. Configuration

```python
from pydantic import BaseModel, Field

class ProctoringConfig(BaseModel):
    """Proctoring system configuration."""

    # Ingestion
    max_events_per_minute: int = Field(100, description="Rate limit per submission")
    event_batch_size: int = Field(50, description="Batch ingestion size")

    # Risk thresholds
    risk_threshold_moderate: float = Field(5.0, description="Moderate risk threshold")
    risk_threshold_high: float = Field(15.0, description="High risk threshold")
    risk_threshold_critical: float = Field(30.0, description="Critical risk threshold")

    # Risk computation
    enable_time_decay: bool = Field(False, description="Apply time decay to event weights")
    decay_half_life_minutes: int = Field(30, description="Time for weight to decay 50%")
    enable_clustering_multiplier: bool = Field(True, description="Escalate repeated events")
    clustering_window_seconds: int = Field(60, description="Time window for clustering")
    max_risk_cap: float = Field(100.0, description="Maximum total risk score")

    # Event weights (base)
    weight_tab_switch: float = Field(0.5, description="Tab switch base weight")
    weight_face_absent: float = Field(1.5, description="Face absent base weight")
    weight_multiple_faces: float = Field(3.0, description="Multiple faces base weight")
    weight_multiple_voices: float = Field(3.0, description="Multiple voices base weight")
    weight_camera_disabled: float = Field(2.0, description="Camera disabled base weight")

    # Retention
    event_retention_days: int = Field(365, description="Event metadata retention (days)")
    media_retention_days: int = Field(30, description="Media artifacts retention (days)")

    # Features
    enable_face_detection: bool = Field(True, description="Enable face detection")
    enable_audio_analysis: bool = Field(True, description="Enable audio anomaly detection")
    enable_screen_recording: bool = Field(False, description="Enable screen recording")
```

---

## 15. Testing Requirements

### 15.1 Unit Tests

1. **Event ingestion:** Valid event → stored with severity and weight
2. **Event validation:** Malformed event → rejected
3. **Rate limiting:** 101 events in 1 minute → excess rejected
4. **Risk computation:** 10 events with weight 2.0 each → total risk = 20.0
5. **Risk classification:** Risk 18 → classified as "high"
6. **Clustering multiplier:** 10 tab switches in 60s → weight escalated

---

### 15.2 Integration Tests

1. **End-to-end event flow:** Interview sends event → stored → risk computed → admin sees flag
2. **Multi-tenant isolation:** Org 1 event → Org 2 admin cannot see
3. **Review queue:** High risk submission → appears in admin queue
4. **Retention policy:** Events older than retention period → auto-deleted
5. **Advisory enforcement:** High risk → evaluation score unchanged

---

### 15.3 Edge Case Tests

1. **Burst events:** 1000 events in 10 seconds → rate limited, no data loss
2. **Event replay attack:** Duplicate event with same timestamp → deduplicated
3. **Clock skew:** Client timestamp 5 minutes ahead → normalized to server time
4. **Face detection false positive:** Rapid face_absent flicker → smoothing applied
5. **Zero-risk interview:** No events logged → risk score = 0.0

---

## 16. Critical Risks

1. **Autonomous rejection:** System auto-fails candidate (FORBIDDEN by SRS)
2. **Silent event loss:** Events dropped under load, incomplete audit trail
3. **Cross-tenant leakage:** Org 1 admin sees Org 2 events
4. **Score drift:** Rule changes retroactively alter historical risk scores
5. **Retention violation:** Events not deleted per policy (GDPR compliance risk)
6. **False positive cascade:** Repeated false positives erode trust

---

## 17. Observability

### 17.1 Metrics

**Must expose:**

- `proctoring_events_total` (counter) - Total events ingested
- `proctoring_events_by_type` (counter with label) - Events per type
- `proctoring_risk_score` (histogram) - Distribution of risk scores
- `proctoring_flagged_submissions` (gauge) - Submissions in review queue
- `proctoring_ingestion_latency_seconds` (histogram) - Event ingestion latency

---

### 17.2 Logging

**Must log:**

- Event ingested (DEBUG with event type, submission_id)
- Risk score computed (INFO with total risk, classification)
- Submission flagged (WARNING with risk score, event count)
- Admin reviewed (INFO with action taken)
- Retention deletion executed (INFO with count deleted)

**Must NOT log:**

- Candidate names or PII in event evidence
- Full video frames or audio clips (only metadata)

---

## 18. Compliance Alignment

### 18.1 SRS Requirements

**FR-9.1 - FR-9.5:** Event collection for tab switches, screen recording, face detection, audio anomalies
**FR-9.6:** All events timestamped and logged ✅
**FR-9.7:** Configurable risk score ✅
**FR-9.8:** Admin review queue ✅
**FR-9.9:** Retention policy enforcement ✅
**FR-9.10:** No emotion recognition, no eye-tracking ✅

**NFR-14:** Advisory only, human oversight required ✅
**NR-1:** No autonomous decisions ✅
**NR-3:** No psychological inference ✅

---

### 18.2 Privacy & Ethics

**Must ensure:**

- Explicit consent before proctoring starts (NFR-9)
- Minimal data collection (only integrity signals)
- Transparent disclosure (candidate knows what's monitored)
- Data subject access (candidate can view own events)
- Right to deletion (events deletable per retention policy)

---

## 19. Future Enhancements

1. **ML-based anomaly detection:** Detect unusual patterns (but remain explainable)
2. **Proctoring lite mode:** Minimal monitoring for low-stakes interviews
3. **Real-time alerts:** Notify admin during live interview (high risk)
4. **Candidate dispute workflow:** Allow candidates to contest flags
5. **Adaptive thresholds:** Adjust risk thresholds per interview type

---

## 20. Acceptance Criteria

**Proctoring module is complete when:**

✅ Event ingestion working (WebSocket + REST)
✅ All event types supported (tab switch, face detection, audio, device)
✅ Severity and weight assignment deterministic
✅ Risk score computation accurate and explainable
✅ Risk classification thresholds configurable
✅ Review queue shows flagged submissions
✅ Admin actions logged with justification
✅ Multi-tenant isolation enforced
✅ Retention policies enforced with auto-deletion
✅ No autonomous rejection (advisory only)
✅ No emotion recognition or eye-tracking
✅ No evaluation score modification
✅ All SRS requirements met (FR-9.1-9.10, NFR-14, NR-1, NR-3)
✅ All tests passing

---

**End of Proctoring Module Requirements**
