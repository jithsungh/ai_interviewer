# Auth API — Human Testing Guide

## Prerequisites

- Python 3.12+ with virtual environment activated
- PostgreSQL running with schema applied (`docs/schema.sql`)
- At least one organization in `organizations` table with `status = 'active'`
- Environment variables configured (see below)

### Required Environment Variables

```bash
export APP_ENV=dev
export DEBUG=true
export BASE_URL=http://localhost:8000
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ai_interviewer
export REDIS_URL=redis://localhost:6379/0
export QDRANT_URL=http://localhost:6333
export GROQ_API_KEY=test-key
export JWT_ALGORITHM=HS256
export JWT_SECRET_KEY=your-secret-key-at-least-32-characters-long
export ACCESS_TOKEN_EXPIRE_MINUTES=30
export REFRESH_TOKEN_EXPIRE_DAYS=30
export PASSWORD_HASH_ROUNDS=12
```

### Start Server

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Seed Test Organization (if needed)

```sql
INSERT INTO organizations (name, organization_type, plan, domain, status, created_at, updated_at)
VALUES ('Test Corp', 'company', 'pro', 'testcorp.com', 'active', NOW(), NOW());
```

Note the returned `id` — you'll use it as `organization_id`.

---

## Endpoints

| Method | Path | Auth | Status |
|--------|------|------|--------|
| POST | `/api/v1/auth/register/admin` | None | 201 |
| POST | `/api/v1/auth/register/candidate` | None | 201 |
| POST | `/api/v1/auth/login` | None | 200 |
| POST | `/api/v1/auth/refresh` | None | 200 |
| POST | `/api/v1/auth/logout` | None | 200 |
| GET | `/api/v1/auth/me` | Bearer Token | 200 |

---

## 1. Register Admin

### Request

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register/admin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@testcorp.com",
    "password": "SecurePass123!",
    "organization_id": 1,
    "admin_role": "admin",
    "full_name": "Admin User"
  }' | python3 -m json.tool
```

### Expected Response (201)

```json
{
  "user_id": 1,
  "email": "admin@testcorp.com",
  "user_type": "admin",
  "message": "Registration successful"
}
```

### Failure Cases

| Case | Payload Change | Expected Status | Error Code |
|------|---------------|-----------------|------------|
| Duplicate email | Same email twice | 409 | `CONFLICT` |
| Invalid email | `"email": "bad"` | 422 | Validation |
| Weak password | `"password": "weak"` | 422 | Validation |
| No uppercase | `"password": "password1!"` | 422 | Validation |
| No special char | `"password": "Password1"` | 422 | Validation |
| Superadmin role | `"admin_role": "superadmin"` | 422 | Validation |
| Org not found | `"organization_id": 99999` | 404 | `NOT_FOUND` |
| Org ID = 0 | `"organization_id": 0` | 422 | Validation |
| Missing fields | `{}` | 422 | Validation |

---

## 2. Register Candidate

### Request

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register/candidate \
  -H "Content-Type: application/json" \
  -d '{
    "email": "candidate@example.com",
    "password": "SecurePass123!",
    "full_name": "Jane Smith",
    "phone": "+1-555-0123"
  }' | python3 -m json.tool
```

### Expected Response (201)

```json
{
  "user_id": 2,
  "email": "candidate@example.com",
  "user_type": "candidate",
  "message": "Registration successful"
}
```

### Failure Cases

| Case | Expected Status |
|------|-----------------|
| Duplicate email | 409 |
| Invalid email | 422 |
| Weak password | 422 |
| Missing email | 422 |

---

## 3. Login

### Request (Admin)

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@testcorp.com",
    "password": "SecurePass123!"
  }' | python3 -m json.tool
```

### Expected Response (200)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "a1b2c3d4e5f6...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "user": {
    "user_id": 1,
    "email": "admin@testcorp.com",
    "user_type": "admin",
    "admin_id": 1,
    "organization_id": 1,
    "admin_role": "admin",
    "candidate_id": null,
    "full_name": null
  }
}
```

**Save the `access_token` and `refresh_token` for subsequent calls.**

### Failure Cases

| Case | Expected Status |
|------|-----------------|
| Wrong email | 401 |
| Wrong password | 401 |
| Inactive user | 401 |
| Banned user | 401 |
| Suspended org | 401 |
| Missing fields | 422 |

---

## 4. Get Current User (Protected)

### Request

```bash
# Replace <ACCESS_TOKEN> with the token from login
curl -s -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>" | python3 -m json.tool
```

### Expected Response (200)

```json
{
  "user_id": 1,
  "email": "admin@testcorp.com",
  "user_type": "admin",
  "user_status": "active",
  "admin_id": 1,
  "organization_id": 1,
  "admin_role": "admin",
  "admin_status": "active",
  "candidate_id": null,
  "full_name": null,
  "candidate_status": null,
  "last_login_at": "2026-02-28T12:00:00Z"
}
```

