# Proctoring Module — Human Testing Guide

**Module:** Proctoring (Ingestion, Rules, Risk Model, Persistence)  
**Purpose:** Verify proctoring event ingestion, rule application, risk scoring, and admin review queue  
**Prerequisites:** Running application with database (migration applied), Redis (optional), valid JWT tokens  
**Ticket:** DEV-46  

---

## Quick Start

### 1. Apply Migration

```bash
cd /home/jithsungh/projects/ai_interviewer

# Apply the proctoring columns migration
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-46_proctoring-risk-model-columns.sql
```

**Expected Output:**
```
ALTER TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
```

### 2. Start Application

```bash
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 3. Obtain Auth Token

```bash
# Admin token (for review queue + recompute)
ADMIN_TOKEN="<your-admin-jwt>"

# Candidate/any authenticated token (for event ingestion + queries)
AUTH_TOKEN="<your-auth-jwt>"
```

---

## Test Scenarios

### Test 1: Single Event Ingestion

**Objective:** Ingest a single proctoring event and verify it is processed

#### Test 1.1: Ingest tab_switch Event

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": 1,
    "event_type": "tab_switch",
    "timestamp": "2026-02-14T10:30:15.234Z",
    "metadata": {"tab_title": "[REDACTED]"}
  }' | python3 -m json.tool
```

**Expected Response (202 Accepted):**
```json
{
  "event_id": 1,
  "status": "accepted",
  "message": "Event accepted and processed"
}
```

**Validation:**
- Status code is 202
- `event_id` is a positive integer
- `status` is `"accepted"`

#### Test 1.2: Ingest Invalid Event Type → Rejected

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": 1,
    "event_type": "teleportation_detected",
    "timestamp": "2026-02-14T10:30:15.234Z"
  }' | python3 -m json.tool
```

**Expected Response (422):**
```json
{
  "detail": [
    {
      "msg": "Value error, Unknown event type 'teleportation_detected'...",
      "type": "value_error"
    }
  ]
}
```

**Validation:**
- Status code is 422
- Error message mentions unknown event type

#### Test 1.3: Duplicate Event → Idempotent

```bash
# Send the same event twice (same submission_id + event_type + timestamp)
curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": 1,
    "event_type": "face_absent",
    "timestamp": "2026-02-14T10:31:00.000Z"
  }' | python3 -m json.tool

# Send again (duplicate)
curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": 1,
    "event_type": "face_absent",
    "timestamp": "2026-02-14T10:31:00.000Z"
  }' | python3 -m json.tool
```

**Expected Second Response (202):**
```json
{
  "event_id": null,
  "status": "duplicate",
  "message": "Duplicate event detected — idempotent acknowledgment"
}
```

**Validation:**
- First call returns `"accepted"` with an `event_id`
- Second call returns `"duplicate"` with `event_id: null`
- Requires Redis to be running for dedup

---

### Test 2: Batch Event Ingestion

**Objective:** Ingest multiple events in a single request

#### Test 2.1: Batch of 3 Events

```bash
curl -s -X POST http://localhost:8000/api/v1/proctoring/events/batch \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_id": 1,
    "events": [
      {
        "submission_id": 1,
        "event_type": "tab_switch",
        "timestamp": "2026-02-14T10:32:00.000Z"
      },
      {
        "submission_id": 1,
        "event_type": "multiple_faces",
        "timestamp": "2026-02-14T10:32:01.000Z"
      },
      {
        "submission_id": 1,
        "event_type": "camera_disabled",
        "timestamp": "2026-02-14T10:32:02.000Z"
      }
    ]
  }' | python3 -m json.tool
