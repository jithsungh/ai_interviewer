# Auth Domain Layer - Core Authentication Logic

## 1. Purpose

**Why this submodule exists:**

The Auth Domain layer contains the **core business logic** for identity and access control. It:

- Implements authentication workflows (registration, login, logout)
- Issues and validates JWT tokens (access + refresh)
- Enforces RBAC (Role-Based Access Control) rules
- Manages password hashing and verification
- Handles token rotation and revocation
- Orchestrates tenant isolation enforcement
- Emits audit events for all auth operations

**Critical responsibility:** This is the **brain** of the auth module. All authentication decisions happen here. The API layer is a thin HTTP wrapper around this logic.

**Architectural principle:** Domain layer contains **zero HTTP concerns**. It works with domain objects, not HTTP requests.

---

## 2. Owned Tables / Entities

**None directly.** Domain layer **uses** repositories from `persistence` layer but does not own database access.

---

## 3. Input Contracts

### Domain Commands

#### RegisterAdminCommand

```python
@dataclass
class RegisterAdminCommand:
    email: str
    password: str
    organization_id: int
    admin_role: Literal["admin", "read_only"]
    full_name: Optional[str] = None
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
```

#### RegisterCandidateCommand

```python
@dataclass
class RegisterCandidateCommand:
    email: str
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
```

#### LoginCommand

```python
@dataclass
class LoginCommand:
    email: str
    password: str
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
    device_info: Optional[str] = None
```

#### RefreshTokenCommand

```python
@dataclass
class RefreshTokenCommand:
    refresh_token: str
    request_ip: Optional[str] = None
```

#### LogoutCommand

```python
@dataclass
class LogoutCommand:
    refresh_token: str
    request_ip: Optional[str] = None
```

---

## 4. Output Contracts

### Domain Results

#### AuthenticationResult

```python
@dataclass
class AuthenticationResult:
    access_token: str                   # JWT
    refresh_token: str                  # Opaque token
    token_type: str = "Bearer"
    expires_in: int                     # Seconds
    user_profile: UserProfile
```

#### UserProfile

```python
@dataclass
class UserProfile:
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    user_status: str

    # Admin fields
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None
    admin_status: Optional[str] = None

    # Candidate fields
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
    candidate_status: Optional[str] = None

    last_login_at: Optional[datetime] = None
```

#### TokenValidationResult

```python
@dataclass
class TokenValidationResult:
    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None         # 'expired', 'invalid_signature', 'revoked'
    auth_context: Optional[AuthContext] = None
```

#### AuthContext

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

    # Token metadata
    token_jti: str                      # JWT ID
    token_version: int                  # For forced logout
    issued_at: datetime
    expires_at: datetime
```

---

## 5. Acceptance Criteria

### Functional Requirements

#### 1. User Registration

**Admin Registration:**

```python
class AuthService:
    def register_admin(self, command: RegisterAdminCommand) -> UserProfile:
        # 1. Validate password complexity
        self._validate_password_complexity(command.password)

        # 2. Check email uniqueness
        if self.user_repo.email_exists(command.email):
            raise EmailAlreadyExistsError()

        # 3. Validate organization exists and is active
        org = self.org_repo.get_by_id(command.organization_id)
        if not org or org.status != 'active':
            raise OrganizationNotFoundError()

        # 4. Hash password
        password_hash = self.password_hasher.hash(command.password)

        # 5. Create user record
        user = self.user_repo.create(
            email=command.email,
            password_hash=password_hash,
            user_type='admin',
            user_status='active'
        )

        # 6. Create admin record
        admin = self.admin_repo.create(
            user_id=user.id,
            organization_id=command.organization_id,
            admin_role=command.admin_role,
            admin_status='active'
        )

        # 7. Emit audit event
        self.event_emitter.emit(AuthEvent(
            event_type='user_registered',
            user_id=user.id,
            organization_id=command.organization_id,
            ip_address=command.request_ip,
            metadata={'user_type': 'admin', 'admin_role': command.admin_role}
        ))

        # 8. Return profile
        return self._build_user_profile(user, admin)
