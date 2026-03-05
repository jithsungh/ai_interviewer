# Coding API — Human Testing Guide

**Module:** `app/coding/api`  
**Purpose:** Verify REST endpoints for code submission, execution status, and submission listing  
**Prerequisites:** Running application, JWT tokens for candidate & admin, active interview with a coding exchange  

---

## Quick Start

### 1. Start the Application

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Obtain Auth Tokens

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

### 3. Pre-requisites in Database

Ensure the following exist:
- A candidate with an active interview submission
- An interview exchange with `coding_problem_id` set
- A coding problem with test cases

```sql
-- Quick check (psql)
SELECT ie.id AS exchange_id, ie.coding_problem_id, isub.id AS submission_id
FROM interview_exchanges ie
JOIN interview_submissions isub ON ie.interview_submission_id = isub.id
WHERE ie.coding_problem_id IS NOT NULL
LIMIT 5;
```

Set variables:
```bash
EXCHANGE_ID=<exchange_id_from_query>
PROBLEM_ID=<coding_problem_id_from_query>
SUBMISSION_ID=<submission_id_from_query>
```

### 4. Apply Migration

```bash
psql -U postgres -d interviewer -f \
  app/persistence/postgres/migrations/DEV-49_audio-persistence-schema-additions.sql
```

---

## Test Scenarios

### Test 1: Submit Code — Happy Path (201)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"interview_exchange_id\": $EXCHANGE_ID,
    \"coding_problem_id\": $PROBLEM_ID,
    \"language\": \"python3\",
    \"source_code\": \"def solve(n):\\n    return n * n\"
  }" | jq .
```

**Expected:** HTTP 201 with:
```json
{
  "submission_id": <int>,
  "execution_status": "pending"
}
```

### Test 2: Submit Code — Duplicate (409)

Re-run the same command. **Expected:** HTTP 409 with conflict error.

### Test 3: Submit Code — Wrong Problem ID (422)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"interview_exchange_id\": $EXCHANGE_ID,
    \"coding_problem_id\": 999999,
    \"language\": \"python3\",
    \"source_code\": \"print(1)\"
  }" | jq .
```

**Expected:** HTTP 422 — Coding problem ID mismatch.

### Test 4: Submit Code — Non-existent Exchange (404)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"interview_exchange_id\": 999999,
    \"coding_problem_id\": $PROBLEM_ID,
    \"language\": \"python3\",
    \"source_code\": \"print(1)\"
  }" | jq .
```

**Expected:** HTTP 404.

### Test 5: Submit Code — Wrong Candidate (403)

Use a different candidate's token. **Expected:** HTTP 403.

### Test 6: Submit Code — No Auth (401)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Content-Type: application/json" \
  -d '{"interview_exchange_id": 1, "coding_problem_id": 1, "language": "python3", "source_code": "print(1)"}' | jq .
```

**Expected:** HTTP 401.

### Test 7: Submit Code — Invalid Language (422)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"interview_exchange_id\": $EXCHANGE_ID,
    \"coding_problem_id\": $PROBLEM_ID,
    \"language\": \"ruby\",
    \"source_code\": \"puts 1\"
  }" | jq .
```

**Expected:** HTTP 422 — `language` must be one of `cpp`, `java`, `python3`.

### Test 8: Submit Code — Empty Source Code (422)

```bash
curl -s -X POST http://localhost:8000/api/v1/coding/submit \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"interview_exchange_id\": $EXCHANGE_ID,
    \"coding_problem_id\": $PROBLEM_ID,
    \"language\": \"python3\",
    \"source_code\": \"   \"
  }" | jq .
```

**Expected:** HTTP 422 — source code empty after trim.

---

### Test 9: Get Execution Status — Happy Path (200)

```bash
# Use submission_id from Test 1
CODE_SUBMISSION_ID=<submission_id_from_test_1>
curl -s http://localhost:8000/api/v1/coding/submissions/$CODE_SUBMISSION_ID \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected:** HTTP 200 with execution status, language, score, and test results.

### Test 10: Get Execution Status — Hidden Tests Redacted

After execution completes (manually update status + insert results), hidden test case results should have `actual_output: null`, `expected_output: null`.

### Test 11: Get Execution Status — Not Found (404)

```bash
curl -s http://localhost:8000/api/v1/coding/submissions/999999 \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected:** HTTP 404.

---

### Test 12: List Submissions for Interview — Happy Path (200)

```bash
curl -s "http://localhost:8000/api/v1/coding/interviews/$SUBMISSION_ID/submissions" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" | jq .
```

**Expected:** HTTP 200 with array of `SubmissionSummary` objects (no `source_code`).

### Test 13: List Submissions — Empty (200)

Use a submission ID with no coding exchanges. **Expected:** HTTP 200 with `[]`.

### Test 14: Admin Access Bypass

```bash
curl -s "http://localhost:8000/api/v1/coding/interviews/$SUBMISSION_ID/submissions" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

**Expected:** HTTP 200 — admin bypasses ownership check.

---

## Automated Tests

### Unit Tests

```bash
pytest tests/unit/coding/api/ -v
```

### Integration Tests (requires PostgreSQL)

```bash
pytest tests/integration/coding/api/ -v
```

---

## Rollback

If the migration needs to be reverted:

```bash
psql -U postgres -d interviewer -f \
  app/persistence/postgres/migrations/DEV-49_audio-persistence-schema-additions_rollback.sql
```