```

**Expected Response (202 Accepted):**
```json
{
  "accepted": 3,
  "rejected": 0,
  "event_ids": [3, 4, 5],
  "errors": null
}
```

**Validation:**
- `accepted` equals number of valid events
- `rejected` is 0
- `event_ids` has one ID per accepted event

#### Test 2.2: Batch Over 50 Events → Rejected

```bash
# Generate 51 events (exceeds max_length=50)
python3 -c "
import json
events = [{'submission_id': 1, 'event_type': 'tab_switch', 'timestamp': f'2026-02-14T10:{i:02d}:00.000Z'} for i in range(51)]
print(json.dumps({'submission_id': 1, 'events': events}))
" | curl -s -X POST http://localhost:8000/api/v1/proctoring/events/batch \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d @- | python3 -m json.tool
```

**Expected Response (422):**
- Pydantic validation error for list exceeding max_length

---

### Test 3: Risk Score Query

**Objective:** Retrieve risk score after ingesting events

#### Test 3.1: Get Risk Score

```bash
curl -s -X GET http://localhost:8000/api/v1/proctoring/risk/1 \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 1,
  "total_risk": 8.0,
  "classification": "moderate",
  "recommended_action": "Informational flag - no review required",
  "event_count": 5,
  "breakdown_by_type": {
    "tab_switch": {"count": 2, "total_weight": 1.0},
    "multiple_faces": {"count": 1, "total_weight": 3.0},
    "face_absent": {"count": 1, "total_weight": 1.5},
    "camera_disabled": {"count": 1, "total_weight": 2.0}
  },
  "top_events": [...],
  "severity_counts": {"low": 2, "medium": 2, "high": 1},
  "computation_algorithm": "sum",
  "computed_at": "2026-02-14T..."
}
```

**Validation:**
- `total_risk` matches sum of event weights
- `classification` matches threshold: low(<5), moderate(<15), high(<15), critical(≥30)
- `event_count` matches number of ingested events
- `breakdown_by_type` contains all ingested event types

#### Test 3.2: Get Risk for Submission with No Events

```bash
curl -s -X GET http://localhost:8000/api/v1/proctoring/risk/99999 \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 99999,
  "total_risk": 0.0,
  "classification": "low",
  "event_count": 0,
  "breakdown_by_type": {},
  ...
}
```

---

### Test 4: Recompute Risk Score (Admin Only)

**Objective:** Force risk score recomputation

#### Test 4.1: Admin Recompute

```bash
curl -s -X POST http://localhost:8000/api/v1/proctoring/risk/1/recompute \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

**Expected Response (200 OK):**
- Same structure as Test 3.1
- Risk score may differ if events changed

#### Test 4.2: Non-Admin Recompute → Forbidden

```bash
curl -s -X POST http://localhost:8000/api/v1/proctoring/risk/1/recompute \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Expected Response (403 Forbidden):**
```json
{
  "detail": "Insufficient permissions"
}
```

---

### Test 5: List Events for Submission

**Objective:** Query proctoring events with optional filters

#### Test 5.1: List All Events

```bash
curl -s -X GET "http://localhost:8000/api/v1/proctoring/events/1" \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Expected Response (200 OK):**
```json
[
  {
    "id": 1,
    "interview_submission_id": 1,
    "event_type": "tab_switch",
    "severity": "low",
    "risk_weight": 0.5,
    "evidence": {...},
    "occurred_at": "2026-02-14T...",
    "created_at": "2026-02-14T..."
  },
  ...
]
```

#### Test 5.2: Filter by Severity

```bash
curl -s -X GET "http://localhost:8000/api/v1/proctoring/events/1?severity=high" \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Validation:**
- All returned events have `severity == "high"`

#### Test 5.3: Filter by Event Type

```bash
curl -s -X GET "http://localhost:8000/api/v1/proctoring/events/1?event_type=tab_switch" \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Validation:**
- All returned events have `event_type == "tab_switch"`

---

### Test 6: Admin Review Queue

**Objective:** Verify flagged submissions appear in admin review queue

#### Test 6.1: Get Review Queue (Admin Only)