```

**Candidate Registration:**

- Similar flow but no organization validation
- Create user + candidate records atomically

#### 2. Login & Token Issuance

```python
class AuthService:
    def login(self, command: LoginCommand) -> AuthenticationResult:
        # 1. Find user by email (case-insensitive)
        user = self.user_repo.find_by_email(command.email.lower())
        if not user:
            self._log_failed_login(command.email, 'user_not_found', command.request_ip)
            raise InvalidCredentialsError()

        # 2. Verify password
        if not self.password_hasher.verify(command.password, user.password_hash):
            self._log_failed_login(user.id, 'invalid_password', command.request_ip)
            raise InvalidCredentialsError()

        # 3. Check user status
        if user.user_status != 'active':
            raise UserInactiveError(f"User is {user.user_status}")

        # 4. If admin, validate admin & org status
        if user.user_type == 'admin':
            admin = self.admin_repo.find_by_user_id(user.id)
            if admin.admin_status != 'active':
                raise AdminInactiveError()

            org = self.org_repo.get_by_id(admin.organization_id)
            if org.status == 'suspended':
                raise OrganizationSuspendedError()
            if org.status != 'active':
                raise OrganizationInactiveError()

        # 5. Generate access token (JWT)
        access_token = self.token_generator.generate_access_token(user)

        # 6. Generate refresh token
        refresh_token = self.token_generator.generate_refresh_token()

        # 7. Store refresh token (hashed)
        self.refresh_token_repo.create(
            user_id=user.id,
            token_hash=self.token_hasher.hash(refresh_token),
            device_info=command.device_info,
            ip_address=command.request_ip,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

        # 8. Update last login
        self.user_repo.update_last_login(user.id)

        # 9. Emit success event
        self.event_emitter.emit(AuthEvent(
            event_type='login_success',
            user_id=user.id,
            ip_address=command.request_ip,
            user_agent=command.request_user_agent
        ))

        # 10. Return tokens + profile
        return AuthenticationResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.access_token_ttl_seconds,
            user_profile=self._build_user_profile(user)
        )
```

#### 3. Token Validation

```python
class AuthService:
    def validate_access_token(self, token: str) -> TokenValidationResult:
        try:
            # 1. Verify JWT signature
            claims = self.jwt_validator.verify(token)

            # 2. Check expiration
            if datetime.fromtimestamp(claims['exp']) < datetime.utcnow():
                return TokenValidationResult(valid=False, error='expired')

            # 3. Extract user_id
            user_id = claims['sub']

            # 4. Check user still active
            user = self.user_repo.get_by_id(user_id)
            if not user or user.user_status != 'active':
                return TokenValidationResult(valid=False, error='user_inactive')

            # 5. Check token version (for forced logout)
            if claims.get('token_version', 0) < user.token_version:
                return TokenValidationResult(valid=False, error='token_revoked')

            # 6. If admin, check org status
            if claims.get('type') == 'admin':
                org = self.org_repo.get_by_id(claims['organization_id'])
                if org.status == 'suspended':
                    return TokenValidationResult(valid=False, error='org_suspended')

            # 7. Build AuthContext
            auth_context = self._build_auth_context(claims)

            return TokenValidationResult(
                valid=True,
                claims=claims,
                auth_context=auth_context
            )

        except JWTSignatureError:
            return TokenValidationResult(valid=False, error='invalid_signature')
        except Exception as e:
            return TokenValidationResult(valid=False, error=str(e))
```

#### 4. Token Refresh

```python
class AuthService:
    def refresh_token(self, command: RefreshTokenCommand) -> AuthenticationResult:
        # 1. Hash incoming token
        token_hash = self.token_hasher.hash(command.refresh_token)

        # 2. Find token in DB
        stored_token = self.refresh_token_repo.find_by_hash(token_hash)
        if not stored_token:
            raise InvalidRefreshTokenError()

        # 3. Check not expired
        if stored_token.expires_at < datetime.utcnow():
            raise RefreshTokenExpiredError()

        # 4. Check not revoked
        if stored_token.revoked_at is not None:
            # Token reuse detected! Revoke all tokens for this user
            self.refresh_token_repo.revoke_all_for_user(stored_token.user_id, reason='token_reuse')
            self.event_emitter.emit(AuthEvent(
                event_type='suspicious_activity',
                user_id=stored_token.user_id,
                ip_address=command.request_ip,
                metadata={'reason': 'refresh_token_reuse'}
            ))
            raise SuspiciousActivityError("Refresh token reused")

        # 5. Get user
        user = self.user_repo.get_by_id(stored_token.user_id)
        if user.user_status != 'active':
            raise UserInactiveError()

        # 6. If rotation enabled, revoke old token
        if self.config.refresh_token_rotation_enabled:
            self.refresh_token_repo.revoke(stored_token.id, reason='rotation')

        # 7. Generate new access token
        access_token = self.token_generator.generate_access_token(user)

        # 8. Generate new refresh token (if rotation enabled)
        if self.config.refresh_token_rotation_enabled:
            new_refresh_token = self.token_generator.generate_refresh_token()
            self.refresh_token_repo.create(
                user_id=user.id,
                token_hash=self.token_hasher.hash(new_refresh_token),
                device_info=stored_token.device_info,
                ip_address=command.request_ip,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
        else:
            new_refresh_token = command.refresh_token

        # 9. Emit event
        self.event_emitter.emit(AuthEvent(
            event_type='token_refreshed',
            user_id=user.id,
            ip_address=command.request_ip
        ))

        return AuthenticationResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self.config.access_token_ttl_seconds,
            user_profile=self._build_user_profile(user)
        )
