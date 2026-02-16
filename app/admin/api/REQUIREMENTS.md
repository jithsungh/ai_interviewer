# Admin API Layer Requirements

## 1. Purpose

The Admin API layer provides **RESTful HTTP endpoints** for administrative CRUD operations on:

- Interview templates
- Rubrics and evaluation dimensions
- Roles and topic associations
- Interview submission windows
- Window-role-template mappings
- **Questions (behavioral/technical)**
- **Coding problems**
- **All content types with override support**

This layer handles:

- HTTP request/response serialization
- Input validation (format, types)
- **Authentication/authorization enforcement (superadmin, admin, read_only)**
- Error handling and response formatting
- Rate limiting (optional)
- **Override management endpoints**

**Responsibilities:** Request handling, validation, delegation to domain layer, RBAC enforcement
**Not Responsible For:** Business logic, database access, complex validation rules

---

## 2. Owned Tables

**None** - API layer does not directly access database. All persistence operations delegated to `admin/persistence` layer via `admin/domain`.

---

## 3. Input Constraints

### Authentication

- All requests MUST include valid JWT in `Authorization: Bearer <token>` header
- JWT MUST contain claims: `user_id`, `role`, `organization_id`
- Invalid/expired tokens → 401 Unauthorized

### Authorization

- **RBAC enforcement with 3 role types:**
  - **`superadmin`**: Full access to super org (org_id=1) base content, all tenant operations, cross-tenant visibility
  - **`admin`**: Full CRUD on tenant-owned content and override management, tenant-scoped visibility only
  - **`read_only`**: GET operations only, effective merged view (base + overrides), tenant-scoped visibility
- Missing/insufficient permissions → 403 Forbidden
- Cross-tenant access attempts → 403 Forbidden (except superadmin)

### Content Negotiation

- Request `Content-Type: application/json` for POST/PUT/PATCH
- Response `Content-Type: application/json`
- Invalid content-type → 415 Unsupported Media Type

### Request Format

- Valid JSON body for POST/PUT/PATCH
- Malformed JSON → 400 Bad Request
- Query parameters for filtering/pagination (GET)
- Path parameters for resource identification

### Validation Rules

### Template Creation (Native):\*\*

- `name` (required, string, max 255 chars)
- `description` (optional, string, max 1000 chars)
- `scope` (required, enum: `global` | `organization`)
- `template_structure` (required, valid JSON)
- `total_estimated_time_minutes` (optional, integer, > 0)
- Only creates native content for calling organization

- **Template Override Creation:**
  - `base_template_id` (required, must be super org template ID)
  - `override_fields` (required, JSONB with fields to override)
  - Cannot override: `id`, `organization_id`, `scope`
  - Can override: `name`, `description`, `template_structure`, `total_estimated_time_minutes`, etc.

- **Rubric Creation:**
  - `name` (required, string, max 255 chars)
  - `schema` (required, valid JSON with dimensions array)
  - Dimensions must have: `name`, `max_score`, `weight`, `criteria`

- **Window Creation:**
  - `start_time` (required, ISO 8601 timestamp with timezone)
  - `end_time` (required, ISO 8601 timestamp with timezone, > start_time)
  - `scope` (required, enum: `global` | `local` | `only_invited`)

---

## 4. Output Guarantees

### Success Responses

- **201 Created:** Resource created, includes `Location` header with new resource URI
- **200 OK:** Resource retrieved or updated successfully
- **204 No Content:** Resource deleted successfully

### Response Format

```json
{
  "data": {
    "id": 123,
    "name": "Senior Engineer Template",
    "version": 1,
    "created_at": "2026-02-13T10:30:00Z"
  },
  "meta": {
    "request_id": "uuid-v4"
  }
}
```