### Failure Cases

| Case | Expected Status |
|------|-----------------|
| No Authorization header | 401 |
| Invalid token | 401 |
| Expired token | 401 |

---

## 5. Refresh Token

### Request

```bash
# Replace <REFRESH_TOKEN> with the refresh_token from login
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<REFRESH_TOKEN>"
  }' | python3 -m json.tool
```

### Expected Response (200)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...(new)",
  "refresh_token": "g7h8i9j0...(new)",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

**Note:** The old refresh token is revoked after rotation. Using it again triggers suspicious activity detection and revokes ALL tokens for that user.

### Failure Cases

| Case | Expected Status |
|------|-----------------|
| Invalid/unknown token | 401 |
| Expired token | 401 |
| Reused (already-rotated) token | 401 (all tokens revoked) |
| Token too short | 422 |

---

## 6. Logout

### Request

```bash
# Use the latest refresh_token (from login or refresh)
curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<REFRESH_TOKEN>"
  }' | python3 -m json.tool
```

### Expected Response (200)

```json
{
  "message": "Logout successful"
}
```

### Idempotency

Calling logout with the same token again returns 200 (idempotent).

---

## Full Flow Test Script

```bash
BASE=http://localhost:8000/api/v1/auth

# 1. Register admin
echo "=== Register Admin ==="
curl -s -X POST $BASE/register/admin \
  -H "Content-Type: application/json" \
  -d '{"email":"flow-test@co.com","password":"SecurePass123!","organization_id":1,"admin_role":"admin","full_name":"Flow Test"}' | python3 -m json.tool

# 2. Login
echo "=== Login ==="
LOGIN=$(curl -s -X POST $BASE/login \
  -H "Content-Type: application/json" \
  -d '{"email":"flow-test@co.com","password":"SecurePass123!"}')
echo $LOGIN | python3 -m json.tool

ACCESS=$(echo $LOGIN | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH=$(echo $LOGIN | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

# 3. Get profile
echo "=== Get Me ==="
curl -s -X GET $BASE/me -H "Authorization: Bearer $ACCESS" | python3 -m json.tool

# 4. Refresh
echo "=== Refresh Token ==="
REFRESHED=$(curl -s -X POST $BASE/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}")
echo $REFRESHED | python3 -m json.tool

NEW_REFRESH=$(echo $REFRESHED | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

# 5. Logout
echo "=== Logout ==="
curl -s -X POST $BASE/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$NEW_REFRESH\"}" | python3 -m json.tool

# 6. Verify old refresh token is rejected
echo "=== Verify old refresh token rejected ==="
curl -s -X POST $BASE/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}" | python3 -m json.tool
```

---

## Running Tests

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate

# Unit tests only (no DB needed)
python -m pytest tests/unit/auth/api/ -v

# Integration tests (no DB needed, uses TestClient with mocks)
python -m pytest tests/integration/auth/api/ -v

# All auth tests
python -m pytest tests/unit/auth/ tests/integration/auth/ -v

# Full suite
python -m pytest tests/ -v
```

---

## Postman Setup

1. Create collection: **AI Interviewer Auth**
2. Set base URL variable: `{{base_url}}` = `http://localhost:8000`
3. Import requests:

| Name | Method | URL | Body |
|------|--------|-----|------|
| Register Admin | POST | `{{base_url}}/api/v1/auth/register/admin` | raw JSON |
| Register Candidate | POST | `{{base_url}}/api/v1/auth/register/candidate` | raw JSON |
| Login | POST | `{{base_url}}/api/v1/auth/login` | raw JSON |
| Get Me | GET | `{{base_url}}/api/v1/auth/me` | none |
| Refresh Token | POST | `{{base_url}}/api/v1/auth/refresh` | raw JSON |
| Logout | POST | `{{base_url}}/api/v1/auth/logout` | raw JSON |

4. For **Login** request, add a post-request script:
   ```javascript
   var data = pm.response.json();
   pm.environment.set("access_token", data.access_token);
   pm.environment.set("refresh_token", data.refresh_token);
   ```

5. For **Get Me**, set Authorization header: `Bearer {{access_token}}`
6. For **Refresh Token**, set body: `{"refresh_token": "{{refresh_token}}"}`

---

## Schema Changes

**None.** All required tables already exist in `docs/schema.sql`. No migrations needed.

## Error Response Format

All errors follow the shared format:

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid credentials",
    "request_id": "uuid-string",
    "metadata": {}
  }
}
```

Validation errors (422):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "request_id": "uuid-string",
    "metadata": {
      "errors": [
        {"field": "body.email", "message": "...", "type": "..."}
      ]
    }
  }
}
```
