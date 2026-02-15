# Auth API Layer - HTTP Endpoints

## 1. Purpose

**Why this submodule exists:**

The Auth API layer exposes **public and protected HTTP endpoints** for identity management. It:

- Provides registration endpoints (admin, candidate)
- Provides authentication endpoints (login, logout, refresh)
- Provides identity introspection endpoints (current user, profile)
- Handles HTTP-specific concerns (request validation, response formatting, error codes)
- Delegates business logic to `domain` layer
- Returns standardized API responses

**Critical responsibility:** This is the **public interface** of the auth module. It must never expose internal implementation details, password hashes, or sensitive data. All business logic stays in `domain` layer.

---

## 2. Owned Tables / Entities

**None.** API layer is stateless and delegates all data operations to `domain` and `persistence` layers.

---

## 3. Input Contracts

### Request Schemas

All requests use Pydantic models for validation.

#### POST `/api/v1/auth/register/admin`

```python
class AdminRegistrationRequest(BaseModel):
    email: EmailStr                                 # Pydantic email validation
    password: str = Field(min_length=8, max_length=128)
    organization_id: int = Field(gt=0)
    admin_role: Literal["admin", "read_only"]       # Cannot self-assign superadmin
    full_name: Optional[str] = Field(max_length=255)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@company.com",
                "password": "SecurePass123!",
                "organization_id": 1,
                "admin_role": "admin",
                "full_name": "John Doe"
            }
        }
```

#### POST `/api/v1/auth/register/candidate`

```python
class CandidateRegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(max_length=255)
    phone: Optional[str] = Field(max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "candidate@example.com",
                "password": "SecurePass123!",
                "full_name": "Jane Smith",
                "phone": "+1-555-0123"
            }
        }
```

#### POST `/api/v1/auth/login`

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }
```

#### POST `/api/v1/auth/refresh`

```python
class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32)
```

---

## 4. Output Contracts

### Response Schemas

#### RegistrationResponse

```python
class RegistrationResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    message: str = "Registration successful"
```

#### LoginResponse

```python
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int                     # Seconds
    user: UserProfileResponse

class UserProfileResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]

    # Admin fields
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None

    # Candidate fields
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
```

#### TokenRefreshResponse

```python
class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str                  # New refresh token (if rotation enabled)
    token_type: str = "Bearer"
    expires_in: int
```

#### CurrentUserResponse

```python
class CurrentUserResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    user_status: str

    # Admin context
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None
    admin_status: Optional[str] = None

    # Candidate context
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
    candidate_status: Optional[str] = None

    last_login_at: Optional[datetime] = None
```

---

## 5. Acceptance Criteria

### Functional Requirements

#### Endpoint: POST `/api/v1/auth/register/admin`

**Success (201 Created):**

- Validate request body (Pydantic)
- Call `domain.auth_service.register_admin()`
- Return user profile without password hash
- Log registration event

**Errors:**

- 400 Bad Request: Invalid email format, password too weak
- 409 Conflict: Email already exists
- 404 Not Found: Organization not found
- 422 Unprocessable Entity: Validation errors

#### Endpoint: POST `/api/v1/auth/register/candidate`

**Success (201 Created):**

- Validate request body
- Call `domain.auth_service.register_candidate()`
- Return user profile

**Errors:**

- 400 Bad Request: Invalid input
- 409 Conflict: Email already exists

#### Endpoint: POST `/api/v1/auth/login`

**Success (200 OK):**

- Validate credentials via `domain.auth_service.login()`
- Extract IP address from request
- Extract user agent from headers
- Return access + refresh tokens
- Set `HttpOnly` cookie for refresh token (optional)

**Errors:**

- 401 Unauthorized: Invalid email or password
- 403 Forbidden: User banned, organization suspended
- 429 Too Many Requests: Rate limit exceeded

#### Endpoint: POST `/api/v1/auth/refresh`

**Success (200 OK):**

- Validate refresh token via `domain.auth_service.refresh_token()`
- Return new access token + new refresh token (if rotation enabled)

**Errors:**

- 401 Unauthorized: Invalid, expired, or revoked refresh token

#### Endpoint: POST `/api/v1/auth/logout`

**Success (200 OK):**

- Extract refresh token from request body or cookie
- Call `domain.auth_service.logout()`
- Clear cookie if used

**Errors:**

- 401 Unauthorized: Invalid refresh token

#### Endpoint: GET `/api/v1/auth/me`

**Success (200 OK):**

- Extract user identity from access token (via middleware)
- Call `domain.auth_service.get_current_user()`
- Return full user profile

**Errors:**

- 401 Unauthorized: Missing or invalid access token

### Non-Functional Requirements

1. **Request Validation:**
   - Use Pydantic for automatic validation
   - Return 422 with detailed error messages on validation failure

2. **Error Responses:**
   - Standardize error format:
     ```json
     {
       "error": "error_code",
       "message": "Human-readable message",
       "details": {...}
     }
     ```

3. **CORS:**
   - Configure CORS headers for frontend access
   - Allow credentials for cookie-based refresh tokens

4. **Rate Limiting:**
   - Apply rate limits via middleware
   - Return `Retry-After` header with 429 responses

5. **Security Headers:**
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Strict-Transport-Security` (HTTPS)