### List Responses with Pagination

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### Error Responses

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid template structure",
    "details": [
      {
        "field": "template_structure.sections",
        "issue": "required field missing"
      }
    ]
  },
  "meta": {
    "request_id": "uuid-v4",
    "timestamp": "2026-02-13T10:30:00Z"
  }
}
```

### Response Time

- Simple GET: <100ms (p95)
- List with filters: <300ms (p95)
- POST/PUT operations: <500ms (p95)

---

## 5. Invariants

### HTTP Method Semantics

- GET: Idempotent, cacheable, no side effects
- POST: Creates new resource, non-idempotent
- PUT: Full resource replacement, idempotent
- PATCH: Partial update, idempotent
- DELETE: Removes resource, idempotent

### Error Consistency

- All errors return valid JSON (never HTML)
- All errors include `request_id` for tracing
- 4xx errors indicate client fault
- 5xx errors indicate server fault

### URL Structure

```
/api/v1/admin/templates
/api/v1/admin/templates/{id}
/api/v1/admin/templates/{id}/activate
/api/v1/admin/templates/{id}/versions
/api/v1/admin/rubrics
/api/v1/admin/rubrics/{id}/dimensions
/api/v1/admin/windows
/api/v1/admin/windows/{id}/mappings
/api/v1/admin/roles
/api/v1/admin/topics
```

---

## 6. Forbidden Behaviors

### Security

- SHALL NOT log sensitive data (credentials, PII) in request/response logs
- SHALL NOT expose stack traces in production error responses
- SHALL NOT bypass authentication/authorization checks
- SHALL NOT allow SQL injection or XSS in any input field

### API Design

- SHALL NOT return different status codes for same operation success/failure inconsistently
- SHALL NOT break backward compatibility within major version
- SHALL NOT return internal database IDs in error messages
- SHALL NOT accept unbounded input sizes (enforce max request body: 10MB)

### Error Handling

- SHALL NOT return 200 OK with error embedded in response body
- SHALL NOT expose internal implementation details in error messages
- SHALL NOT return different error formats across endpoints

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `admin/domain` - Business logic and orchestration
- `admin/validation` - Structural validation delegates
- `shared/auth_context` - Request-scoped auth resolution
- `shared/errors` - Exception types (ValidationError, NotFoundError, etc.)
- `shared/observability` - Request logging, tracing

### Dependents (Outbound)

- **None** - API is the entry point, called by external HTTP clients

### External Systems

- FastAPI framework for routing and dependency injection
- Pydantic for request/response serialization

---

## 8. Event Contracts Emitted

### Metrics (Prometheus format)

```
http_requests_total{method="POST", endpoint="/admin/templates", status="201"}
http_request_duration_seconds{method="POST", endpoint="/admin/templates"}
```

### Access Logs (JSON format)

```json
{
  "timestamp": "2026-02-13T10:30:00Z",
  "method": "POST",
  "path": "/api/v1/admin/templates",
  "status": 201,
  "duration_ms": 45,
  "user_id": 123,
  "organization_id": 45,
  "request_id": "uuid-v4"
}
```

---

## 9. Acceptance Criteria

### Template Endpoints

- [ ] `POST /api/v1/admin/templates` creates template and returns 201
- [ ] `GET /api/v1/admin/templates` returns list with pagination
- [ ] `GET /api/v1/admin/templates/{id}` returns single template
- [ ] `PUT /api/v1/admin/templates/{id}` updates template (versioning if in use)
- [ ] `PUT /api/v1/admin/templates/{id}/activate` activates template
- [ ] `DELETE /api/v1/admin/templates/{id}` soft-deletes template
- [ ] Invalid JWT returns 401
- [ ] Insufficient permissions return 403
- [ ] Malformed JSON returns 400
- [ ] Non-existent ID returns 404

### Rubric Endpoints

- [ ] `POST /api/v1/admin/rubrics` creates rubric with dimensions
- [ ] `GET /api/v1/admin/rubrics/{id}/dimensions` returns dimensions list
- [ ] Dimension weight validation rejects sum != 1.0

### Window Endpoints

- [ ] `POST /api/v1/admin/windows` creates window with time validation
- [ ] `POST /api/v1/admin/windows/{id}/mappings` adds role-template mappings
- [ ] Overlapping windows rejected (400)

---

## 10. Testing Guide

### Unit Tests (FastAPI route handlers)

```python
# tests/unit/admin/api/test_template_routes.py

def test_create_template_handler():
    """Test route handler with mocked domain service"""
    # Mock domain layer
    # Call route handler
    # Verify 201 response and Location header

def test_get_template_not_found():
    """Test 404 handling"""
    # Mock domain service to raise NotFoundError
    # Verify 404 response with correct error format
```

### Integration Tests (Full HTTP stack)

```python
# tests/integration/admin/api/test_template_api.py

def test_create_template_e2e(client, admin_jwt):
    response = client.post(
        "/api/v1/admin/templates",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json=VALID_TEMPLATE_PAYLOAD
    )
    assert response.status_code == 201
    assert "id" in response.json()["data"]
```

---

## 11. Edge Cases

### Large Payloads

- Template structure with 50KB JSON → Accept if valid
- Request body > 10MB → 413 Payload Too Large

### Concurrent Requests

- Two POSTs with identical data → Both succeed, different IDs created
- Two PUTs to same resource → Last write wins (optimistic locking in domain layer)

### Special Characters

- Template name with emojis → Accept (UTF-8 support)
- Template name with SQL characters (`'; DROP TABLE--`) → Sanitize, no injection

### Timeout Handling

- Domain layer exceeds 30s → 504 Gateway Timeout
- Client disconnects during request → Log and clean up