```bash
curl -s -X GET "http://localhost:8000/api/v1/proctoring/review-queue?limit=10&offset=0" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

**Expected Response (200 OK):**
```json
{
  "total": 1,
  "items": [
    {
      "submission_id": 1,
      "total_risk": 30.5,
      "classification": "critical",
      "event_count": 15,
      "flagged": true,
      "reviewed": false
    }
  ],
  "limit": 10,
  "offset": 0
}
```

**Validation:**
- Only flagged submissions (high/critical risk) appear
- Sorted by `total_risk` descending
- `reviewed` defaults to `false`

#### Test 6.2: Non-Admin Review Queue → Forbidden

```bash
curl -s -X GET "http://localhost:8000/api/v1/proctoring/review-queue" \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Expected Response (403 Forbidden)**

---

### Test 7: Clustering Detection

**Objective:** Verify clustering rules escalate severity

#### Test 7.1: 10+ tab_switch in 60 seconds → Escalation

```bash
# Ingest 11 tab_switch events within 60 seconds
for i in $(seq 1 11); do
  curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"submission_id\": 2,
      \"event_type\": \"tab_switch\",
      \"timestamp\": \"2026-02-14T11:00:$(printf '%02d' $i).000Z\"
    }" | python3 -m json.tool
  echo "---"
done
```

**Then check risk:**
```bash
curl -s -X GET http://localhost:8000/api/v1/proctoring/risk/2 \
  -H "Authorization: Bearer $AUTH_TOKEN" | python3 -m json.tool
```

**Validation:**
- After 10th event, subsequent events have `risk_weight` of 0.75 (not 0.5)
- Risk score reflects escalated weights
- Events after clustering have `severity` escalated to "medium"

---

### Test 8: All 13 Event Types

**Objective:** Verify all supported event types can be ingested

```bash
EVENT_TYPES=(
  "tab_switch" "window_blur" "window_focus_lost"
  "screen_recording_started" "screen_recording_stopped"
  "face_absent" "multiple_faces"
  "multiple_voices" "background_noise_spike"
  "camera_disabled" "microphone_disabled" "device_change"
)

for i in "${!EVENT_TYPES[@]}"; do
  curl -s -X POST http://localhost:8000/api/v1/proctoring/events \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"submission_id\": 3,
      \"event_type\": \"${EVENT_TYPES[$i]}\",
      \"timestamp\": \"2026-02-14T12:00:$(printf '%02d' $i).000Z\"
    }" | python3 -m json.tool
  echo "---"
done
```

**Validation:**
- All 12 event types return `"accepted"`
- `screen_recording_started` and `screen_recording_stopped` contribute 0.0 weight

---

## Endpoint Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/proctoring/events` | Any | Ingest single event |
| POST | `/api/v1/proctoring/events/batch` | Any | Ingest batch (max 50) |
| GET | `/api/v1/proctoring/risk/{submission_id}` | Any | Get risk score |
| POST | `/api/v1/proctoring/risk/{submission_id}/recompute` | Admin | Force recompute |
| GET | `/api/v1/proctoring/events/{submission_id}` | Any | List events |
| GET | `/api/v1/proctoring/review-queue` | Admin | Flagged submissions |

## Risk Classification Thresholds

| Range | Classification | Action |
|-------|---------------|--------|
| 0 – 4.99 | Low | No action required |
| 5.0 – 14.99 | Moderate | Informational flag |
| 15.0 – 29.99 | High | Admin review required |
| ≥ 30.0 | Critical | Urgent admin review |

## Event Severity & Weight Reference

| Event Type | Base Severity | Base Weight |
|-----------|--------------|-------------|
| tab_switch | low | 0.5 |
| window_blur | low | 0.5 |
| window_focus_lost | low | 0.5 |
| microphone_disabled | low | 1.0 |
| device_change | low | 1.0 |
| face_absent | medium | 1.5 |
| camera_disabled | medium | 2.0 |
| background_noise_spike | medium | 1.5 |
| multiple_faces | high | 3.0 |
| multiple_voices | high | 3.0 |
| screen_recording_started | low | 0.0 |
| screen_recording_stopped | low | 0.0 |

## Migration Rollback

```bash
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-46_proctoring-risk-model-columns_rollback.sql
```
