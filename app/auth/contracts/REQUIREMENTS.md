# Auth Contracts Layer - Schemas & Data Transfer Objects

## 1. Purpose

**Why this submodule exists:**

The Auth Contracts layer defines **strict schemas** for all auth-related data transfer between layers and external systems. It:

- Defines request/response schemas (Pydantic models)
- Defines JWT claim structures
- Defines `AuthContext` injected into requests
- Ensures type safety across module boundaries
- Provides validation rules
- Documents public API contracts

**Critical responsibility:** This is the **contract layer** - any change here affects API consumers. Versioning and backward compatibility are critical.

---

## 2. Owned Tables / Entities

**None.** This layer contains only data structures (schemas), no database access.

---

## 3. Input / Output Contracts

Since this IS the contracts layer, all contracts defined here ARE the input/output.

---

## 4. Schema Definitions

### Request Schemas

#### AdminRegistrationRequest

```python
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Literal, Optional

class AdminRegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_id: int = Field(gt=0)
    admin_role: Literal["admin", "read_only"]
    full_name: Optional[str] = Field(None, max_length=255)

    @validator('password')
    def validate_password_complexity(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

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

#### CandidateRegistrationRequest

```python
class CandidateRegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)

    @validator('password')
    def validate_password_complexity(cls, v):
        # Same validation as AdminRegistrationRequest
        ...

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

#### LoginRequest

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }
```

#### RefreshTokenRequest

```python
class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)
```

#### LogoutRequest

```python
class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)
```

---

### Response Schemas

#### RegistrationResponse

```python
class RegistrationResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    message: str = "Registration successful"

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "email": "user@example.com",
                "user_type": "admin",
                "message": "Registration successful"
            }
        }
```

#### LoginResponse

```python
class UserProfileResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]

    # Admin fields
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[Literal["superadmin", "admin", "read_only"]] = None

    # Candidate fields
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # Seconds until access token expires
    user: UserProfileResponse

    class Config:
        json_schema_extra = {
            "example": {
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
        }
```

#### TokenRefreshResponse

```python
class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str  # New refresh token if rotation enabled
    token_type: str = "Bearer"
    expires_in: int

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "g7h8i9j0k1l2...",
                "token_type": "Bearer",
                "expires_in": 900
            }
        }
```

#### CurrentUserResponse

```python
from datetime import datetime

class CurrentUserResponse(BaseModel):
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    user_status: Literal["active", "inactive", "banned"]

    # Admin context
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[Literal["superadmin", "admin", "read_only"]] = None
    admin_status: Optional[Literal["active", "inactive"]] = None

    # Candidate context
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
    candidate_status: Optional[Literal["active", "inactive"]] = None

    last_login_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
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
        }
```

#### ErrorResponse

```python
from typing import Any, Dict

class ErrorResponse(BaseModel):
    error: str  # Machine-readable error code
    message: str  # Human-readable message
    details: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "invalid_credentials",
                "message": "Email or password is incorrect",
                "details": None
            }
        }
```

---

### JWT Claim Structures

#### AdminAccessTokenClaims

```python
from typing import TypedDict

class AdminAccessTokenClaims(TypedDict):
    sub: int  # Subject (user_id)
    type: str  # "admin"
    admin_id: int
    organization_id: int
    role: str  # "superadmin" | "admin" | "read_only"
    iat: int  # Issued at (timestamp)
    exp: int  # Expires at (timestamp)
    jti: str  # JWT ID (unique identifier)
    token_version: int  # For forced logout
```

#### CandidateAccessTokenClaims

```python
class CandidateAccessTokenClaims(TypedDict):
    sub: int  # Subject (user_id)
    type: str  # "candidate"
    candidate_id: int
    iat: int
    exp: int
    jti: str
    token_version: int
```

---

### AuthContext (Injected into Requests)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

@dataclass
class AuthContext:
    """Identity context injected into authenticated requests"""
    user_id: int
    user_type: Literal["admin", "candidate"]

    # Admin context
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[Literal["superadmin", "admin", "read_only"]] = None

    # Candidate context
    candidate_id: Optional[int] = None

    # Token metadata
    token_jti: str = ""
    token_version: int = 0
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def is_admin(self) -> bool:
        return self.user_type == "admin"

    def is_candidate(self) -> bool:
        return self.user_type == "candidate"

    def is_superadmin(self) -> bool:
        return self.user_type == "admin" and self.admin_role == "superadmin"

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission (delegates to RBAC enforcer)"""
        from app.auth.domain.rbac import RBACEnforcer
        return RBACEnforcer().has_permission(self, permission)

    def require_permission(self, permission: str):
        """Raise exception if user lacks permission"""
        if not self.has_permission(permission):
            from app.auth.domain.exceptions import InsufficientPermissionsError
            raise InsufficientPermissionsError(f"Missing permission: {permission}")

    def get_tenant_filter(self) -> Optional[int]:
        """Get organization_id for tenant filtering (returns None for candidates)"""
        return self.organization_id if self.is_admin() else None
```

