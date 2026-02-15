# Auth Persistence Layer - Data Access

## 1. Purpose

**Why this submodule exists:**

The Auth Persistence layer provides **repository pattern implementations** for identity data access. It:

- Abstracts database operations for `users`, `admins`, `candidates`,`refresh_tokens`, `auth_audit_log`
- Enforces data integrity constraints (UNIQUE, foreign keys)
- Provides query methods for authentication workflows
- Handles database transactions
- Isolates domain layer from SQLAlchemy ORM details

**Critical responsibility:** This is the **only layer** that directly accesses identity tables. Domain logic never writes raw SQL or imports ORM models directly.

---

## 2. Owned Tables / Entities

See main auth REQUIREMENTS.md for full table schemas. This layer owns:

- `users`
- `admins`
- `candidates`
- `refresh_tokens`
- `auth_audit_log`

---

## 3. Input Contracts

### Repository Methods

#### UserRepository

```python
class UserRepository:
    def create(self, email: str, password_hash: str, user_type: str, user_status: str = 'active') -> User:
        """Create new user"""

    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email (case-insensitive)"""

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""

    def email_exists(self, email: str) -> bool:
        """Check if email already registered"""

    def update_last_login(self, user_id: int):
        """Update last_login_at timestamp"""

    def update_password(self, user_id: int, new_password_hash: str):
        """Update password hash"""

    def update_status(self, user_id: int, new_status: str):
        """Update user_status"""

    def increment_token_version(self, user_id: int):
        """Increment token_version (for forced logout)"""
```

#### AdminRepository

```python
class AdminRepository:
    def create(self, user_id: int, organization_id: int, admin_role: str, admin_status: str = 'active') -> Admin:
        """Create admin record"""

    def find_by_user_id(self, user_id: int) -> Optional[Admin]:
        """Get admin by user_id"""

    def get_by_id(self, admin_id: int) -> Optional[Admin]:
        """Get admin by admin_id"""

    def update_role(self, admin_id: int, new_role: str):
        """Update admin_role"""

    def update_status(self, admin_id: int, new_status: str):
        """Update admin_status"""

    def list_by_organization(self, organization_id: int) -> List[Admin]:
        """List all admins for an organization"""
```

#### CandidateRepository

```python
class CandidateRepository:
    def create(self, user_id: int, full_name: Optional[str] = None, phone: Optional[str] = None) -> Candidate:
        """Create candidate record"""

    def find_by_user_id(self, user_id: int) -> Optional[Candidate]:
        """Get candidate by user_id"""

    def get_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """Get candidate by candidate_id"""

    def update_profile(self, candidate_id: int, full_name: Optional[str] = None, phone: Optional[str] = None, resume_url: Optional[str] = None):
        """Update candidate profile"""

    def update_status(self, candidate_id: int, new_status: str):
        """Update candidate_status"""
```

#### RefreshTokenRepository

```python
class RefreshTokenRepository:
    def create(self, user_id: int, token_hash: str, device_info: Optional[str], ip_address: Optional[str], expires_at: datetime) -> RefreshToken:
        """Store refresh token"""

    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Find refresh token by hash"""

    def revoke(self, token_id: int, reason: str):
        """Revoke specific refresh token"""

    def revoke_all_for_user(self, user_id: int, reason: str):
        """Revoke all refresh tokens for user (e.g., password change, suspicious activity)"""

    def cleanup_expired(self):
        """Delete expired tokens (maintenance task)"""

    def list_active_for_user(self, user_id: int) -> List[RefreshToken]:
        """List active (non-revoked, non-expired) tokens for user"""
```

#### AuthAuditLogRepository

```python
class AuthAuditLogRepository:
    def log_event(self, event: AuthEvent):
        """Log auth event to audit log"""

    def get_recent_events(self, user_id: int, limit: int = 50) -> List[AuthAuditLog]:
        """Get recent auth events for user"""

    def get_failed_login_attempts(self, email: str, since: datetime) -> int:
        """Count failed login attempts for email since timestamp"""

    def get_suspicious_events(self, since: datetime) -> List[AuthAuditLog]:
        """Get suspicious activity events"""
```

---

## 4. Output Contracts

### ORM Models