```

#### 5. Logout

```python
class AuthService:
    def logout(self, command: LogoutCommand):
        # 1. Hash token
        token_hash = self.token_hasher.hash(command.refresh_token)

        # 2. Find token
        stored_token = self.refresh_token_repo.find_by_hash(token_hash)
        if not stored_token:
            # Already revoked or invalid, idempotent
            return

        # 3. Revoke token
        self.refresh_token_repo.revoke(stored_token.id, reason='logout')

        # 4. Emit event
        self.event_emitter.emit(AuthEvent(
            event_type='logout',
            user_id=stored_token.user_id,
            ip_address=command.request_ip
        ))
```

#### 6. RBAC Enforcement

```python
class RBACEnforcer:
    PERMISSION_MATRIX = {
        'superadmin': [
            'manage_admins',
            'manage_organization',
            'create_templates',
            'edit_templates',
            'delete_templates',
            'create_interviews',
            'view_submissions',
            'download_reports',
            'manage_candidates',
            'view_analytics'
        ],
        'admin': [
            'create_templates',
            'edit_templates',
            'create_interviews',
            'view_submissions',
            'download_reports',
            'manage_candidates',
            'view_analytics'
        ],
        'read_only': [
            'view_submissions',
            'download_reports',
            'view_analytics'
        ]
    }

    def has_permission(self, auth_context: AuthContext, permission: str) -> bool:
        if auth_context.user_type != 'admin':
            return False

        allowed_permissions = self.PERMISSION_MATRIX.get(auth_context.admin_role, [])
        return permission in allowed_permissions

    def require_permission(self, auth_context: AuthContext, permission: str):
        if not self.has_permission(auth_context, permission):
            raise InsufficientPermissionsError(
                f"User does not have permission: {permission}"
            )
```

### Non-Functional Requirements

1. **Password Hashing:**
   - bcrypt (cost factor 12) or argon2id
   - Verification time: <100ms p95

2. **JWT Generation:**
   - RS256 signing with private key
   - Generation time: <50ms p95

3. **JWT Validation:**
   - Signature verification with public key
   - Validation time: <10ms p95

4. **Token Expiry:**
   - Access token: 15-30 minutes
   - Refresh token: 7-30 days

---

## 6. Invariants & Constraints

### Must Hold

1. **Password Never Plaintext:** Passwords always hashed before storage
2. **Token JTI Uniqueness:** Each access token has unique JTI (JWT ID)
3. **Refresh Token Hashing:** Refresh tokens hashed before storage (like passwords)
4. **User Status Check:** Always validate user status before issuing tokens
5. **Organization Status Check:** Always validate org status for admin logins
6. **Token Rotation:** If enabled, old refresh token must be revoked before issuing new
7. **Audit Logging:** All auth events logged, no exceptions

### Forbidden

- MUST NOT store plaintext passwords
- MUST NOT skip password complexity validation
- MUST NOT issue tokens to inactive/banned users
- MUST NOT issue admin tokens if org suspended
- MUST NOT allow token reuse after revocation
- MUST NOT embed sensitive data in JWT claims (no password hashes, internal IDs beyond necessary)
- MUST NOT accept tampered JWTs

---

## 7. Dependent Modules

### Upstream (Callers)

1. **API Layer (`app.auth.api`):**
   - Calls domain service methods
   - Passes commands
   - Returns domain results

### Downstream (Dependencies)

1. **Persistence Layer (`app.auth.persistence`):**
   - `UserRepository`
   - `AdminRepository`
   - `CandidateRepository`
   - `RefreshTokenRepository`
   - `AuthAuditLogRepository`

2. **Organization Repository (`app.admin.persistence`):**
   - Validate organization exists and is active

3. **Cryptography Libraries:**
   - `bcrypt` or `argon2-cffi` for password hashing
   - `PyJWT` or `python-jose` for JWT operations

4. **Event Emitter:**
   - Emits `AuthEvent` for audit logging

---

## 8. Event Contracts Emitted

### AuthEvent

```python
@dataclass
class AuthEvent:
    event_type: Literal[
        'user_registered',
        'login_success',
        'login_failure',
        'logout',
        'token_refreshed',
        'password_changed',
        'admin_role_changed',
        'user_status_changed',
        'refresh_token_revoked',
        'suspicious_activity'
    ]
    user_id: Optional[int]
    organization_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

