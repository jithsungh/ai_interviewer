# Shared Auth Context - Identity & Tenant Context Propagation

## 1. Purpose

The **auth_context** subdirectory provides:

- Identity context abstraction (user, tenant, role)
- Request-scoped injection (REST, WebSocket, WebRTC)
- Tenant resolution and enforcement
- Context propagation to async tasks
- Connection-scoped identity binding

**Critical responsibility:** Consistent identity WITHOUT implementing authentication or authorization logic.

---

## 2. Responsibilities

### 2.1 Identity Context Object

**Must provide:**

- Immutable identity container
- User identification (user_id, user_type)
- Tenant identification (organization_id)
- Role information (admin_role if admin)
- Token metadata (token_version for revocation)

**Must NOT:**

- Validate JWT tokens (belongs in auth module)
- Check permissions (belongs in auth module)
- Implement RBAC (belongs in auth module)

---

### 2.2 Request-Scoped Injection

**For REST:**

- Extract identity from validated JWT (auth middleware)
- Inject into `request.state.identity`
- Access via dependency injection

**For WebSocket:**

- Validate token on connection
- Bind identity to connection instance
- Store in connection registry

**For WebRTC:**

- Validate identity on signaling start
- Bind to signaling channel
- Propagate to audio/proctoring modules

---

### 2.3 Tenant Resolution

**Must enforce:**

- `organization_id` present for admin users
- Candidate access restricted to own `candidate_id`
- No cross-tenant context resolution

**Identity source:**

- ONLY from validated JWT (not query params, not headers)

---

### 2.4 Context Propagation

**To async tasks:**

- Serializable context (user_id, submission_id, organization_id)
- Request ID propagation (for tracing)
- Tenant isolation enforcement

---

## 3. Identity Context Structure

### 3.1 IdentityContext Definition

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class UserType(Enum):
    ADMIN = "admin"
    CANDIDATE = "candidate"

@dataclass(frozen=True)  # Immutable
class IdentityContext:
    """
    Immutable identity context for a request or connection.

    Populated by auth middleware after JWT validation.
    """
    # User identification
    user_id: int
    user_type: UserType

    # Tenant identification
    organization_id: Optional[int]  # Required for admin, null for candidate

    # Role-specific IDs
    candidate_id: Optional[int]  # If user_type=candidate
    admin_id: Optional[int]      # If user_type=admin
    admin_role: Optional[str]    # 'super_admin', 'org_admin', 'recruiter', 'reviewer'

    # Token metadata
    token_version: int           # For revocation (increment on password change)
    issued_at: int               # Unix timestamp
    expires_at: int              # Unix timestamp

    def is_admin(self) -> bool:
        return self.user_type == UserType.ADMIN

    def is_candidate(self) -> bool:
        return self.user_type == UserType.CANDIDATE

    def is_expired(self) -> bool:
        import time
        return time.time() > self.expires_at

    def belongs_to_organization(self, org_id: int) -> bool:
        """Check if identity belongs to organization."""
        if self.is_candidate():
            return False  # Candidates don't belong to org
        return self.organization_id == org_id
```

---

### 3.2 Identity Builder

**Purpose:** Construct IdentityContext from validated JWT claims

```python
class IdentityBuilder:
    """
    Build IdentityContext from JWT claims.

    NOTE: JWT validation is done by auth module.
    This only transforms validated claims into IdentityContext.
    """

    @staticmethod
    def from_jwt_claims(claims: dict) -> IdentityContext:
        """
        Build IdentityContext from JWT claims.

        Expected claims:
        - sub: user_id
        - user_type: 'admin' or 'candidate'
        - organization_id: (if admin)
        - candidate_id: (if candidate)
        - admin_id: (if admin)
        - admin_role: (if admin)
        - token_version: integer
        - iat: issued at (unix timestamp)
        - exp: expires at (unix timestamp)
        """
        user_type = UserType(claims["user_type"])

        return IdentityContext(
            user_id=claims["sub"],
            user_type=user_type,
            organization_id=claims.get("organization_id"),
            candidate_id=claims.get("candidate_id"),
            admin_id=claims.get("admin_id"),
            admin_role=claims.get("admin_role"),
            token_version=claims["token_version"],
            issued_at=claims["iat"],
            expires_at=claims["exp"]
        )