#### User Model

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    user_type = Column(String(20), nullable=False)
    user_status = Column(String(20), nullable=False, default='active')
    token_version = Column(Integer, default=0)  # For forced logout
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)

    # Relationships
    admin = relationship("Admin", back_populates="user", uselist=False)
    candidate = relationship("Candidate", back_populates="user", uselist=False)
    refresh_tokens = relationship("RefreshToken", back_populates="user")

    __table_args__ = (
        CheckConstraint("user_type IN ('admin', 'candidate')", name="user_type_check"),
        CheckConstraint("user_status IN ('active', 'inactive', 'banned')", name="user_status_check"),
    )
```

#### Admin Model

```python
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    admin_role = Column(String(50), nullable=False)
    admin_status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="admin")
    organization = relationship("Organization")

    __table_args__ = (
        CheckConstraint("admin_role IN ('superadmin', 'admin', 'read_only')", name="admin_role_check"),
        CheckConstraint("admin_status IN ('active', 'inactive')", name="admin_status_check"),
    )
```

#### Candidate Model

```python
class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    resume_url = Column(Text)
    candidate_status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="candidate")

    __table_args__ = (
        CheckConstraint("candidate_status IN ('active', 'inactive')", name="candidate_status_check"),
    )
```

#### RefreshToken Model

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, unique=True, nullable=False, index=True)
    device_info = Column(Text)
    ip_address = Column(String(45))
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    revoked_reason = Column(String(100))

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
```

#### AuthAuditLog Model

