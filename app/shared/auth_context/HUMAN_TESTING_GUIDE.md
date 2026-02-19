# Human Testing Guide: Auth Context Module

## Overview

This guide provides step-by-step manual testing procedures for the `shared/auth_context` module. Use this to verify core authentication, authorization, and multi-tenant isolation functionality.

---

## Prerequisites

1. **Running Application**: Ensure the FastAPI application is running with the auth_context middleware configured
2. **Redis Instance**: Ensure Redis is running and accessible (required for WebSocket connection registry)
3. **JWT Secret**: Know the JWT secret key used by your auth module
4. **Test Database**: Have test organizations, admins, and candidates in the database

---

## Test Data Setup

### Create Test Users in Database

```sql
-- Organization 1
INSERT INTO organizations (id, name, created_at) VALUES (1, 'ACME Corp', NOW());

-- Superadmin (user_id=1, org_id=1)
INSERT INTO users (id, created_at, updated_at) VALUES (1, NOW(), NOW());
INSERT INTO admins (user_id, organization_id, admin_role, status, created_at)
VALUES (1, 1, 'superadmin', 'active', NOW());

-- Regular Admin (user_id=2, org_id=1)
INSERT INTO users (id, created_at, updated_at) VALUES (2, NOW(), NOW());
INSERT INTO admins (user_id, organization_id, admin_role, status, created_at)
VALUES (2, 1, 'admin', 'active', NOW());

-- Organization 2
INSERT INTO organizations (id, name, created_at) VALUES (2, 'TechStart Inc', NOW());

-- Admin from org 2 (user_id=3, org_id=2)
INSERT INTO users (id, created_at, updated_at) VALUES (3, NOW(), NOW());
INSERT INTO admins (user_id, organization_id, admin_role, status, created_at)
VALUES (3, 2, 'admin', 'active', NOW());

-- Candidate (user_id=100)
INSERT INTO users (id, created_at, updated_at) VALUES (100, NOW(), NOW());
INSERT INTO candidates (user_id, full_name, status, created_at)
VALUES (100, 'John Doe', 'active', NOW());
```

---

## Generate Test JWT Tokens

### Python Script to Generate Tokens

```python
import jwt
import time

SECRET_KEY = "your-secret-key"  # Use your actual secret
ALGORITHM = "HS256"

def generate_token(user_id: int, user_type: str, organization_id: int = None, admin_role: str = None):
    """Generate JWT token for testing"""
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "user_type": user_type,
        "token_version": 1,
        "iat": now,
        "exp": now + 3600  # 1 hour expiration
    }

    if user_type == "admin":
        payload["organization_id"] = organization_id
        payload["admin_role"] = admin_role

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

# Generate tokens
superadmin_token = generate_token(1, "admin", 1, "superadmin")
admin_org1_token = generate_token(2, "admin", 1, "admin")
admin_org2_token = generate_token(3, "admin", 2, "admin")
candidate_token = generate_token(100, "candidate")

print(f"Superadmin: {superadmin_token}")
print(f"Admin Org 1: {admin_org1_token}")
print(f"Admin Org 2: {admin_org2_token}")
print(f"Candidate: {candidate_token}")
```

---

## Test Scenarios

### 1. Middleware Identity Injection

**Test**: Verify middleware injects identity into request state

```bash
# Valid admin token should succeed
curl -X GET "http://localhost:8000/api/health" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

# Missing token should fail with 401
curl -X GET "http://localhost:8000/api/health"

# Invalid token should fail with 401
curl -X GET "http://localhost:8000/api/health" \
  -H "Authorization: Bearer invalid_token"
```

**Expected Results**:

- ✅ Valid token: 200 OK with response data
- ❌ Missing token: 401 Unauthorized
- ❌ Invalid token: 401 Unauthorized

---

### 2. Admin-Only Endpoint Access

**Test**: Verify `require_admin()` dependency blocks candidates

```bash
# Admin should access admin-only endpoint
curl -X GET "http://localhost:8000/api/admin/dashboard" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

# Candidate should be blocked
curl -X GET "http://localhost:8000/api/admin/dashboard" \
  -H "Authorization: Bearer <CANDIDATE_TOKEN>"
```

**Expected Results**:

- ✅ Admin: 200 OK with dashboard data
- ❌ Candidate: 403 Forbidden

---

### 3. Candidate-Only Endpoint Access

**Test**: Verify `require_candidate()` dependency blocks admins

```bash
# Candidate should access their profile
curl -X GET "http://localhost:8000/api/candidate/profile" \
  -H "Authorization: Bearer <CANDIDATE_TOKEN>"

# Admin should be blocked
curl -X GET "http://localhost:8000/api/candidate/profile" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Expected Results**:

- ✅ Candidate: 200 OK with profile data
- ❌ Admin: 403 Forbidden

---

### 4. Superadmin-Only Access

**Test**: Verify `require_superadmin()` dependency

```bash
# Superadmin should access system settings
curl -X GET "http://localhost:8000/api/system/settings" \
  -H "Authorization: Bearer <SUPERADMIN_TOKEN>"

