# Auth Contracts — Human Testing Guide

## Module Overview

`app/auth/contracts` is a **pure schema/DTO layer** — no database, no API endpoints, no persistence.
It defines Pydantic models (request/response), JWT claim types, and error codes used by the auth API layer.

---

## File Inventory

| File | Purpose |
|------|---------|
| `__init__.py` | Public API (re-exports all schemas, enums, claims) |
| `schemas.py` | Request models: `AdminRegistrationRequest`, `CandidateRegistrationRequest`, `LoginRequest`, `RefreshTokenRequest`, `LogoutRequest` |
| `responses.py` | Response models: `RegistrationResponse`, `UserProfileResponse`, `LoginResponse`, `TokenRefreshResponse`, `CurrentUserResponse`, `ErrorResponse` |
| `enums.py` | `AuthErrorCode` enum (18 machine-readable error codes) |
| `claims.py` | `AdminAccessTokenClaims`, `CandidateAccessTokenClaims` (TypedDict for JWT payloads) |

---

## Running Tests

### Prerequisites

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
```

### Unit Tests (100 tests)

```bash
.venv/bin/python -m pytest tests/unit/auth/contracts/ -v
```

### Integration Tests (21 tests)

```bash
.venv/bin/python -m pytest tests/integration/auth/contracts/ -v
```

### All Auth Contract Tests

```bash
.venv/bin/python -m pytest tests/unit/auth/contracts/ tests/integration/auth/contracts/ -v
```

---

## Schema Changes

**None.** This module is pure Python — no database tables, no migrations required.

---

## Manual Validation (Python REPL)

### 1. Validate AdminRegistrationRequest

```python
from app.auth.contracts import AdminRegistrationRequest

# Valid request
req = AdminRegistrationRequest(
    email="admin@company.com",
    password="SecurePass123!",
    organization_id=1,
    admin_role="admin",
    full_name="John Doe"
)
print(req.model_dump_json(indent=2))

# Should FAIL: superadmin not allowed via registration
try:
    AdminRegistrationRequest(
        email="a@b.com",
        password="Secure1!",
        organization_id=1,
        admin_role="superadmin"
    )
except Exception as e:
    print(f"EXPECTED ERROR: {e}")

# Should FAIL: weak password (no uppercase)
try:
    AdminRegistrationRequest(
        email="a@b.com",
        password="lowercase1!",
        organization_id=1,
        admin_role="admin"
    )
except Exception as e:
    print(f"EXPECTED ERROR: {e}")
```

### 2. Validate CandidateRegistrationRequest

```python
from app.auth.contracts import CandidateRegistrationRequest

req = CandidateRegistrationRequest(
    email="candidate@example.com",
    password="StrongPass1!",
    full_name="Jane Smith",
    phone="+1-555-0123"
)
print(req.model_dump_json(indent=2))
```

### 3. Validate LoginRequest

```python
from app.auth.contracts import LoginRequest

# Login does NOT enforce password complexity (only min_length=1)
req = LoginRequest(email="user@example.com", password="x")
print(req.model_dump_json(indent=2))
```

### 4. Validate Response Construction

```python
from app.auth.contracts import LoginResponse, UserProfileResponse

resp = LoginResponse(
    access_token="eyJhbGciOiJSUzI1NiJ9...",
    refresh_token="a" * 64,
    expires_in=900,
    user=UserProfileResponse(
        user_id=42,
        email="admin@company.com",
        user_type="admin",
        admin_id=10,
        organization_id=5,
        admin_role="admin"
    )
)
print(resp.model_dump_json(indent=2))
```

### 5. Validate ErrorResponse with AuthErrorCode

```python
from app.auth.contracts import ErrorResponse, AuthErrorCode

err = ErrorResponse(
    error=AuthErrorCode.INVALID_CREDENTIALS.value,
    message="Email or password is incorrect"
)
print(err.model_dump_json(indent=2))
```

### 6. Validate JWT Claim Types

```python
from app.auth.contracts import AdminAccessTokenClaims, CandidateAccessTokenClaims

admin_claims: AdminAccessTokenClaims = {
    "sub": 42, "type": "admin", "admin_id": 10,
    "organization_id": 5, "role": "admin",
    "iat": 1700000000, "exp": 1700003600,
    "jti": "uuid-here", "token_version": 3
}
print(admin_claims)

candidate_claims: CandidateAccessTokenClaims = {
    "sub": 123, "type": "candidate", "candidate_id": 50,
    "iat": 1700000000, "exp": 1700003600,
    "jti": "uuid-here", "token_version": 1
}
print(candidate_claims)
```

### 7. Validate OpenAPI Schema Generation

```python
import json
from app.auth.contracts import AdminRegistrationRequest, LoginResponse

print(json.dumps(AdminRegistrationRequest.model_json_schema(), indent=2))
print(json.dumps(LoginResponse.model_json_schema(), indent=2))
```

---

## Security Invariants to Verify

| Invariant | How to verify |
|-----------|---------------|
| No `password` field in any response | `"password" not in ResponseModel.model_fields` for all response models |
| No `password_hash` in any response | Same check for `password_hash` |
| `superadmin` rejected on registration | `AdminRegistrationRequest(admin_role="superadmin")` raises `ValidationError` |
| Password complexity enforced | Weak passwords rejected by `AdminRegistrationRequest` and `CandidateRegistrationRequest` |
| Login does NOT enforce complexity | `LoginRequest(email="a@b.com", password="x")` succeeds |
| Admin claims always have `organization_id` | `"organization_id" in AdminAccessTokenClaims.__annotations__` |
| Candidate claims never have `organization_id` | `"organization_id" not in CandidateAccessTokenClaims.__annotations__` |

---

## Dependency Notes

- Requires `pydantic >= 2.0` and `email-validator` (for `EmailStr`)
- Reuses `MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH` from `app.config.constants`
- Uses `UserType`, `AdminRole` enums from `app.shared.auth_context` for compatibility (not direct import in schemas — Literal types used to avoid coupling)
- No database, Redis, or external service dependencies
