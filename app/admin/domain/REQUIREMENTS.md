# Admin Domain Layer Requirements

## 1. Purpose

The domain layer contains **core business logic** for admin operations:

- Template versioning and immutability enforcement
- Rubric validation (dimension weights, schema checks)
- Window scheduling logic (overlap detection, time validation)
- Scope resolution (global vs organization)
- Activation/deactivation workflows

**Responsibilities:** Business rules, orchestration between persistence and validation layers
**Not Responsible For:** HTTP concerns, database queries, external I/O

---

## 2. Owned Tables

**None** - Domain layer does not directly access database. Delegates to `admin/persistence` repositories.

---

## 3. Input Constraints

### From API Layer

- Pre-validated request DTOs (types, formats correct)
- Authenticated context with `user_id`, `role`, `organization_id`

### Business Rules to Enforce

- **Template editing:** If template is referenced by any submission → create new version
- **Rubric dimension weights:** Must sum to 1.0 (tolerance: ±0.001)
- **Window timing:** `end_time` > `start_time`
- **Scope constraints:** Global templates can only reference global rubrics

---

## 4. Output Guarantees

### Return Types

- Success: Domain entity objects (Template, Rubric, Window)
- Failure: Raises typed exceptions (ValidationError, ConflictError, NotFoundError)

### Transactional Guarantees

- All mutations wrapped in database transactions
- On exception: Automatic rollback
- Audit log entries written within same transaction

### Idempotency

- Repeated identical requests produce same final state
- Duplicate activations are no-ops

---

## 5. Invariants

### Template Immutability (ERD Invariant #3)

```python
if template.is_in_use():
    new_template = template.create_version()
    return new_template
else:
    template.update(changes)
    return template
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
- SHALL NOT allow overrides on non-super-org content
- SHALL NOT allow cross-tenant override access
- SHALL NOT allow template edits that break versioning invariant
- SHALL NOT persist entities that fail validation
- SHALL NOT expose repository/database abstractions to API layer
- SHALL NOT perform I/O directly (delegate to repositories)

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

- [ ] Template versioning triggered when in use
- [ ] Rubric weight validation enforced before save
- [ ] Window overlap detection works correctly
- [ ] Scope constraints validated before activation

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
