# Auth Module - Identity & Access Control Boundary

## 1. Purpose

**Why this module exists:**

The Auth module is the **single source of identity truth** and **access control enforcement** for the entire system. It:

- Manages user identities (admins, candidates, and future roles)
- Issues and validates JWT tokens (access + refresh)
- Enforces RBAC (Role-Based Access Control) for admin actions
- Provides **tenant isolation** (organization-level data boundaries)
- Authenticates WebSocket connections for real-time features
- Supports future WebRTC session validation for video interviews
- Maintains **immutable audit trail** of authentication events
- Prevents unauthorized access across organizational boundaries

**Critical responsibility:** If this module is compromised, the entire system collapses. Every other module **trusts** the identity claims issued by auth. There is no secondary authentication layer.

**Architectural principle:** Auth is a **boundary module** - it sits between the external world (unauthenticated requests) and the internal application (authenticated, authorized operations). It does NOT contain business logic beyond authorization.

---

## 2. Owned Tables / Entities

### Primary Tables

#### `users`

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    user_type VARCHAR(20) NOT NULL,  -- 'admin' | 'candidate'
    user_status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active' | 'inactive' | 'banned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,

    CONSTRAINT user_type_check CHECK (user_type IN ('admin', 'candidate')),
    CONSTRAINT user_status_check CHECK (user_status IN ('active', 'inactive', 'banned'))
);
```

#### `admins`

```sql
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    organization_id INT NOT NULL,
    admin_role VARCHAR(50) NOT NULL,  -- 'superadmin' | 'admin' | 'read_only'
    admin_status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active' | 'inactive'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT admin_role_check CHECK (admin_role IN ('superadmin', 'admin', 'read_only'))
);
```

#### `candidates`

```sql
CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    full_name VARCHAR(255),
    phone VARCHAR(50),
    resume_url TEXT,
    candidate_status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active' | 'inactive'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,  -- Hashed refresh token
    device_info TEXT,  -- User agent, device fingerprint
    ip_address VARCHAR(45),
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    revoked_reason VARCHAR(100),  -- 'logout' | 'password_change' | 'admin_action' | 'suspicious'

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `auth_audit_log`

```sql
CREATE TABLE auth_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT,
    event_type VARCHAR(50) NOT NULL,  -- 'login_success' | 'login_failure' | 'logout' | 'token_refresh' | 'password_change' | 'role_change'
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,  -- Additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

---

## 3. Input Contracts

### Registration Requests

#### AdminRegistrationRequest

```python
@dataclass
class AdminRegistrationRequest:
    email: str                          # REQUIRED: Valid email, unique
    password: str                       # REQUIRED: Min 8 chars, complexity rules
    organization_id: int                # REQUIRED: Organization to join
    admin_role: Literal["admin", "read_only"]  # REQUIRED: Cannot self-assign superadmin
    full_name: Optional[str] = None
```

#### CandidateRegistrationRequest

```python
@dataclass
class CandidateRegistrationRequest:
    email: str                          # REQUIRED: Valid email, unique
    password: str                       # REQUIRED: Min 8 chars
    full_name: Optional[str] = None
    phone: Optional[str] = None
```

### Authentication Requests

#### LoginRequest

```python
@dataclass
class LoginRequest:
    email: str                          # REQUIRED
    password: str                       # REQUIRED
    device_info: Optional[str] = None   # User agent fingerprint
    ip_address: Optional[str] = None    # For audit log
```

#### RefreshTokenRequest

```python
@dataclass
class RefreshTokenRequest:
    refresh_token: str                  # REQUIRED: Current refresh token
```

#### WebSocketAuthRequest

```python
@dataclass
class WebSocketAuthRequest:
    token: str                          # Access token from query param or header
    connection_id: str                  # WebSocket connection ID
```

---

## 4. Output Contracts

### Token Responses

#### LoginResponse

```python
@dataclass
class LoginResponse:
    access_token: str                   # JWT, short-lived (15-30 min)
    refresh_token: str                  # Opaque token, long-lived (7-30 days)
    token_type: str = "Bearer"
    expires_in: int                     # Seconds until access token expires
    user: UserProfile                   # Basic user info