# Regular admin should be blocked
curl -X GET "http://localhost:8000/api/system/settings" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Expected Results**:

- ✅ Superadmin: 200 OK with settings
- ❌ Regular admin: 403 Forbidden

---

### 5. Multi-Tenant Isolation

**Test**: Verify organization scope enforcement

```bash
# Admin from org 1 accesses their own organization
curl -X GET "http://localhost:8000/api/organizations/1/candidates" \
  -H "Authorization: Bearer <ADMIN_ORG1_TOKEN>"

# Admin from org 1 tries to access org 2 (should fail)
curl -X GET "http://localhost:8000/api/organizations/2/candidates" \
  -H "Authorization: Bearer <ADMIN_ORG1_TOKEN>"

# Superadmin can access any organization
curl -X GET "http://localhost:8000/api/organizations/2/candidates" \
  -H "Authorization: Bearer <SUPERADMIN_TOKEN>"
```

**Expected Results**:

- ✅ Admin accessing own org: 200 OK
- ❌ Admin accessing different org: 403 Forbidden (TenantIsolationViolation)
- ✅ Superadmin accessing any org: 200 OK

---

### 6. Candidate Scope Enforcement

**Test**: Verify candidates can only access their own resources

```bash
# Candidate accesses their own submission (candidate_id=100)
curl -X GET "http://localhost:8000/api/candidates/100/submissions" \
  -H "Authorization: Bearer <CANDIDATE_TOKEN>"

# Candidate tries to access another candidate's submission (should fail)
curl -X GET "http://localhost:8000/api/candidates/99/submissions" \
  -H "Authorization: Bearer <CANDIDATE_TOKEN>"
```

**Expected Results**:

- ✅ Own resources: 200 OK
- ❌ Other candidate's resources: 403 Forbidden

---

### 7. WebSocket Connection Registry

**Test**: Verify Redis-backed connection registry

#### Test 7.1: Register Connection

```python
import asyncio
from app.shared.auth_context.registry import ConnectionRegistry

async def test_register():
    registry = ConnectionRegistry()

    # Register connection
    await registry.register_connection(
        submission_id=1001,
        connection_id="conn-abc-123"
    )

    print("Connection registered successfully")

asyncio.run(test_register())
```

**Verify in Redis**:

```bash
redis-cli
> GET active_websocket:1001
# Should return: "conn-abc-123"
> TTL active_websocket:1001
# Should return: ~60 (seconds)
```

#### Test 7.2: Prevent Duplicate Connections

```python
async def test_duplicate():
    registry = ConnectionRegistry()

    # First connection
    await registry.register_connection(
        submission_id=1001,
        connection_id="conn-first"
    )

    # Second connection should fail
    try:
        await registry.register_connection(
            submission_id=1001,
            connection_id="conn-second"
        )
        print("ERROR: Should have raised ConflictError")
    except Exception as e:
        print(f"✅ Correctly blocked duplicate: {e}")

asyncio.run(test_duplicate())
```

#### Test 7.3: Refresh TTL (Heartbeat)

```python
async def test_heartbeat():
    registry = ConnectionRegistry()

    # Register connection
    await registry.register_connection(
        submission_id=1001,
        connection_id="conn-abc-123"
    )

    # Wait 30 seconds
    await asyncio.sleep(30)

    # Refresh TTL
    refreshed = await registry.refresh_ttl(submission_id=1001)
    print(f"✅ TTL refreshed: {refreshed}")

asyncio.run(test_heartbeat())
```

**Verify in Redis**:

```bash
> TTL active_websocket:1001
# Should return: ~60 (reset to full TTL)
```

---

### 8. WebSocket Authentication

**Test**: Authenticate WebSocket before accepting connection

#### Test via Python

```python
from app.shared.auth_context.websocket import authenticate_websocket

async def mock_validator(token: str):
    """Replace with actual JWT validator"""
    # Validate token and return claims
    import jwt
    claims = jwt.decode(token, "secret", algorithms=["HS256"])
    return claims

async def test_ws_auth():
    # Valid token
    identity = await authenticate_websocket("<CANDIDATE_TOKEN>", mock_validator)
    print(f"✅ Authenticated: user_id={identity.user_id}, type={identity.user_type}")

    # Invalid token
    try:
        await authenticate_websocket("invalid_token", mock_validator)
        print("ERROR: Should have raised AuthenticationError")
    except Exception as e:
        print(f"✅ Correctly rejected: {e}")

asyncio.run(test_ws_auth())
```