---

## 5. Acceptance Criteria

### Functional Requirements

1. **Validation:**
   - All request schemas validated by Pydantic
   - Invalid data raises `ValidationError` with detailed messages

2. **Serialization:**
   - All response schemas serializable to JSON
   - Datetime fields formatted as ISO 8601

3. **Type Safety:**
   - All fields have explicit types
   - Optional fields marked with `Optional[]`
   - Literal types for enums

4. **Documentation:**
   - All schemas have examples
   - All fields have descriptions (via Pydantic Field)

### Non-Functional Requirements

1. **Backward Compatibility:**
   - Breaking changes require API versioning
   - Deprecated fields marked but not removed

2. **Security:**
   - Password fields never included in response schemas
   - Token fields never logged

---

## 6. Invariants & Constraints

### Must Hold

1. **Password Never in Response:** No response schema contains `password` or `password_hash`
2. **Email Always Lowercase:** Email stored and compared in lowercase
3. **Token Type Consistency:** Admin tokens always have `organization_id`, candidates never do
4. **Claim Completeness:** JWT claims include all required fields for authorization

### Forbidden

- MUST NOT include password fields in any response schema
- MUST NOT serialize `password_hash` to JSON
- MUST NOT expose internal IDs beyond necessary (e.g., no database sequence values)
- MUST NOT include sensitive metadata in error responses (no stack traces in production)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **API Layer:** Uses request/response schemas
2. **Middleware:** Uses `AuthContext`
3. **All Protected Endpoints:** Depend on `AuthContext`

### Downstream (Dependencies)

1. **Pydantic:** Schema validation
2. **Python typing:** Type hints

---

## 8. Error Code Definitions

```python
from enum import Enum

class AuthErrorCode(str, Enum):
    # Authentication errors
    INVALID_CREDENTIALS = "invalid_credentials"
    USER_INACTIVE = "user_inactive"
    USER_BANNED = "user_banned"
    ADMIN_INACTIVE = "admin_inactive"
    ORG_SUSPENDED = "organization_suspended"
    ORG_INACTIVE = "organization_inactive"

    # Token errors
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TOKEN_REVOKED = "token_revoked"
    REFRESH_TOKEN_INVALID = "refresh_token_invalid"
    REFRESH_TOKEN_EXPIRED = "refresh_token_expired"

    # Registration errors
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    PASSWORD_TOO_WEAK = "password_too_weak"
    ORG_NOT_FOUND = "organization_not_found"

    # Authorization errors
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    MISSING_TOKEN = "missing_token"

    # Security errors
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
```

---

## 9. Example Usage

### Using Request Schemas

```python
from app.auth.contracts import LoginRequest

# Pydantic validates automatically
try:
    request = LoginRequest(
        email="user@example.com",
        password="SecurePass123!"
    )
except ValidationError as e:
    print(e.json())
```

### Using Response Schemas

```python
from app.auth.contracts import LoginResponse, UserProfileResponse

# Build response
response = LoginResponse(
    access_token="eyJhbGci...",
    refresh_token="a1b2c3...",
    expires_in=900,
    user=UserProfileResponse(
        user_id=123,
        email="user@example.com",
        user_type="admin",
        admin_id=1,
        organization_id=1,
        admin_role="admin"
    )
)

# Serialize to JSON
return response.dict()
```

### Using AuthContext

```python
from app.auth.contracts import AuthContext

# Injected by middleware
def protected_endpoint(auth: AuthContext):
    # Check permissions
    auth.require_permission('create_templates')

    # Get tenant filter
    org_id = auth.get_tenant_filter()  # Returns organization_id for admins, None for candidates

    # Query with tenant filter
    templates = template_repo.list(organization_id=org_id)
```

---

## 10. Validation Rules

### Email Validation

- Must be valid email format (Pydantic `EmailStr`)
- Stored lowercase for case-insensitive comparison

### Password Validation

- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character

### Token Validation

- JWT: valid signature, not expired
- Refresh token: 32-256 characters (cryptographically random)

---

## 11. Future Enhancements

1. **API Versioning:**
   - `/api/v1/auth/*` vs `/api/v2/auth/*`
   - Support multiple schema versions

2. **Custom Validators:**
   - Email domain whitelist/blacklist
   - Phone number format validation

3. **Localization:**
   - Error messages in multiple languages
   - Accept-Language header support

4. **Schema Evolution:**
   - Deprecation warnings for old fields
   - Migration guides

---

**End of Auth Contracts Layer Requirements**
