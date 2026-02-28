# Audio Ingestion Submodule — Human Testing Guide

**Module:** `app/audio/ingestion`  
**Purpose:** Verify audio session lifecycle management (start, pause, resume, stop, status) via REST API  
**Prerequisites:** Configured environment (`.env` file), running application, valid auth token  

---

## Quick Start

### 1. Start Application

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Obtain Auth Token

All audio ingestion endpoints require an authenticated identity (`Authorization: Bearer <token>`). Obtain a valid JWT token via the auth module before proceeding.

```bash
# Replace with your actual auth endpoint / credentials
TOKEN="<your-jwt-token>"
```

### 3. Base URL

```
http://localhost:8000/api/v1/audio/ingestion
```

---

## Endpoint Reference

| # | Method | Path                                             | Auth | Description               |
|---|--------|--------------------------------------------------|------|---------------------------|
| 1 | POST   | `/exchanges/{exchange_id}/session/start`         | Yes  | Start audio session       |
| 2 | POST   | `/exchanges/{exchange_id}/session/control`       | Yes  | Pause / resume / stop     |
| 3 | GET    | `/exchanges/{exchange_id}/session/status`        | Yes  | Get current session state |

---

## Test Scenarios

### ✅ Test 1: Start Audio Session

**Objective:** Start an audio ingestion session for an exchange.

#### Test 1.1: Start with Default Settings

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (201 Created):**
```json
{
  "exchange_id": 1,
  "status": "started",
  "message": "Audio session started for exchange 1"
}
```

#### Test 1.2: Start with Custom Sample Rate and Silence Threshold

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/2/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sample_rate": 48000, "silence_threshold_ms": 5000}'
```

**Expected Response (201 Created):**
```json
{
  "exchange_id": 2,
  "status": "started",
  "message": "Audio session started for exchange 2"
}
```

#### Test 1.3: Start Duplicate Session (Conflict)

**Request** (repeat Test 1.1 without stopping first):
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (409 Conflict):**
```json
{
  "error_code": "SESSION_ALREADY_ACTIVE",
  "message": "Audio session already active for exchange 1",
  "metadata": null
}
```

#### Test 1.4: Invalid Exchange ID (Zero or Negative)

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/0/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (422 Unprocessable Entity):**
FastAPI path parameter validation will reject `exchange_id <= 0`.

#### Test 1.5: Invalid Sample Rate

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/3/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sample_rate": -1}'
```

**Expected Response (422 Unprocessable Entity):**
Pydantic rejects `sample_rate <= 0`.

---

### ✅ Test 2: Control Audio Session (Pause / Resume / Stop)

**Prerequisite:** Start a session first (Test 1.1).

#### Test 2.1: Pause Session

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause", "reason": "Candidate asked for a break"}'
```

**Expected Response (200 OK):**
```json
{
  "exchange_id": 1,
  "status": "paused",
  "message": "Audio session paused for exchange 1"
}
```

#### Test 2.2: Resume Session

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'
```

**Expected Response (200 OK):**
```json
{
  "exchange_id": 1,
  "status": "resumed",
  "message": "Audio session resumed for exchange 1"
}
```

#### Test 2.3: Stop Session

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "stop", "reason": "Interview complete"}'
```

**Expected Response (200 OK):**
```json
{
  "exchange_id": 1,
  "status": "stopped",
  "message": "Audio session stopped for exchange 1"
}
```

#### Test 2.4: Control Non-Existent Session (Not Found)

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/999/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'
```

**Expected Response (404 Not Found):**
```json
{
  "error_code": "SESSION_NOT_FOUND",
  "message": "No active audio session for exchange 999",
  "metadata": null
}
```

#### Test 2.5: Pause Already-Paused Session (Conflict)

**Prerequisite:** Session 1 is already paused (run Test 2.1 twice without resuming).

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'
```

**Expected Response (409 Conflict):**
```json
{
  "error_code": "SESSION_PAUSED",
  "message": "Audio session for exchange 1 is paused",
  "metadata": null
}
```

#### Test 2.6: Resume Active (Non-Paused) Session (Conflict)

**Prerequisite:** Session is active but not paused.

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'
```

**Expected Response (409 Conflict):**
Session is not paused — resume raises `SessionPausedError` (session must be paused to resume).

#### Test 2.7: Invalid Action Value

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "restart"}'
```

**Expected Response (422 Unprocessable Entity):**
Pydantic Literal validation rejects `"restart"` — only `"pause"`, `"resume"`, `"stop"` allowed.

#### Test 2.8: Missing Action Field

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (422 Unprocessable Entity):**
`action` is required (no default).

---

### ✅ Test 3: Get Audio Session Status

**Prerequisite:** Start a session first (Test 1.1).

#### Test 3.1: Active Session Status

**Request:**
```bash
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/status \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**
```json
{
  "exchange_id": 1,
  "status": "active",
  "message": "Audio session is active"
}
```

#### Test 3.2: Paused Session Status

**Prerequisite:** Pause the session first (Test 2.1).