```

#### UserProfile

```python
@dataclass
class UserProfile:
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]

    # Admin-specific
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None

    # Candidate-specific
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
```

### JWT Claims Structure

#### AdminAccessToken

```python
{
    "sub": user_id,                     # Subject (user ID)
    "type": "admin",                    # User type
    "admin_id": int,
    "organization_id": int,
    "role": "superadmin|admin|read_only",
    "iat": timestamp,                   # Issued at
    "exp": timestamp,                   # Expires at
    "jti": uuid,                        # JWT ID (for revocation)
    "token_version": int                # For forced logout
}
```

#### CandidateAccessToken

```python
{
    "sub": user_id,
    "type": "candidate",
    "candidate_id": int,
    "iat": timestamp,
    "exp": timestamp,
    "jti": uuid,
    "token_version": int
}
```

### Identity Context (Injected into Requests)

```python
@dataclass
class AuthContext:
    user_id: int
    user_type: Literal["admin", "candidate"]

    # Admin context
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None

    # Candidate context
    candidate_id: Optional[int] = None

    # Metadata
    token_jti: str                      # For revocation checks
    token_version: int                  # For forced logout
```

---

## 5. Acceptance Criteria

### Functional Requirements

#### 1. User Registration

- **Admin Registration:**
  - Validate email uniqueness across all users
  - Enforce password complexity (min 8 chars, uppercase, lowercase, number, special char)
  - Hash password with bcrypt (cost factor 12) or argon2id
  - Create `user` record with `user_type='admin'`, `user_status='active'`
  - Create `admin` record linked to organization
  - Log registration event to `auth_audit_log`
  - Cannot self-assign `superadmin` role (requires existing superadmin approval)

- **Candidate Registration:**
  - Same email/password validation
  - Create `user` + `candidate` records atomically
  - Default `candidate_status='active'`
  - No organization association

#### 2. Login & Token Issuance

- **Credential Validation:**
  - Lookup user by email (case-insensitive)
  - Verify password hash
  - Check `user_status='active'` (reject if inactive/banned)
  - For admins: check `admin_status='active'` and `organization.status='active'`
  - For admins: check `organization.status != 'suspended'`

- **Token Issuance:**
  - Generate access token (JWT, 15-30 min expiry)
  - Embed claims based on user type (admin vs candidate)
  - Generate refresh token (cryptographically random, 30 days expiry)
  - Store refresh token hash in `refresh_tokens` table
  - Return both tokens + user profile

- **Audit Logging:**
  - Log successful login with IP, user agent
  - Log failed login attempts with reason
  - Increment failed attempt counter (for rate limiting)

#### 3. Token Refresh

- **Validation:**
  - Lookup refresh token hash in `refresh_tokens`
  - Check not expired (`expires_at > NOW()`)
  - Check not revoked (`revoked_at IS NULL`)
  - Verify user still active

- **Rotation (Recommended):**
  - Revoke old refresh token
  - Issue new refresh token
  - Issue new access token
  - Detect token reuse (if old token used after rotation → revoke all user tokens, log suspicious activity)

#### 4. Logout

- **Token Revocation:**
  - Mark refresh token as revoked (`revoked_at=NOW()`, `revoked_reason='logout'`)
  - Optionally blacklist access token JTI (if revocation list maintained)
  - Log logout event

#### 5. RBAC Enforcement

- **Permission Matrix:**

| Action                       | superadmin | admin | read_only |
| ---------------------------- | ---------- | ----- | --------- |
| Create/delete admins         | ✅         | ❌    | ❌        |
| Modify organization settings | ✅         | ❌    | ❌        |
| Create interview templates   | ✅         | ✅    | ❌        |
| Edit interview templates     | ✅         | ✅    | ❌        |
| Create interviews            | ✅         | ✅    | ❌        |
| View submissions             | ✅         | ✅    | ✅        |
| Download reports             | ✅         | ✅    | ✅        |
| Access admin analytics       | ✅         | ✅    | ✅        |
| Manage candidates            | ✅         | ✅    | ❌        |

- **Enforcement:**
  - Decorators or middleware check `admin_role` from token
  - Raise `ForbiddenError` if insufficient permissions
  - Superadmin bypass optional (design decision)

#### 6. Tenant Isolation

- **For Admin Requests:**
  - Extract `organization_id` from access token
  - Inject into all repository queries as filter
  - Admin from org A **cannot** query data from org B
  - Enforced at **repository layer**, not just API layer

- **For Candidate Requests:**
  - No organization filtering (candidates not tenant-scoped)
  - Filter by `candidate_id` from token

- **Superadmin Override:**
  - Design decision: allow superadmin to query across orgs (for support)
  - If enabled, add explicit flag in queries

#### 7. WebSocket Authentication

- **Connection Upgrade:**
  - Accept JWT in query param (`?token=...`) or `Authorization` header
  - Validate token before accepting connection
  - Reject if expired, invalid signature, or user inactive
  - Bind socket to `user_id`, `organization_id`, `role`

- **Mid-Session Expiration:**
  - Optionally close socket if token expires mid-session
  - Or allow grace period, client must refresh

#### 8. WebRTC Authentication (Future)

- **Session Token:**
  - Before establishing WebRTC stream, client requests ephemeral session token
  - Session token valid for 1 hour, scoped to `submission_id`
  - WebRTC server validates session token before accepting stream

- **Auth Module Responsibility:**
  - Provide reusable `validate_token()` function for HTTP, WS, WebRTC

### Non-Functional Requirements

1. **Performance:**
   - Login: <200ms p95
   - Token validation: <10ms p95 (in-memory signature verification)
   - Token refresh: <100ms p95

2. **Security:**
   - Password hashing: bcrypt (cost 12) or argon2id
   - JWT signing: RS256 (RSA) recommended over HS256 (shared secret)
   - Refresh token: cryptographically random (32+ bytes)
   - Rate limiting: 5 failed login attempts per IP per 15 min

3. **Audit Trail:**
   - All auth events logged to `auth_audit_log`
   - Retention: 90 days minimum (compliance requirement)
   - Immutable: no updates or deletes allowed

---

## 6. Invariants & Constraints

### Must Hold

1. **Email Uniqueness:** One email maps to exactly one user across all user types
2. **User Status Enforcement:** Inactive/banned users cannot login
3. **Admin-Organization Link:** Every admin belongs to exactly one organization
4. **Candidate Independence:** Candidates have no organization association
5. **Refresh Token Uniqueness:** Each refresh token hash is unique
6. **Token Expiration:** Expired tokens always rejected
7. **Revoked Token Immutability:** Once revoked, refresh token cannot be un-revoked
8. **Password Irreversibility:** Password hash never reversible, never exposed in API
9. **Organization Status Enforcement:** Admin from suspended org cannot login
10. **Audit Log Immutability:** Auth events never deleted or modified

### Forbidden

- MUST NOT store plaintext passwords
- MUST NOT expose password hash in any API response
- MUST NOT allow admin to query data from other organizations (unless superadmin override)
- MUST NOT allow candidate to self-assign admin role
- MUST NOT allow `superadmin` role assignment via registration (requires existing superadmin)
- MUST NOT skip audit logging for any auth event
- MUST NOT reuse revoked refresh tokens
- MUST NOT embed business logic (interview state, templates) in auth module
- MUST NOT accept unsigned or tampered JWTs
- MUST NOT allow token signature algorithm to be `none`

---

## 7. Dependent Modules

### Upstream (Callers)

1. **API Gateway / Middleware:**
   - Validates access token on every protected request
   - Injects `AuthContext` into request context
   - Returns 401 if token invalid/expired

2. **Admin Module (`app.admin`):**
   - Uses RBAC to enforce permissions on template/rubric operations
   - Filters queries by `organization_id` from `AuthContext`

3. **Interview Module (`app.interview`):**
   - Verifies candidate identity before starting interview
   - Binds submission to `candidate_id` from token
   - Admin viewing submissions filtered by `organization_id`

4. **WebSocket Gateway:**
   - Validates token before accepting connection
   - Binds socket to user identity

### Downstream (Dependencies)

1. **Database (PostgreSQL):**
   - Stores users, admins, candidates, refresh tokens, audit logs
   - Enforces UNIQUE, CHECK, FK constraints

2. **JWT Library (`PyJWT`, `jose`):**
   - Signs and verifies JWTs
   - RS256 signing with public/private key pair

3. **Password Hashing (`bcrypt`, `argon2-cffi`):**
   - Hashes passwords on registration
   - Verifies passwords on login

4. **Email Service (Optional, Future):**
   - Sends verification emails
   - Password reset emails

---

## 8. Event Contracts Emitted

### AuthEvent

```python
@dataclass
class AuthEvent:
    event_type: Literal[
        "user_registered",
        "login_success",
        "login_failure",
        "logout",
        "token_refreshed",
        "password_changed",
        "admin_role_changed",
        "user_status_changed",
        "refresh_token_revoked",
        "suspicious_activity"
    ]
    user_id: Optional[int]
    organization_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Dict[str, Any]
    timestamp: datetime