---

## 6. Invariants & Constraints

### Must Hold

1. **Password Never Returned:** API responses never include `password` or `password_hash` fields
2. **Refresh Token Security:** Refresh tokens stored in `HttpOnly` cookies (optional) or secure storage
3. **Email Case Insensitivity:** Email comparisons always case-insensitive
4. **Request Validation:** All inputs validated before calling domain layer
5. **Error Sanitization:** Error messages never expose internal implementation details

### Forbidden

- MUST NOT expose stack traces in production
- MUST NOT return password hashes in any response
- MUST NOT accept `superadmin` role in registration endpoint
- MUST NOT skip validation (even for internal calls)
- MUST NOT log passwords or tokens in plain text

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Frontend Applications:**
   - Admin dashboard
   - Candidate interview portal
   - Mobile apps (future)

2. **API Gateway:**
   - Routes auth requests to auth API layer
   - May apply global rate limiting

### Downstream (Dependencies)

1. **Domain Layer (`app.auth.domain`):**
   - `AuthService.register_admin()`
   - `AuthService.register_candidate()`
   - `AuthService.login()`
   - `AuthService.refresh_token()`
   - `AuthService.logout()`
   - `AuthService.get_current_user()`

2. **Middleware:**
   - JWT validation middleware (extracts `AuthContext`)
   - Rate limiting middleware
   - CORS middleware

---

## 8. Event Contracts Emitted

API layer emits HTTP responses only. Domain layer emits `AuthEvent` for audit logging.

---

## 9. Edge Cases to Handle

1. **Missing Authorization Header:**
   - Return 401 with `missing_token` error code

2. **Malformed Token:**
   - Return 401 with `invalid_token` error code

3. **Rate Limit Exceeded:**
   - Return 429 with `Retry-After: 900` (15 minutes)

4. **Organization Suspended:**
   - Return 403 with `organization_suspended` message

5. **Concurrent Registration:**
   - Database UNIQUE constraint prevents duplicate
   - Return 409 if email already exists

---

## 10. Concurrency Concerns

API layer is stateless. Concurrency handled by:

- Database constraints (UNIQUE on email)
- Domain layer transaction management
- Rate limiting middleware

---

## 11. Configuration

### Environment Variables

```bash
# API Configuration
AUTH_API_BASE_PATH=/api/v1/auth
AUTH_API_CORS_ORIGINS=http://localhost:3000,https://app.example.com

# Cookie Configuration (if using HttpOnly cookies)
AUTH_COOKIE_NAME=refresh_token
AUTH_COOKIE_SECURE=true  # HTTPS only
AUTH_COOKIE_HTTPONLY=true
AUTH_COOKIE_SAMESITE=Strict

# Rate Limiting
AUTH_RATE_LIMIT_ENABLED=true
```

---

## 12. Example API Usage

### Register Admin

```bash
curl -X POST http://localhost:8000/api/v1/auth/register/admin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "password": "SecurePass123!",
    "organization_id": 1,
    "admin_role": "admin",
    "full_name": "John Doe"
  }'

# Response 201 Created
{
  "user_id": 123,
  "email": "admin@company.com",
  "user_type": "admin",
  "message": "Registration successful"
}
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "password": "SecurePass123!"
  }'

# Response 200 OK
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a1b2c3d4e5f6...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "user_id": 123,
    "email": "admin@company.com",
    "user_type": "admin",
    "admin_id": 1,
    "organization_id": 1,
    "admin_role": "admin"
  }
}
```

### Get Current User

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# Response 200 OK
{
  "user_id": 123,
  "email": "admin@company.com",
  "user_type": "admin",
  "user_status": "active",
  "admin_id": 1,
  "organization_id": 1,
  "admin_role": "admin",
  "admin_status": "active",
  "last_login_at": "2026-02-13T10:30:00Z"
}
```

### Refresh Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "a1b2c3d4e5f6..."
  }'

# Response 200 OK
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "g7h8i9j0k1l2...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "a1b2c3d4e5f6..."
  }'

# Response 200 OK
{
  "message": "Logout successful"
}
```

---

**End of Auth API Layer Requirements**