---

## 12. Concurrency Concerns

### Stateless Request Handling

- API layer is stateless; no shared mutable state
- All request context isolated per request

### Database Connection Pooling

- Use connection pool (max: 50 connections)
- Ensure connections released on error

### Rate Limiting (Optional)

- Per-user rate limit: 100 requests/minute
- Per-organization rate limit: 1000 requests/minute
- Return 429 Too Many Requests with `Retry-After` header

---

## Endpoint Catalog

### Templates

| Method | Path                                     | Description                         |
| ------ | ---------------------------------------- | ----------------------------------- |
| GET    | `/api/v1/admin/templates`                | List templates (paginated)          |
| POST   | `/api/v1/admin/templates`                | Create native template              |
| GET    | `/api/v1/admin/templates/{id}`           | Get template by ID (with overrides) |
| PUT    | `/api/v1/admin/templates/{id}`           | Update template                     |
| DELETE | `/api/v1/admin/templates/{id}`           | Delete template                     |
| PUT    | `/api/v1/admin/templates/{id}/activate`  | Activate template                   |
| GET    | `/api/v1/admin/templates/{id}/versions`  | Get version history                 |
| POST   | `/api/v1/admin/templates/{id}/overrides` | Create override for base template   |
| GET    | `/api/v1/admin/templates/{id}/overrides` | Get current org's override          |
| PUT    | `/api/v1/admin/templates/{id}/overrides` | Update override                     |
| DELETE | `/api/v1/admin/templates/{id}/overrides` | Delete override (revert to base)    |

### Rubrics

| Method | Path                                    | Description                |
| ------ | --------------------------------------- | -------------------------- |
| GET    | `/api/v1/admin/rubrics`                 | List rubrics               |
| POST   | `/api/v1/admin/rubrics`                 | Create native rubric       |
| GET    | `/api/v1/admin/rubrics/{id}`            | Get rubric by ID           |
| PUT    | `/api/v1/admin/rubrics/{id}`            | Update rubric              |
| DELETE | `/api/v1/admin/rubrics/{id}`            | Delete rubric              |
| GET    | `/api/v1/admin/rubrics/{id}/dimensions` | Get dimensions             |
| POST   | `/api/v1/admin/rubrics/{id}/dimensions` | Add dimension              |
| POST   | `/api/v1/admin/rubrics/{id}/overrides`  | Create override for rubric |
| GET    | `/api/v1/admin/rubrics/{id}/overrides`  | Get current org's override |
| PUT    | `/api/v1/admin/rubrics/{id}/overrides`  | Update override            |
| DELETE | `/api/v1/admin/rubrics/{id}/overrides`  | Delete override            |

### Windows

| Method | Path                                  | Description               |
| ------ | ------------------------------------- | ------------------------- |
| GET    | `/api/v1/admin/windows`               | List windows              |
| POST   | `/api/v1/admin/windows`               | Create window             |
| GET    | `/api/v1/admin/windows/{id}`          | Get window by ID          |
| PUT    | `/api/v1/admin/windows/{id}`          | Update window             |
| DELETE | `/api/v1/admin/windows/{id}`          | Delete window             |
| POST   | `/api/v1/admin/windows/{id}/mappings` | Add role-template mapping |

### Roles & Topics

| Method | Path                                 | Description                |
| ------ | ------------------------------------ | -------------------------- |
| GET    | `/api/v1/admin/roles`                | List roles                 |
| POST   | `/api/v1/admin/roles`                | Create role                |
| GET    | `/api/v1/admin/roles/{id}`           | Get role by ID             |
| POST   | `/api/v1/admin/roles/{id}/overrides` | Create override for role   |
| PUT    | `/api/v1/admin/roles/{id}/overrides` | Update role override       |
| DELETE | `/api/v1/admin/roles/{id}/overrides` | Delete role override       |
| GET    | `/api/v1/admin/topics`               | List topics                |
| POST   | `/api/v1/admin/topics`               | Create topic               |
| GET    | `/api/v1/admin/topics/{id}`          | Get topic by ID            |
| POST   | `/api/v1/admin/topics/{id}/overrides`| Create override for topic  |
| PUT    | `/api/v1/admin/topics/{id}/overrides`| Update topic override      |
| DELETE | `/api/v1/admin/topics/{id}/overrides`| Delete topic override      |

### Questions