```

### Consumers

1. **Audit Service (Future):**
   - Consumes auth events for compliance reporting
   - Aggregates suspicious activity

2. **Notification Service (Future):**
   - Sends email on suspicious login
   - Sends email on password change

3. **Analytics Service:**
   - Tracks login frequency
   - Identifies inactive users

---

## 9. Invariant Alignment with ERD

### User Status Enforcement

From ERD: `user_status` can be `active`, `inactive`, `banned`.

**Auth must enforce:**

- `inactive`: User cannot login, but data preserved
- `banned`: User cannot login, admin intervention required
- Status change revokes all active tokens

### Admin Status Enforcement

From ERD: `admin_status` can be `active`, `inactive`.

**Auth must enforce:**

- `inactive`: Admin cannot login, but record preserved
- Admin status change revokes active sessions

### Organization Status Enforcement

From ERD: `organization_status` can be `active`, `inactive`, `suspended`.

**Auth must enforce:**

- `suspended`: All admins from org blocked from login
- Organization suspension revokes all admin tokens for that org

### Cascade Delete Behavior

From ERD:

- Delete user → cascade to admin/candidate
- Delete organization → cascade to admins (but not interviews/submissions, per ERD)

**Auth must:**

- Revoke all tokens on user deletion
- Log deletion event before cascade

---

## 10. Edge Cases to Handle

### 1. Expired Token During Request

- **Scenario:** Client sends expired access token
- **Handling:** Return 401 Unauthorized with `token_expired` error code
- **Client Action:** Client should refresh token automatically

### 2. Revoked Refresh Token Reuse

- **Scenario:** Client tries to use already-revoked refresh token
- **Handling:** Return 401 with `token_revoked` error code
- **Security:** Log as suspicious activity (possible token theft)
- **Action:** Revoke ALL refresh tokens for that user

### 3. Organization Suspended Mid-Session

- **Scenario:** Admin logged in, org gets suspended
- **Handling:** Next API call should fail with 403 Forbidden
- **Token:** Access token still valid until expiry, but org status check fails
- **Future:** Maintain active session list, revoke immediately on suspension

### 4. Admin Role Downgraded Mid-Session

- **Scenario:** Admin with `admin` role has token, role changed to `read_only`
- **Handling:** Token still claims `admin` role until expiry
- **Mitigation:** Short access token expiry (15 min)
- **Alternative:** Increment `token_version` in user record, reject old version

### 5. Concurrent Login from Multiple Devices

- **Scenario:** User logs in from phone and laptop simultaneously
- **Handling:** Allow (default behavior)
- **Option:** Limit to 1 active session (per device) via token store

### 6. Password Change

- **Scenario:** User changes password
- **Handling:** Revoke ALL refresh tokens for that user
- **Access Tokens:** Still valid until expiry (tradeoff: UX vs security)
- **Mitigation:** Short access token expiry

### 7. Duplicate Email Registration

- **Scenario:** User tries to register with existing email
- **Handling:** Return 409 Conflict with `email_already_exists` error
- **Security:** Don't reveal if email exists (privacy concern vs UX tradeoff)

### 8. Brute Force Login Attempts

- **Scenario:** Attacker tries multiple passwords for same email
- **Handling:** Rate limit: 5 attempts per IP per 15 min
- **Action:** Return 429 Too Many Requests
- **Future:** Account lockout after 10 failed attempts

### 9. Token Signature Mismatch

- **Scenario:** Token tampered with or signed with wrong key
- **Handling:** Reject immediately with 401
- **Log:** Log as suspicious activity

### 10. WebSocket Token Expiry Mid-Session

- **Scenario:** User connected via WebSocket, access token expires
- **Handling:** Option A: Close socket, client must reconnect
- **Handling:** Option B: Allow grace period, client refreshes in background

---

## 11. Concurrency Concerns

### 1. Simultaneous Registration

- **Scenario:** Two users try to register with same email simultaneously
- **Handling:** Database UNIQUE constraint on email
- **Result:** One succeeds, one fails with IntegrityError → return 409 Conflict

### 2. Concurrent Token Refresh

- **Scenario:** Client sends two refresh requests simultaneously (network issue)
- **Handling:** First request rotates token, second request fails (token already revoked)
- **Client Action:** Client should retry with new token

### 3. Concurrent Password Change + Login

- **Scenario:** User changes password while another device tries to login with old password
- **Handling:** Login fails (password mismatch)
- **Token Revocation:** Password change revokes tokens after commit
- **Race:** Login might succeed if it commits before password change (acceptable)

### 4. Admin Role Change During Request

- **Scenario:** Superadmin changes admin role from `admin` to `read_only` while admin is making edit request
- **Handling:** Token still claims `admin` until expiry (eventual consistency)
- **Mitigation:** Check `token_version` on sensitive operations

### 5. Organization Suspension During Request

- **Scenario:** Admin making request, org gets suspended mid-request
- **Handling:** Request completes if token validation passed at start
- **Next Request:** Next API call checks org status, fails with 403

---

## 12. Security Considerations

### Password Security

- **Hashing:** bcrypt (cost 12) or argon2id (memory-hard)
- **Complexity:** Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
- **Storage:** Never plaintext, never reversible
- **Reset:** Future: email-based reset with expiring token

### Token Security

- **JWT Signing:** RS256 (public/private key) > HS256 (shared secret)
- **Key Management:** Private key stored securely (env var, secrets manager)
- **Public Key:** Distribute to services for validation
- **Algorithm Enforcement:** Reject `alg=none` tokens

### Refresh Token Security

- **Generation:** Cryptographically random (32+ bytes)
- **Storage:** Hashed in database (like passwords)
- **Rotation:** Recommended to prevent replay attacks
- **Reuse Detection:** If revoked token used → revoke all user tokens

### Rate Limiting

- **Login:** 5 failed attempts per IP per 15 min
- **Token Refresh:** 10 requests per user per minute
- **Registration:** 3 registrations per IP per hour

### Audit Logging

- **Events:** Login success/failure, logout, token refresh, password change, role change
- **Data:** User ID, IP, user agent, timestamp, metadata
- **Retention:** 90 days minimum (compliance)
- **Immutability:** No updates or deletes allowed

### Token Revocation

- **Refresh Tokens:** Stored in DB, revocation immediate
- **Access Tokens:** Stateless, revocation requires blacklist or short expiry
- **Strategy:** Short access token expiry (15-30 min) + refresh token rotation

### Tenant Isolation

- **Repository Layer:** Inject `organization_id` filter from token
- **Enforcement:** Cannot be bypassed at API layer
- **Testing:** Must test cross-tenant access attempts

---

## 13. Future Enhancements

1. **Email Verification:**
   - Send verification email on registration
   - User cannot login until verified

2. **Password Reset:**
   - Email-based reset flow
   - Expiring reset tokens (1 hour)

3. **Multi-Factor Authentication (MFA):**
   - TOTP (Time-based One-Time Password)
   - SMS-based OTP
   - Required for admins, optional for candidates

4. **OAuth / SSO:**
   - Google, GitHub, Microsoft login
   - SAML for enterprise customers

5. **Session Management:**
   - View active sessions
   - Revoke specific sessions
   - Device fingerprinting

6. **Account Lockout:**
   - Automatic lockout after 10 failed attempts
   - Admin unlock required

7. **Suspicious Activity Detection:**
   - Login from new location
   - Login from new device
   - Multiple failed attempts

8. **Token Introspection:**
   - Validate token status in real-time
   - Check revocation list

9. **API Keys:**
   - Long-lived API keys for integrations
   - Scoped permissions

10. **Biometric Authentication:**
    - WebAuthn for passwordless login
    - Fingerprint, Face ID

---

## 14. Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=<private_key_for_signing>  # RS256 private key
JWT_PUBLIC_KEY=<public_key_for_verification>
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Password Security
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_DIGIT=true
PASSWORD_REQUIRE_SPECIAL=true
BCRYPT_COST_FACTOR=12

# Rate Limiting
LOGIN_RATE_LIMIT_ATTEMPTS=5
LOGIN_RATE_LIMIT_WINDOW_MINUTES=15
REFRESH_RATE_LIMIT_ATTEMPTS=10
REFRESH_RATE_LIMIT_WINDOW_MINUTES=1

# Audit Logging
AUTH_AUDIT_LOG_RETENTION_DAYS=90

# Refresh Token Rotation
REFRESH_TOKEN_ROTATION_ENABLED=true
REFRESH_TOKEN_REUSE_DETECTION=true

# Organization Checks
CHECK_ORG_STATUS_ON_LOGIN=true
CHECK_ORG_STATUS_ON_REQUEST=true
```

---

**End of Auth Module Requirements**
