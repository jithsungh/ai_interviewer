# Admin Domain Layer Requirements

## 1. Purpose

The domain layer contains **core business logic** for admin operations:

- Content versioning and immutability enforcement (templates, questions, coding problems, etc.)
- Rubric validation (dimension weights, schema checks)
- Window scheduling logic (overlap detection, time validation)
- Scope resolution (global vs organization)
- Activation/deactivation workflows
- **Override management across all content types**
- **RBAC enforcement (superadmin, admin, read_only)**

**Responsibilities:** Business rules, orchestration between persistence and validation layers, override resolution logic
**Not Responsible For:** HTTP concerns, database queries, external I/O

---

## 2. Owned Tables

**None** - Domain layer does not directly access database. Delegates to `admin/persistence` repositories.

---

## 3. Input Constraints

### From API Layer

- Pre-validated request DTOs (types, formats correct)
- Authenticated context with `user_id`, `role` (superadmin/admin/read_only), `organization_id`

### Business Rules to Enforce

- **Content editing (all types):** If content is referenced by any submission → create new version
- **Override management:**
  - Tenant can only create overrides for super org (org_id=1) base content
  - Override fields must be valid JSON subset of base content structure
  - Cannot override immutable fields (id, organization_id, scope)
- **RBAC validation:**
  - `superadmin`: Can modify base content (org_id=1) and view all tenants
  - `admin`: Can modify native tenant content and manage tenant overrides
  - `read_only`: View-only access to effective merged content
- **Rubric dimension weights:** Must sum to 1.0 (tolerance: ±0.001)
- **Window timing:** `end_time` > `start_time`
- **Scope constraints:** Global content can only reference global dependencies

---

## 4. Output Guarantees

### Return Types

- Success: Domain entity objects (Template, Rubric, Window, Question, CodingProblem, etc.)
- Success with override: Effective merged entity (base + tenant override)
- Failure: Raises typed exceptions (ValidationError, ConflictError, NotFoundError, UnauthorizedError)

### Transactional Guarantees

- All mutations wrapped in database transactions
- On exception: Automatic rollback
- Audit log entries written within same transaction
- Override creation/update/deletion is atomic

### Idempotency

- Repeated identical requests produce same final state
- Duplicate activations are no-ops
- Duplicate override creation with same fields is idempotent

---

## 5. Invariants

### Content Immutability After Use (ERD Invariant #3)

```python
# Generic pattern for all content types
if content.is_in_use():
    new_content = content.create_version()
    return new_content
else:
    content.update(changes)
    return content

# Applies to: templates, questions, coding_problems, rubrics, roles, topics
```

### Override Resolution

```python
def get_effective_content(base_content_id: int, org_id: int, content_type: str):
    """
    Generic override resolution for any content type.
    Returns effective content = base + tenant override (if exists).
    """
    base = repository.get_base_content(base_content_id, content_type)
    override = repository.get_override(org_id, base_content_id, content_type)
    
    if override:
        return merge(base, override.override_fields)
    return base
```

### RBAC Authorization

```python
def authorize_operation(user_role: str, operation: str, resource_org_id: int, user_org_id: int) -> bool:
    """
    Enforce role-based access control:
    - superadmin: All operations on all organizations
    - admin: All operations on own organization only
    - read_only: GET operations on own organization only
    """
    if user_role == "superadmin":
        return True
    
    if user_org_id != resource_org_id:
        return False  # Cross-tenant access forbidden
    
    if user_role == "read_only":
        return operation == "GET"
    
    return user_role == "admin"  # Admin has full CRUD on own org
```

### Rubric Dimension Weights

```python
assert abs(sum(d.weight for d in rubric.dimensions) - 1.0) < 0.001
```

### Window-Role-Template Consistency

- All referenced roles and templates MUST exist
- All referenced roles/templates MUST be active
- No orphaned mappings

---

## 6. Forbidden Behaviors

- SHALL NOT allow tenants to directly edit super org base content
- SHALL NOT allow overrides on non-super-org content (only org_id=1)
- SHALL NOT allow cross-tenant override access
- SHALL NOT allow content edits that break versioning invariant
- SHALL NOT persist entities that fail validation
- SHALL NOT expose repository/database abstractions to API layer
- SHALL NOT perform I/O directly (delegate to repositories)
- **SHALL NOT allow role escalation (admin cannot perform superadmin operations)**
- **SHALL NOT allow read_only admins to mutate any data**
- **SHALL NOT allow override of immutable fields (id, organization_id, scope)**
- **SHALL NOT create overrides without validating base content ownership (org_id=1)**

---

## 7. Dependent Modules

### Dependencies

- `admin/persistence` - Repositories for CRUD operations
- `admin/validation` - Structural validation services
- `shared/errors` - Exception types

### Dependents

- `admin/api` - HTTP handlers

---

## 8. Event Contracts Emitted

(See main admin REQUIREMENTS.md - domain layer emits business events)

---

## 9. Acceptance Criteria

- [ ] Content versioning triggered when in use (all content types)
- [ ] Rubric weight validation enforced before save
- [ ] Window overlap detection works correctly
- [ ] Scope constraints validated before activation
- [ ] Override creation validates base content is super org (org_id=1)
- [ ] Override merge produces correct effective content
- [ ] Deleting override reverts to base content
- [ ] RBAC enforcement prevents unauthorized operations
- [ ] Superadmin can modify base content
- [ ] Admin can only modify tenant-native content and overrides
- [ ] Read_only admin blocked from mutations
- [ ] Cross-tenant access prevented for all tenant-admin roles

---

## 10. Testing Guide

### Unit Tests (Pure Business Logic)

```python
def test_template_versioning_when_in_use():
    # Mock repository to return in_use=True
    # Call domain service edit method
    # Assert new template created with version++

def test_rubric_weight_validation():
    # Create rubric with weights summing to 0.99
    # Expect ValidationError
```

---

## 11. Edge Cases

- Concurrent version creation (handled by unique constraint)
- Editing template while submission is being created (transaction isolation)

---

## 12. Concurrency Concerns

- Use `SELECT FOR UPDATE` for critical sections (checking template usage)
- Optimistic locking for updates (version/timestamp)