**Request:**
```bash
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/status \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**
```json
{
  "exchange_id": 1,
  "status": "paused",
  "message": "Audio session is paused"
}
```

#### Test 3.3: Non-Existent Session (Not Found)

**Request:**
```bash
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/999/session/status \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (404 Not Found):**
```json
{
  "error_code": "SESSION_NOT_FOUND",
  "message": "No active audio session for exchange 999",
  "metadata": null
}
```

---

### ✅ Test 4: Authentication

**Objective:** Verify endpoints reject unauthenticated requests.

#### Test 4.1: Missing Authorization Header

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/start \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (401 Unauthorized or 403 Forbidden):**
The auth dependency rejects the request.

#### Test 4.2: Invalid Token

**Request:**
```bash
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/1/session/start \
  -H "Authorization: Bearer invalid_token" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (401 Unauthorized):**
Token validation fails.

---

### ✅ Test 5: Full Lifecycle Scenario

**Objective:** Walk through a complete audio session lifecycle.

**Steps:**

```bash
# 1. Start session for exchange 10
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sample_rate": 16000}'
# → 201 Created, status: "started"

# 2. Check status
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/status \
  -H "Authorization: Bearer $TOKEN"
# → 200 OK, status: "active"

# 3. Pause session
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause", "reason": "Break requested"}'
# → 200 OK, status: "paused"

# 4. Check status (should be paused)
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/status \
  -H "Authorization: Bearer $TOKEN"
# → 200 OK, status: "paused"

# 5. Resume session
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'
# → 200 OK, status: "resumed"

# 6. Stop session
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/control \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}'
# → 200 OK, status: "stopped"

# 7. Verify session is gone
curl -s -X GET http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/status \
  -H "Authorization: Bearer $TOKEN"
# → 404 Not Found, error_code: "SESSION_NOT_FOUND"

# 8. Try to start a new session on the same exchange (should succeed now)
curl -s -X POST http://localhost:8000/api/v1/audio/ingestion/exchanges/10/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
# → 201 Created, status: "started"
```

---

## Postman Collection Setup

### Environment Variables

| Variable       | Value                                     |
|----------------|-------------------------------------------|
| `base_url`     | `http://localhost:8000`                   |
| `token`        | `<your-jwt-token>`                        |
| `exchange_id`  | `1`                                       |

### Request Template

- **Method:** POST / GET  
- **URL:** `{{base_url}}/api/v1/audio/ingestion/exchanges/{{exchange_id}}/session/start`  
- **Headers:**
  - `Authorization`: `Bearer {{token}}`
  - `Content-Type`: `application/json`

### Collection Structure

```
Audio Ingestion/
  ├── Start Session (POST)
  ├── Control Session - Pause (POST)
  ├── Control Session - Resume (POST)
  ├── Control Session - Stop (POST)
  └── Get Session Status (GET)
```

---

## Swagger / OpenAPI

When the application is running, interactive API docs are available at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Filter by tag **"Audio Ingestion"** to see the three endpoints.

---

## Error Code Reference

| Error Code              | HTTP Status | Meaning                                        |
|-------------------------|-------------|------------------------------------------------|
| `SESSION_ALREADY_ACTIVE`| 409         | Attempted to start a session that already exists |
| `SESSION_NOT_FOUND`     | 404         | Exchange has no active audio session             |
| `SESSION_CLOSED`        | 409         | Attempted action on a closed session             |
| `SESSION_PAUSED`        | 409         | Attempted pause on already-paused session        |
| *(Pydantic)*            | 422         | Invalid request body / path parameter            |
| *(Auth)*                | 401 / 403   | Missing or invalid authentication                |

---

## Request / Response Schemas

### AudioSessionStartRequest

```json
{
  "sample_rate": 16000,            // int, > 0, default 16000
  "silence_threshold_ms": null     // int | null, > 0, default null (uses config)
}
```

### AudioSessionControlRequest

```json
{
  "action": "pause",               // "pause" | "resume" | "stop" (required)
  "reason": "Optional reason"      // string | null, max 256 chars
}
```

### AudioSessionResponse

```json
{
  "exchange_id": 1,                // int
  "status": "started",             // string
  "message": "Audio session started for exchange 1"  // string
}
```

### ErrorResponse

```json
{
  "error_code": "SESSION_NOT_FOUND",  // string
  "message": "No active audio session for exchange 999",  // string
  "metadata": null                    // object | null
}
```

---

## Troubleshooting

| Symptom                           | Likely Cause                        | Resolution                                |
|-----------------------------------|-------------------------------------|-------------------------------------------|
| 401 on all requests               | Missing / expired token             | Re-authenticate and update `$TOKEN`       |
| 422 on start                      | Invalid JSON or bad sample_rate     | Check request body matches schema         |
| 409 on start                      | Session already exists              | Stop existing session first               |
| 404 on control / status           | No session for that exchange_id     | Start a session first                     |
| Application won't start           | Missing env vars or dependencies    | Check `.env` file, run `pip install -r requirements.txt` |