```

---

## 4. Request-Scoped Injection

### 4.1 REST Middleware

**Purpose:** Inject identity into FastAPI request state

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class IdentityInjectionMiddleware(BaseHTTPMiddleware):
    """
    Inject IdentityContext into request state.

    Assumes auth middleware has already validated JWT and stored claims.
    """

    async def dispatch(self, request: Request, call_next):
        # Extract validated JWT claims (set by auth middleware)
        claims = getattr(request.state, "jwt_claims", None)

        if claims:
            # Build identity context
            identity = IdentityBuilder.from_jwt_claims(claims)

            # Inject into request state
            request.state.identity = identity

            # Log identity injection
            logger.debug(
                "Identity injected",
                extra={
                    "user_id": identity.user_id,
                    "user_type": identity.user_type.value,
                    "organization_id": identity.organization_id
                }
            )

        response = await call_next(request)
        return response
```

---

### 4.2 FastAPI Dependency

**Purpose:** Inject identity via dependency injection

```python
from fastapi import Depends, Request, HTTPException

def get_identity(request: Request) -> IdentityContext:
    """
    Dependency to extract identity from request state.

    Raises 401 if identity not present (unauthenticated request).
    """
    identity = getattr(request.state, "identity", None)

    if not identity:
        raise AuthenticationError("Authentication required")

    return identity


def require_admin(identity: IdentityContext = Depends(get_identity)) -> IdentityContext:
    """
    Dependency to require admin user.

    Raises 403 if not admin.
    """
    if not identity.is_admin():
        raise AuthorizationError("Admin access required")

    return identity


def require_candidate(identity: IdentityContext = Depends(get_identity)) -> IdentityContext:
    """
    Dependency to require candidate user.

    Raises 403 if not candidate.
    """
    if not identity.is_candidate():
        raise AuthorizationError("Candidate access required")

    return identity
```

**Usage in endpoint:**

```python
@app.get("/api/v1/admin/submissions")
async def list_submissions(
    identity: IdentityContext = Depends(require_admin)
):
    # Identity is guaranteed to be admin
    submissions = submission_service.list_by_organization(
        organization_id=identity.organization_id
    )
    return submissions
```

---

## 5. WebSocket Identity Binding

### 5.1 WebSocket Authentication

**Purpose:** Validate token and bind identity on connection

```python
from fastapi import WebSocket, WebSocketDisconnect

async def authenticate_websocket(
    websocket: WebSocket,
    token: str
) -> IdentityContext:
    """
    Authenticate WebSocket connection and return identity.

    Args:
        websocket: WebSocket connection instance
        token: Access token (from query param or header)

    Returns:
        IdentityContext if authentication succeeds

    Raises:
        AuthenticationError if token invalid
    """
    # Validate token (auth module)
    claims = await auth_service.validate_access_token(token)

    if not claims:
        raise AuthenticationError("Invalid token")

    # Build identity
    identity = IdentityBuilder.from_jwt_claims(claims)

    # Check expiry
    if identity.is_expired():
        raise AuthenticationError("Token expired")

    return identity


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint with authentication.
    """
    await websocket.accept()

    try:
        # Extract token from query param
        token = websocket.query_params.get("token")

        if not token:
            await websocket.close(code=1008, reason="Missing token")
            return

        # Authenticate
        identity = await authenticate_websocket(websocket, token)

        # Bind identity to connection
        websocket.identity = identity

        # Register connection
        connection_id = generate_connection_id()
        connection_registry.register(
            connection_id=connection_id,
            websocket=websocket,
            identity=identity
        )

        logger.info(
            "WebSocket authenticated",
            extra={
                "connection_id": connection_id,
                "user_id": identity.user_id,
                "user_type": identity.user_type.value
            }
        )

        # Handle messages...

    except AuthenticationError as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Authentication failed")

    except WebSocketDisconnect:
        # Cleanup on disconnect
        if hasattr(websocket, 'identity'):
            connection_registry.unregister(connection_id)
```

