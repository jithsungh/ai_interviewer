# Interview Module — Human Testing Guide

**Module:** `app/interview` (api + persistence submodules)  
**Purpose:** Verify REST endpoints for exchange listing and section progress  
**Prerequisites:** Running application, JWT tokens for candidate & admin, at least one active interview submission with exchanges

---

## Quick Start

### 1. Start the Application

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Obtain Auth Tokens

You need JWTs for two roles:

| Role      | Description                          |
|-----------|--------------------------------------|
| Candidate | Can access only their own interviews |
| Admin     | Can access any interview             |

```bash
# Candidate login
CANDIDATE_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "candidate@example.com", "password": "password"}' | jq -r '.access_token')

# Admin login
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}' | jq -r '.access_token')
```

### 3. Identify a Submission

Ensure at least one interview submission exists. Use the session endpoints to create one if needed:

```bash
# Start an interview (candidate)
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/start \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"window_id": 1}' | jq .

# Note the submission_id from the response
SUBMISSION_ID=<returned_id>
```

---

## Test Scenarios

### Test 1: List Exchanges — Candidate (Happy Path)

**Objective:** Candidate retrieves their own exchange audit trail.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/exchanges" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 123,
  "exchanges": [
    {
      "exchange_id": 789,
      "sequence_order": 1,
      "question_text": "Tell me about your experience with Python.",
      "question_type": "text",
      "difficulty_at_time": "medium",
      "section_name": "resume",
      "response_text": "I have 5 years of experience...",
      "response_code": null,
      "response_language": null,
      "response_time_ms": 45000,
      "ai_followup_message": null,
      "created_at": "2026-02-14T10:05:00Z"
    }
  ],
  "total_exchanges": 1
}
```

**Validation:**
- Status code is 200
- `submission_id` matches the requested ID
- `exchanges` is an array ordered by `sequence_order`
- `total_exchanges` reflects the actual count
- All response fields are present when `include_responses=true` (default)

---

### Test 2: List Exchanges — Without Responses

**Objective:** Verify that response fields are redacted when `include_responses=false`.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/exchanges?include_responses=false" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 123,
  "exchanges": [
    {
      "exchange_id": 789,
      "sequence_order": 1,
      "question_text": "Tell me about your experience with Python.",
      "question_type": "text",
      "difficulty_at_time": "medium",
      "section_name": "resume",
      "response_text": null,
      "response_code": null,
      "response_language": null,
      "response_time_ms": null,
      "ai_followup_message": null,
      "created_at": "2026-02-14T10:05:00Z"
    }
  ],
  "total_exchanges": 1
}
```

**Validation:**
- `response_text`, `response_code`, `response_language`, `response_time_ms`, `ai_followup_message` are all `null`
- Question metadata (`question_text`, `question_type`, `difficulty_at_time`, `section_name`) is still present

---

### Test 3: List Exchanges — Section Filter

**Objective:** Verify section-based filtering.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/exchanges?section=resume" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected Response (200 OK):**
- Only exchanges with `"section_name": "resume"` are returned
- `total_exchanges` reflects the filtered count

**Validation:**
- Every exchange in the array has `section_name == "resume"`
- Count matches the actual number of resume-section exchanges

---

### Test 4: List Exchanges — Admin Access

**Objective:** Admin can access any submission's exchanges.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/exchanges" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected Response (200 OK):**
- Same response shape as candidate
- Access granted regardless of submission ownership

**Validation:**
- Status code is 200
- No ownership validation error

---

### Test 5: List Exchanges — Submission Not Found

**Objective:** Verify proper 404 handling.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/999999/exchanges" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected Response (404 Not Found):**
```json
{
  "detail": "Submission 999999 not found"
}
```

**Validation:**
- Status code is 404
- Error message identifies the missing resource

---

### Test 6: List Exchanges — Wrong Candidate

**Objective:** Candidate cannot access another candidate's submission.

**Request:**
```bash
# Use a submission_id belonging to a different candidate
curl -s -X GET "http://localhost:8000/api/v1/interviews/${OTHER_SUBMISSION_ID}/exchanges" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected Response (404 Not Found):**
```json
{
  "detail": "Submission <id> not found"
}
```

**Validation:**
- Status code is 404 (not 403 — prevents enumeration)

---

### Test 7: Get Progress — Candidate (Happy Path)

**Objective:** Candidate retrieves section-level progress for their interview.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/progress" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 123,
  "overall_progress": 50.0,
  "sections": [
    {
      "section_name": "resume",
      "questions_total": 2,
      "questions_answered": 2,
      "progress_percentage": 100.0
    },
    {
      "section_name": "coding",
      "questions_total": 3,
      "questions_answered": 0,
      "progress_percentage": 0.0
    }
  ]
}
```

