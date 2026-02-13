# Admin Persistence Layer Requirements

## 1. Purpose

The persistence layer provides **repository abstractions** for database access:

- CRUD operations on admin-owned tables
- Multi-tenancy filtering
- Query optimization (indexes, joins)
- Transaction management support

**Responsibilities:** Data access, query building, ORM interaction
**Not Responsible For:** Business logic, validation, HTTP concerns

---

## 2. Owned Tables

### Direct Ownership (Read/Write)

**Base Content Tables:**

- `interview_templates`
- `interview_template_roles`
- `interview_template_rubrics`
- `rubrics`
- `rubric_dimensions`
- `roles`
- `topics`
- `coding_topics`
- `interview_submission_windows`
- `window_role_templates`

**Override Tables:**

- `template_overrides`
- `rubric_overrides`
- `role_overrides`
- `topic_overrides`

### Read-Only Access

- `organizations` (for multi-tenancy checks)
- `interview_submissions` (for immutability checks)

---

## 3. Input Constraints

### From Domain Layer

- Validated domain entities (business rules already enforced)
- Database session/transaction context
- Organization ID for multi-tenancy scoping

### Query Parameters

- Filters: organization_id, scope, is_active, etc.
- Pagination: page, per_page
- Sorting: order_by, direction

---

## 4. Output Guarantees

### Return Types

- Single entity: Domain model object or None
- Multiple entities: List of domain model objects
- Exists checks: Boolean
- Count queries: Integer

### Performance

- Single entity lookup: <10ms (indexed primary key)
- Filtered list queries: <100ms (indexed foreign keys)
- Batch operations: Use bulk insert/update

### Data Integrity

- All foreign key constraints enforced
- Unique constraints enforced
- Check constraints enforced

---

## 5. Invariants

### Multi-Tenancy Scoping

```python
# Every query must include organization_id filter (except global scope)
query = query.filter(
    (Template.organization_id == org_id) | (Template.scope == 'global')
)
```

### Soft Deletes

```python
# Logical deletion via is_active flag
template.is_active = False
# Never hard-delete referenced entities
```

### Override Resolution Pattern

```python
def get_effective_template(base_template_id: int, org_id: int) -> Template:
    """
    Merge base template with tenant override (if exists).
    Returns effective template for given organization.
    """
    # 1. Load base template
    base = session.query(InterviewTemplate).filter_by(id=base_template_id).one()

    # 2. Check for tenant override
    override = session.query(TemplateOverride).filter_by(
        base_template_id=base_template_id,
        organization_id=org_id,
        is_active=True
    ).first()

    # 3. Merge if override exists
    if override:
        effective_data = {**base.to_dict(), **override.override_fields}
        return Template(**effective_data)

    # 4. Return base if no override
    return base

# Example: Query all templates visible to tenant
def list_templates_for_org(org_id: int) -> List[Template]:
    """
    Returns: Super org base templates + tenant native templates
    Each base template merged with tenant override if exists
    """
    # Base templates (super org)
    base_templates = session.query(InterviewTemplate).filter_by(
        organization_id=1,  # super org
        is_active=True
    ).all()

    # Apply tenant overrides
    effective_templates = [
        get_effective_template(t.id, org_id) for t in base_templates
    ]

    # Native tenant templates
    native_templates = session.query(InterviewTemplate).filter_by(
        organization_id=org_id,
        is_active=True
    ).all()

    return effective_templates + native_templates
```

---

## 6. Forbidden Behaviors

- SHALL NOT expose raw SQL to domain layer
- SHALL NOT return SQLAlchemy models directly (map to domain entities)
- SHALL NOT skip override resolution (always merge base + override)
- SHALL NOT allow direct queries that bypass multi-tenancy scoping
- SHALL NOT perform business logic in repositories
- SHALL NOT allow tenants to modify super org base content directly
- SHALL NOT expose other tenants' overrides

---

## 7. Dependent Modules

### Dependencies

- `persistence/postgres` - SQLAlchemy engine, Base models
- `shared/auth_context` - Current organization context

### Dependents

- `admin/domain` - Domain services

---

## 8. Event Contracts Emitted

**None** - Persistence layer is passive, emits no events

---

## 9. Acceptance Criteria

- [ ] All CRUD operations work with multi-tenancy filtering
- [ ] Queries use appropriate indexes (verify with EXPLAIN)
- [ ] Bulk operations are atomic (all-or-nothing)
- [ ] Soft delete preserves referential integrity
- [ ] Override merge correctly applies tenant-specific fields over base
- [ ] Querying base template returns effective (merged) template for tenant
- [ ] Creating override validates base_template exists and is super org content
- [ ] Deleting override reverts tenant view to base content
- [ ] Tenant cannot query other tenant's overrides

---

## 10. Testing Guide

### Unit Tests (Mocked SQLAlchemy)

```python
def test_template_repository_get_by_id():
    # Mock session query
    # Call repository method
    # Assert correct SQL generated
```

### Integration Tests (Real Database)

```python
def test_template_repository_create(db_session):
    repo = TemplateRepository(db_session)
    template = repo.create(template_data)
    assert template.id is not None
```

---

## 11. Edge Cases

- Query with no results → Return empty list (not None)
- Concurrent inserts with unique constraint → Raise IntegrityError
- Transaction rollback mid-operation → All changes reverted

---

## 12. Concurrency Concerns

- Use row-level locking for critical reads: `WITH FOR UPDATE`
- Avoid long-running transactions (blocking)
- Connection pool exhaustion: Ensure connections released