---

### 5.2 Connection Registry

**Purpose:** Track active WebSocket connections with identity

```python
from typing import Dict, Optional
from threading import Lock

class ConnectionRegistry:
    """
    In-memory registry of active WebSocket connections.

    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._connections: Dict[str, dict] = {}
        self._lock = Lock()

    def register(
        self,
        connection_id: str,
        websocket: WebSocket,
        identity: IdentityContext
    ):
        """
        Register active connection.

        Raises ConflictError if duplicate submission_id active.
        """
        with self._lock:
            # Check for duplicate submission (if submission_id available)
            submission_id = getattr(websocket, 'submission_id', None)

            if submission_id:
                existing = self._find_by_submission(submission_id)
                if existing:
                    raise ConflictError(
                        f"Active connection already exists for submission {submission_id}"
                    )

            # Register
            self._connections[connection_id] = {
                "connection_id": connection_id,
                "websocket": websocket,
                "identity": identity,
                "submission_id": submission_id,
                "connected_at": time.time()
            }

            logger.info(
                "Connection registered",
                extra={
                    "connection_id": connection_id,
                    "user_id": identity.user_id,
                    "submission_id": submission_id
                }
            )

    def unregister(self, connection_id: str):
        """
        Unregister connection on disconnect.
        """
        with self._lock:
            connection = self._connections.pop(connection_id, None)

            if connection:
                logger.info(
                    "Connection unregistered",
                    extra={
                        "connection_id": connection_id,
                        "submission_id": connection.get("submission_id")
                    }
                )

    def get_connection(self, submission_id: int) -> Optional[WebSocket]:
        """
        Get active WebSocket for submission.
        """
        with self._lock:
            connection = self._find_by_submission(submission_id)
            return connection["websocket"] if connection else None

    def is_active(self, submission_id: int) -> bool:
        """
        Check if submission has active connection.
        """
        return self.get_connection(submission_id) is not None

    def _find_by_submission(self, submission_id: int) -> Optional[dict]:
        """
        Find connection by submission_id.
        """
        for conn in self._connections.values():
            if conn.get("submission_id") == submission_id:
                return conn
        return None
```

---

## 6. Tenant Isolation Enforcement

### 6.1 Organization Scope

**Enforce organization_id for admin operations:**

```python
def enforce_organization_scope(
    identity: IdentityContext,
    resource_organization_id: int
):
    """
    Enforce that admin can only access resources in their organization.

    Raises AuthorizationError if organization mismatch.
    """
    if not identity.is_admin():
        raise AuthorizationError("Admin access required")

    if identity.organization_id != resource_organization_id:
        raise AuthorizationError(
            f"Cannot access resources from organization {resource_organization_id}"
        )
```

**Usage:**

```python
@app.get("/api/v1/admin/submissions/{submission_id}")
async def get_submission(
    submission_id: int,
    identity: IdentityContext = Depends(require_admin)
):
    submission = submission_service.get_by_id(submission_id)

    if not submission:
        raise NotFoundError("submission", submission_id)

    # Enforce tenant isolation
    enforce_organization_scope(identity, submission.organization_id)

    return submission
```

---

### 6.2 Candidate Scope

**Enforce candidate can only access own submissions:**

```python
def enforce_candidate_scope(
    identity: IdentityContext,
    candidate_id: int
):
    """
    Enforce that candidate can only access their own resources.

    Raises AuthorizationError if candidate_id mismatch.
    """
    if not identity.is_candidate():
        raise AuthorizationError("Candidate access required")

    if identity.candidate_id != candidate_id:
        raise AuthorizationError(
            f"Cannot access resources for candidate {candidate_id}"
        )
```

**Usage:**