**Consumers:**

- `AuthAuditLogRepository` (persists to `auth_audit_log` table)
- Future: Analytics service, notification service

---

## 9. Edge Cases to Handle

### 1. Password Change During Active Session

- Revoke all refresh tokens for user
- Access tokens still valid until expiry (tradeoff)
- Increment `token_version` to invalidate access tokens

### 2. Admin Role Changed During Session

- Token still claims old role until expiry
- Check `token_version` on sensitive operations
- Or force re-login on role change

### 3. Organization Suspended During Session

- Next request with org status check fails
- Active access tokens rejected
- Refresh tokens revoked

### 4. Refresh Token Reuse (Attack Scenario)

- Detect: Token already revoked but used again
- Action: Revoke ALL refresh tokens for user
- Log as suspicious activity
- Notify user (future)

### 5. Concurrent Refresh Requests

- Two refresh requests with same token simultaneously
- First succeeds, revokes token
- Second fails (token revoked)
- Client should retry with new token

### 6. Token Validation Failure

- Invalid signature → reject immediately
- Expired token → return specific error code
- User inactive → reject
- Org suspended → reject with specific error

---

## 10. Concurrency Concerns

### 1. Concurrent Registration

- Database UNIQUE constraint on email prevents duplicates
- One succeeds, one fails with constraint error
- Domain layer catches and raises `EmailAlreadyExistsError`

### 2. Concurrent Login

- Allowed (same user can have multiple active sessions)
- Each session gets unique refresh token

### 3. Concurrent Token Refresh

- If rotation enabled, first request revokes token
- Second request fails (token revoked)
- Acceptable behavior

### 4. Password Change + Login Race

- Login may succeed with old password if commits before change
- Acceptable (eventual consistency)
- Next login requires new password

---

## 11. Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_ACCESS_TOKEN_TTL_MINUTES=15
JWT_REFRESH_TOKEN_TTL_DAYS=30
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=/path/to/private.pem
JWT_PUBLIC_KEY_PATH=/path/to/public.pem

# Password Configuration
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_COMPLEXITY=true
BCRYPT_COST_FACTOR=12

# Token Rotation
REFRESH_TOKEN_ROTATION_ENABLED=true
REFRESH_TOKEN_REUSE_DETECTION=true

# Organization Checks
CHECK_ORG_STATUS_ON_LOGIN=true
CHECK_ORG_STATUS_ON_TOKEN_VALIDATION=true
```

---

## 12. Future Enhancements

1. **Token Versioning:**
   - Increment `user.token_version` to force logout
   - Check version on every request (performance tradeoff)

2. **Device Fingerprinting:**
   - Store device fingerprint with refresh token
   - Detect token theft across devices

3. **IP Address Whitelisting:**
   - Admin can specify allowed IP ranges
   - Reject logins from other IPs

4. **MFA (Multi-Factor Authentication):**
   - TOTP-based 2FA
   - SMS-based OTP
   - Required for admins

5. **Password History:**
   - Prevent password reuse (last 5 passwords)
   - Store hashed old passwords

6. **Session Limits:**
   - Limit active sessions per user
   - Revoke oldest session when limit reached

---

**End of Auth Domain Layer Requirements**