**Validation:**
- `submission_id` matches
- `overall_progress` is between 0.0 and 100.0
- Each section has `questions_total >= questions_answered`
- `progress_percentage` equals `(questions_answered / questions_total) * 100` (rounded)
- All sections from the frozen template snapshot are represented

---

### Test 8: Get Progress — Admin Access

**Objective:** Admin can view progress for any submission.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/progress" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected Response (200 OK):**
- Same shape as candidate response
- Access granted regardless of ownership

---

### Test 9: Get Progress — No Template Snapshot

**Objective:** Verify behaviour when submission has no frozen template.

**Request:**
```bash
# Use a submission with null template_structure_snapshot
curl -s -X GET "http://localhost:8000/api/v1/interviews/${NO_TEMPLATE_SUBMISSION_ID}/progress" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected Response (200 OK):**
```json
{
  "submission_id": 456,
  "overall_progress": 0.0,
  "sections": []
}
```

**Validation:**
- `overall_progress` is 0.0
- `sections` is an empty array
- No error is raised

---

### Test 10: Unauthenticated Request

**Objective:** Verify auth requirement.

**Request:**
```bash
curl -s -X GET "http://localhost:8000/api/v1/interviews/${SUBMISSION_ID}/exchanges" | jq .
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated"
}
```

---

## Endpoint Reference

| Method | Path                                    | Auth      | Description                    |
|--------|-----------------------------------------|-----------|--------------------------------|
| GET    | `/api/v1/interviews/{id}/exchanges`     | Required  | List exchanges (audit trail)   |
| GET    | `/api/v1/interviews/{id}/progress`      | Required  | Section progress breakdown     |

### Query Parameters — `/exchanges`

| Parameter          | Type    | Default | Description                         |
|--------------------|---------|---------|-------------------------------------|
| `include_responses`| bool    | `true`  | Include response data in output     |
| `section`          | string  | `null`  | Filter by section name (max 50 chars)|

### Response Schemas

#### ExchangeListResponse

| Field              | Type                  | Description                      |
|--------------------|-----------------------|----------------------------------|
| `submission_id`    | int                   | The submission ID                |
| `exchanges`        | ExchangeItemDTO[]     | Ordered list of exchanges        |
| `total_exchanges`  | int                   | Total count of returned exchanges|

#### ExchangeItemDTO

| Field                | Type       | Description                          |
|----------------------|------------|--------------------------------------|
| `exchange_id`        | int        | Exchange primary key                 |
| `sequence_order`     | int        | 1-based sequence within submission   |
| `question_text`      | string     | Frozen question text                 |
| `question_type`      | string?    | `text`, `coding`, or `audio`         |
| `difficulty_at_time` | string     | Difficulty when question was served  |
| `section_name`       | string?    | Section from content_metadata        |
| `response_text`      | string?    | Candidate's text response            |
| `response_code`      | string?    | Candidate's code response            |
| `response_language`  | string?    | Programming language (if coding)     |
| `response_time_ms`   | int?       | Time taken in milliseconds           |
| `ai_followup_message`| string?    | AI-generated follow-up               |
| `created_at`         | datetime?  | Exchange creation timestamp          |

#### SectionProgressResponse

| Field              | Type                   | Description                        |
|--------------------|------------------------|------------------------------------|
| `submission_id`    | int                    | The submission ID                  |
| `overall_progress` | float (0-100)          | Weighted overall progress          |
| `sections`         | SectionProgressDTO[]   | Per-section breakdown              |

#### SectionProgressDTO

| Field                | Type        | Description                        |
|----------------------|-------------|------------------------------------|
| `section_name`       | string      | Section identifier from template   |
| `questions_total`    | int         | Total questions in section         |
| `questions_answered` | int         | Completed exchanges in section     |
| `progress_percentage`| float (0-100)| Section completion percentage     |

---

## Automated Test Commands

```bash
# Run all new unit tests
python -m pytest tests/unit/interview/persistence/ tests/unit/interview/api/ -v

# Run all new integration tests
python -m pytest tests/integration/interview/persistence/ tests/integration/interview/api/ -v

# Run everything together
python -m pytest tests/unit/interview/persistence/ tests/unit/interview/api/ \
  tests/integration/interview/persistence/ tests/integration/interview/api/ -v --tb=short
```

**Expected:** 67 tests, all passing.

---

## Architecture Notes

- **Read-only guarantee:** These endpoints perform no writes. State transitions remain in `session/api`, exchange creation in `orchestration/exchange_coordinator`.
- **Ownership scoping:** Candidates are scoped to their own submissions via `candidate_id` filtering. Admins bypass ownership checks. 404 (not 403) is returned for unauthorized access to prevent ID enumeration.
- **Template snapshot:** Progress is computed from the frozen `template_structure_snapshot` JSONB column, ensuring progress reflects the template at interview creation time, not the current template state.
- **No duplication:** Reuses ORM models from `session/persistence/models` and error types from `shared/errors`. No model or DTO duplication.