```python
class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    event_type = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

---

## 5. Acceptance Criteria

### Functional Requirements

#### 1. User Repository

**Create User:**

- Insert into `users` table
- Enforce email UNIQUE constraint
- Set default `user_status='active'`
- Set `token_version=0`
- Return User model

**Find by Email:**

- Query case-insensitive (use `LOWER(email)` or `ilike`)
- Return None if not found

**Email Exists:**

- Efficient check (no full model load)
- Return boolean

**Update Last Login:**

- Update `last_login_at` to current timestamp
- Update `updated_at` automatically (via `onupdate`)

**Increment Token Version:**

- Atomic increment: `UPDATE users SET token_version = token_version + 1 WHERE id = ?`
- Used to invalidate all access tokens on password change or forced logout

#### 2. Admin Repository

**Create Admin:**

- Insert into `admins` table
- Link to existing `user_id` (FK constraint enforced)
- Link to `organization_id` (FK constraint enforced)
- Cannot self-assign `superadmin` (enforced at domain layer, not DB)

**Find by User ID:**

- Join `user` and `admin` tables
- Return Admin with related User and Organization

**Update Role:**

- Update `admin_role`
- Log role change event (domain layer responsibility)

**List by Organization:**

- Filter by `organization_id`
- Return all admins for that org

#### 3. Candidate Repository

**Create Candidate:**

- Insert into `candidates` table
- Link to `user_id`
- Optional profile fields

**Update Profile:**

- Update `full_name`, `phone`, `resume_url`
- Partial updates allowed (only update provided fields)

#### 4. Refresh Token Repository

**Create Refresh Token:**

- Insert hashed token
- Store device info, IP address
- Set expiration timestamp

**Find by Hash:**

- Query by `token_hash`
- Return None if not found or expired

**Revoke:**

- Set `revoked_at = NOW()`
- Set `revoked_reason`

**Revoke All for User:**

- Update all non-revoked tokens for `user_id`
- Set `revoked_reason` (e.g., 'password_change', 'suspicious_activity')

**Cleanup Expired:**

- Delete tokens where `expires_at < NOW()` AND at least 7 days old
- Run as scheduled job (e.g., daily)

#### 5. Auth Audit Log Repository

**Log Event:**

- Insert event into `auth_audit_log`
- Never update or delete (immutable audit log)

**Get Recent Events:**

- Query last N events for `user_id`
- Order by `created_at DESC`

**Get Failed Login Attempts:**

- Count `login_failure` events for email since timestamp
- Used for rate limiting

**Get Suspicious Events:**

- Filter by `event_type='suspicious_activity'`
- Used for security monitoring

### Non-Functional Requirements

1. **Query Performance:**
   - User lookup by email: <10ms p95 (indexed)
   - Refresh token lookup by hash: <10ms p95 (indexed)
   - Audit log queries: <50ms p95

2. **Transaction Safety:**
   - User + Admin creation: atomic (single transaction)
   - User + Candidate creation: atomic
   - Refresh token creation + revocation: atomic

3. **Connection Pooling:**
   - Use SQLAlchemy connection pool
   - Prevent connection leaks

---

## 6. Invariants & Constraints

### Must Hold

1. **Email Uniqueness:** Database UNIQUE constraint enforced
2. **User-Admin 1:1:** One user can have at most one admin record
3. **User-Candidate 1:1:** One user can have at most one candidate record
4. **User Type Consistency:** If `user_type='admin'`, `admins` record must exist
5. **Token Hash Uniqueness:** Each refresh token hash is unique
6. **Audit Log Immutability:** No updates or deletes allowed on `auth_audit_log`

### Forbidden

- MUST NOT expose password hash in query results (exclude from SELECT)
- MUST NOT update `auth_audit_log` records
- MUST NOT delete `auth_audit_log` records (except retention policy cleanup)
- MUST NOT allow NULL in required fields (`email`, `password_hash`, `user_type`)
- MUST NOT bypass constraints via raw SQL

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Domain Layer (`app.auth.domain`):**
   - Calls repository methods
   - Passes domain objects
   - Receives ORM models (converted to domain models)

### Downstream (Dependencies)

1. **Database (PostgreSQL):**
   - SQLAlchemy ORM
   - Connection pool
   - Transaction management

2. **SQLAlchemy Core:**
   - Query builder
   - Column definitions
   - Constraints

---

## 8. Event Contracts Emitted

Persistence layer does **not** emit events. Events are emitted by domain layer after successful persistence.

---

## 9. Edge Cases to Handle

### 1. Duplicate Email Registration

- **Scenario:** Two users register with same email simultaneously
- **Handling:** Database UNIQUE constraint raises `IntegrityError`
- **Result:** Repository catches error, domain layer raises `EmailAlreadyExistsError`

### 2. User Deleted Mid-Transaction

- **Scenario:** User deleted while creating admin record
- **Handling:** FK constraint `ON DELETE CASCADE` ensures admin deleted too
- **Result:** Cascading delete maintains referential integrity

### 3. Organization Deleted

- **Scenario:** Organization deleted, admins linked to it
- **Handling:** FK constraint `ON DELETE CASCADE` deletes admin records
- **Result:** Users remain (can be reassigned to new org)

### 4. Expired Refresh Token Lookup

- **Scenario:** Client sends expired refresh token
- **Handling:** `find_by_hash()` returns token, domain layer checks expiration
- **Result:** Domain layer rejects with `RefreshTokenExpiredError`

### 5. Revoked Token Reused

- **Scenario:** Client sends already-revoked token
- **Handling:** `find_by_hash()` returns token with `revoked_at != None`
- **Result:** Domain layer detects reuse, revokes all user tokens

### 6. Concurrent Token Revocation

- **Scenario:** Two threads try to revoke same token
- **Handling:** Both UPDATE statements succeed (idempotent)
- **Result:** Token revoked, `revoked_reason` may differ (last write wins)

---

## 10. Concurrency Concerns

### 1. Concurrent User Creation

- Database UNIQUE constraint prevents duplicates
- One transaction succeeds, others fail with `IntegrityError`

### 2. Concurrent Token Version Increment

- Use atomic UPDATE: `SET token_version = token_version + 1`
- No race condition (database handles atomicity)

### 3. Concurrent Refresh Token Revocation

- Multiple threads revoking same token: idempotent
- Multiple threads revoking all user tokens: all succeed

### 4. Transaction Isolation

- Use default isolation level (READ COMMITTED)
- For critical operations (e.g., payment-related in future), consider SERIALIZABLE

---

## 11. Configuration

### Environment Variables

```bash
# Database Connection
DATABASE_URL=postgresql://user:pass@localhost/ai_interviewer

# Connection Pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Query Logging (dev only)
DB_ECHO=false
```

---

## 12. Future Enhancements

1. **Read Replicas:**
   - Route read queries to replicas
   - Write queries to primary

2. **Soft Deletes:**
   - Add `deleted_at` column
   - Filter out soft-deleted records

3. **Audit Log Archival:**
   - Move old audit logs to cold storage (S3, Glacier)
   - Keep 90 days in hot DB, archive older

4. **Query Optimization:**
   - Add composite indexes for common queries
   - Monitor slow query log

5. **Sharding:**
   - Shard users by `user_id` range (future scale)
   - Route queries to appropriate shard

---

**End of Auth Persistence Layer Requirements**