#### Test via WebSocket Client

```python
import websockets
import asyncio

async def test_websocket():
    uri = "ws://localhost:8000/ws/interview/1001"
    headers = {"Authorization": "Bearer <CANDIDATE_TOKEN>"}

    async with websockets.connect(uri, extra_headers=headers) as websocket:
        print("✅ WebSocket connected")
        # Send/receive messages
        await websocket.send("Hello")
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())
```

---

### 9. Role Hierarchy Enforcement

**Test**: Verify role hierarchy (superadmin > admin > read_only)

```bash
# Read-only admin tries to create resource (requires 'admin' role)
curl -X POST "http://localhost:8000/api/organizations/1/templates" \
  -H "Authorization: Bearer <READONLY_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Template"}'

# Regular admin can create resource
curl -X POST "http://localhost:8000/api/organizations/1/templates" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Template"}'

# Superadmin can create resource in any organization
curl -X POST "http://localhost:8000/api/organizations/2/templates" \
  -H "Authorization: Bearer <SUPERADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Template"}'
```

**Expected Results**:

- ❌ Read-only admin: 403 Forbidden (insufficient privileges)
- ✅ Admin: 201 Created
- ✅ Superadmin: 201 Created (any org)

---

## Verification Checklist

After running all tests, verify:

- [ ] Middleware correctly injects identity from valid JWT
- [ ] Missing/invalid tokens are rejected with 401
- [ ] `require_admin()` blocks candidates
- [ ] `require_candidate()` blocks admins
- [ ] `require_superadmin()` blocks regular admins
- [ ] Admins cannot access other organizations' resources
- [ ] Superadmins can access all organizations
- [ ] Candidates cannot access other candidates' resources
- [ ] WebSocket connections are registered in Redis with TTL
- [ ] Duplicate WebSocket connections are prevented
- [ ] TTL refresh (heartbeat) extends connection lifetime
- [ ] WebSocket authentication validates JWT before connection
- [ ] Role hierarchy is enforced (read_only < admin < superadmin)

---

## Troubleshooting

### 401 Unauthorized (Unexpected)

- **Check**: JWT secret matches between token generation and validation
- **Check**: Token hasn't expired (`exp` claim)
- **Check**: Token signature is valid

### 403 Forbidden (Unexpected)

- **Check**: User has correct `user_type` in JWT claims
- **Check**: Admin has correct `admin_role` in JWT claims
- **Check**: `organization_id` matches resource being accessed

### WebSocket Connection Fails

- **Check**: Redis is running and accessible
- **Check**: Token is passed in correct header/query param
- **Check**: No existing connection for same `submission_id`

### TTL Not Refreshing

- **Check**: Redis EXPIRE command succeeds
- **Check**: Key exists in Redis before refresh
- **Check**: Heartbeat interval is less than TTL (30s < 60s)

---

## Performance Testing

### Load Test: Concurrent WebSocket Connections

```python
import asyncio
import websockets

async def connect(submission_id: int, token: str):
    uri = f"ws://localhost:8000/ws/interview/{submission_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(uri, extra_headers=headers) as ws:
        await ws.send("ping")
        await ws.recv()

async def load_test():
    # 100 concurrent connections
    tasks = [
        connect(submission_id=i, token=f"<TOKEN_{i}>")
        for i in range(100)
    ]
    await asyncio.gather(*tasks)

asyncio.run(load_test())
```

**Expected**: All connections succeed without Redis conflicts.

---

## Security Testing

### Test 1: Token Tampering

```python
# Modify token payload without re-signing
tampered_token = "<VALID_TOKEN>"[:-10] + "tampered"

# Should fail validation
curl -X GET "http://localhost:8000/api/health" \
  -H "Authorization: Bearer $tampered_token"
# Expected: 401 Unauthorized
```

### Test 2: Expired Token

```python
# Generate token with past expiration
expired_token = generate_token(100, "candidate", exp=int(time.time()) - 3600)

# Should fail validation
curl -X GET "http://localhost:8000/api/health" \
  -H "Authorization: Bearer $expired_token"
# Expected: 401 Unauthorized
```

### Test 3: SQL Injection in Organization ID

```bash
# Try SQL injection in organization_id parameter
curl -X GET "http://localhost:8000/api/organizations/1%27%20OR%20%271%27%3D%271/candidates" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
# Expected: 400 Bad Request (validation error, not SQL injection)
```

---

## Next Steps

After completing manual testing:

1. Review test results and verify all checks pass
2. Document any failures or unexpected behavior
3. Run automated test suite: `pytest tests/unit/shared/auth_context tests/integration/shared/auth_context`
4. Integrate with actual auth module when JWT validation is implemented
5. Update this guide with additional edge cases discovered during testing