```python
@app.get("/api/v1/candidate/submissions/{submission_id}")
async def get_submission(
    submission_id: int,
    identity: IdentityContext = Depends(require_candidate)
):
    submission = submission_service.get_by_id(submission_id)

    if not submission:
        raise NotFoundError("submission", submission_id)

    # Enforce candidate scope
    enforce_candidate_scope(identity, submission.candidate_id)

    return submission
```

---

## 7. Context Propagation to Async Tasks

### 7.1 Serializable Context

**Purpose:** Propagate identity to background tasks

```python
@dataclass
class TaskContext:
    """
    Serializable context for async tasks.

    Subset of IdentityContext (only essential fields).
    """
    request_id: str
    user_id: int
    user_type: str
    organization_id: Optional[int]
    candidate_id: Optional[int]
    submission_id: Optional[int]

    @staticmethod
    def from_identity(
        identity: IdentityContext,
        request_id: str,
        submission_id: Optional[int] = None
    ) -> "TaskContext":
        """
        Build TaskContext from IdentityContext.
        """
        return TaskContext(
            request_id=request_id,
            user_id=identity.user_id,
            user_type=identity.user_type.value,
            organization_id=identity.organization_id,
            candidate_id=identity.candidate_id,
            submission_id=submission_id
        )

    def to_dict(self) -> dict:
        """Serialize for task queue."""
        return asdict(self)
```

---

### 7.2 Task Context Propagation

**Celery example:**

```python
@celery.task
def evaluate_exchange_task(
    exchange_id: int,
    context: dict  # TaskContext serialized
):
    """
    Background task to evaluate exchange.

    Context propagated from API request.
    """
    # Deserialize context
    task_context = TaskContext(**context)

    # Log with context
    logger.info(
        "Evaluating exchange",
        extra={
            "request_id": task_context.request_id,
            "user_id": task_context.user_id,
            "submission_id": task_context.submission_id,
            "exchange_id": exchange_id
        }
    )

    # Execute evaluation
    evaluation_service.evaluate_exchange(exchange_id)
```

**Calling from API:**

```python
@app.post("/api/v1/exchanges/{exchange_id}/evaluate")
async def trigger_evaluation(
    exchange_id: int,
    request: Request,
    identity: IdentityContext = Depends(get_identity)
):
    # Build task context
    task_context = TaskContext.from_identity(
        identity=identity,
        request_id=request.state.request_id,
        submission_id=exchange.submission_id
    )

    # Trigger async task with context
    evaluate_exchange_task.delay(
        exchange_id=exchange_id,
        context=task_context.to_dict()
    )

    return {"status": "evaluation_queued"}
```

---

## 8. Security Constraints

### 8.1 Token Handling

**Auth context module MUST NOT:**

- Parse JWT tokens (use auth module)
- Validate JWT signatures (use auth module)
- Store raw tokens (only IdentityContext)

**Auth context module MUST:**

- Accept pre-validated claims (from auth middleware)
- Build IdentityContext from claims
- Enforce immutability (frozen dataclass)

---

### 8.2 Context Isolation

**Must enforce:**

- One IdentityContext per request (no mutation)
- WebSocket identity bound on connection (not per message)
- No cross-request identity sharing (stateless)

**Must prevent:**

- Identity mutation (frozen dataclass)
- Context leakage between requests (request-scoped)
- Token reuse across connections (validate per connection)

---

## 9. Testing Requirements

### 9.1 Identity Builder Tests

**Test: Build identity from JWT claims**

```python
def test_build_identity_from_jwt_claims():
    claims = {
        "sub": 42,
        "user_type": "admin",
        "organization_id": 1,
        "admin_id": 10,
        "admin_role": "org_admin",
        "token_version": 1,
        "iat": 1707916800,
        "exp": 1707920400
    }

    identity = IdentityBuilder.from_jwt_claims(claims)

    assert identity.user_id == 42
    assert identity.user_type == UserType.ADMIN
    assert identity.organization_id == 1
    assert identity.admin_role == "org_admin"
```