| Method | Path                                       | Description                    |
| ------ | ------------------------------------------ | ------------------------------ |
| GET    | `/api/v1/admin/questions`                  | List questions (paginated)     |
| POST   | `/api/v1/admin/questions`                  | Create native question         |
| GET    | `/api/v1/admin/questions/{id}`             | Get question by ID             |
| PUT    | `/api/v1/admin/questions/{id}`             | Update question                |
| DELETE | `/api/v1/admin/questions/{id}`             | Delete question                |
| POST   | `/api/v1/admin/questions/{id}/overrides`   | Create override for question   |
| GET    | `/api/v1/admin/questions/{id}/overrides`   | Get current org's override     |
| PUT    | `/api/v1/admin/questions/{id}/overrides`   | Update question override       |
| DELETE | `/api/v1/admin/questions/{id}/overrides`   | Delete override (revert)       |
| PUT    | `/api/v1/admin/questions/{id}/activate`    | Activate question              |
| POST   | `/api/v1/admin/questions/bulk-import`      | Bulk import questions          |

### Coding Problems

| Method | Path                                           | Description                        |
| ------ | ---------------------------------------------- | ---------------------------------- |
| GET    | `/api/v1/admin/coding-problems`                | List coding problems (paginated)   |
| POST   | `/api/v1/admin/coding-problems`                | Create native coding problem       |
| GET    | `/api/v1/admin/coding-problems/{id}`           | Get coding problem by ID           |
| PUT    | `/api/v1/admin/coding-problems/{id}`           | Update coding problem              |
| DELETE | `/api/v1/admin/coding-problems/{id}`           | Delete coding problem              |
| POST   | `/api/v1/admin/coding-problems/{id}/overrides` | Create override for coding problem |
| GET    | `/api/v1/admin/coding-problems/{id}/overrides` | Get current org's override         |
| PUT    | `/api/v1/admin/coding-problems/{id}/overrides` | Update coding problem override     |
| DELETE | `/api/v1/admin/coding-problems/{id}/overrides` | Delete override (revert)           |
| PUT    | `/api/v1/admin/coding-problems/{id}/activate`  | Activate coding problem            |
| GET    | `/api/v1/admin/coding-problems/{id}/test-cases`| Get test cases for problem         |
| POST   | `/api/v1/admin/coding-problems/{id}/test-cases`| Add test case to problem           |

### Reports & Analytics (Read-only for all admins)

| Method | Path                                     | Description                     |
| ------ | ---------------------------------------- | ------------------------------- |
| GET    | `/api/v1/admin/reports/candidate-summary`| Generate candidate summary      |
| GET    | `/api/v1/admin/reports/proctoring-risk`  | Generate proctoring risk report |
| POST   | `/api/v1/admin/reports/{type}/publish`   | Publish report                  |
| GET    | `/api/v1/admin/analytics/dashboard`      | Get dashboard metrics           |

### Live Monitoring (Admin and Superadmin only)

| Method | Path                                       | Description                   |
| ------ | ------------------------------------------ | ----------------------------- |
| GET    | `/api/v1/admin/monitoring/ongoing`         | List ongoing interviews       |
| GET    | `/api/v1/admin/monitoring/sessions/{id}`   | View live session details     |
| POST   | `/api/v1/admin/monitoring/sessions/{id}/pause`| Pause interview            |
| POST   | `/api/v1/admin/monitoring/sessions/{id}/flag` | Flag incident              |

### Review Queue (Admin and Superadmin only)

| Method | Path                                       | Description                   |
| ------ | ------------------------------------------ | ----------------------------- |
| GET    | `/api/v1/admin/review/flagged`             | List flagged submissions      |
| GET    | `/api/v1/admin/review/submissions/{id}`    | Get submission details        |
| POST   | `/api/v1/admin/review/submissions/{id}/override`| Apply score override      |
| POST   | `/api/v1/admin/review/submissions/{id}/finalize`| Finalize review           |

### Governance (Superadmin only)

| Method | Path                                  | Description              |
| ------ | ------------------------------------- | ------------------------ |
| GET    | `/api/v1/admin/audit-logs`            | Query audit logs         |
| GET    | `/api/v1/admin/retention-policies`    | List retention policies  |
| POST   | `/api/v1/admin/deletion-requests`     | Create deletion request  |
| GET    | `/api/v1/admin/consent-records`       | List consent records     |

### System Settings (Superadmin only)

| Method | Path                               | Description             |
| ------ | ---------------------------------- | ----------------------- |
| GET    | `/api/v1/admin/settings/admins`    | List admin users        |
| POST   | `/api/v1/admin/settings/admins`    | Create admin user       |
| PUT    | `/api/v1/admin/settings/admins/{id}/role`| Update admin role |
| GET    | `/api/v1/admin/settings/models`    | List AI models          |
| PUT    | `/api/v1/admin/settings/models/{id}`| Update model config    |
| GET    | `/api/v1/admin/settings/prompts`   | List prompt templates   |
| PUT    | `/api/v1/admin/settings/feature-flags`| Update feature flags |