---

### 9.2 Scope Enforcement Tests

**Test: Organization scope enforced**

```python
def test_organization_scope_enforced():
    identity = IdentityContext(
        user_id=42,
        user_type=UserType.ADMIN,
        organization_id=1,
        ...
    )

    # Same org: OK
    enforce_organization_scope(identity, resource_organization_id=1)

    # Different org: Error
    with pytest.raises(AuthorizationError):
        enforce_organization_scope(identity, resource_organization_id=2)
```

**Test: Candidate scope enforced**

```python
def test_candidate_scope_enforced():
    identity = IdentityContext(
        user_id=42,
        user_type=UserType.CANDIDATE,
        candidate_id=123,
        ...
    )

    # Same candidate: OK
    enforce_candidate_scope(identity, candidate_id=123)

    # Different candidate: Error
    with pytest.raises(AuthorizationError):
        enforce_candidate_scope(identity, candidate_id=456)
```

---

### 9.3 Connection Registry Tests

**Test: Duplicate connection rejected**

```python
def test_duplicate_connection_rejected():
    registry = ConnectionRegistry()

    identity = create_mock_identity()
    ws1 = create_mock_websocket(submission_id=123)

    registry.register("conn1", ws1, identity)

    # Duplicate submission
    ws2 = create_mock_websocket(submission_id=123)

    with pytest.raises(ConflictError):
        registry.register("conn2", ws2, identity)
```

**Test: Unregister removes connection**

```python
def test_unregister_removes_connection():
    registry = ConnectionRegistry()

    identity = create_mock_identity()
    ws = create_mock_websocket(submission_id=123)

    registry.register("conn1", ws, identity)
    assert registry.is_active(submission_id=123)

    registry.unregister("conn1")
    assert not registry.is_active(submission_id=123)
```

---

## 10. Configuration

### 10.1 AuthContextConfig

```python
@dataclass
class AuthContextConfig:
    # WebSocket
    allow_duplicate_connections: bool = False
    connection_registry_ttl_seconds: int = 3600

    # Token expiry
    enforce_token_expiry: bool = True
    token_expiry_grace_period_seconds: int = 300

    # Logging
    log_identity_injection: bool = True
    log_connection_registry_operations: bool = True
```

---

## 11. Observability

### 11.1 Metrics

**Must expose:**

- `identity_injections_total` (counter with label: protocol) - Identity injections
- `websocket_connections_active` (gauge) - Active WebSocket connections
- `websocket_duplicate_connection_attempts_total` (counter) - Duplicate attempts

---

### 11.2 Logging

**Must log (INFO level):**

- Identity injected (user_id, user_type, organization_id, protocol)
- Connection registered (connection_id, user_id, submission_id)
- Connection unregistered (connection_id, reason)

**Must log (WARN level):**

- Duplicate connection attempt (submission_id, action)
- Token expiry approaching (user_id, expires_at)

**Must log (ERROR level):**

- Identity injection failed (reason)

---

## 12. Critical Risks

1. **JWT validation in auth_context:** Belongs in auth module → architectural violation
2. **Identity mutation:** Context not frozen → race conditions, inconsistent state
3. **Cross-tenant leakage:** organization_id not enforced → data breach
4. **Connection registry memory leak:** Stale entries not cleaned → OOM
5. **Token in query param logged:** Token exposed in access logs → security breach

---

## 13. Acceptance Criteria

**Auth context module is complete when:**

✅ IdentityContext defined (immutable, frozen dataclass)
✅ Identity builder working (from JWT claims)
✅ REST injection working (middleware + dependency)
✅ WebSocket binding working (authenticate on connect)
✅ Connection registry working (register, unregister, duplicate detection)
✅ Organization scope enforcement working
✅ Candidate scope enforcement working
✅ Task context propagation working (serializable)
✅ No JWT validation logic present (uses auth module)
✅ All tests passing (identity, scope, registry)

---

**End of Shared Auth Context Requirements**
