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

**Base Content Tables (Super Org - org_id=1):**

- `interview_templates`
- `interview_template_roles`
- `interview_template_rubrics`
- `rubrics`
- `rubric_dimensions`
- `roles`
- `topics`
- `coding_topics`
- `questions`
- `coding_problems`
- `interview_submission_windows`
- `window_role_templates`

**Override Tables (Tenant-specific modifications):**

- `template_overrides`
- `rubric_overrides`
- `role_overrides`
- `topic_overrides`
- `question_overrides`
- `coding_problem_overrides`

### Read-Only Access

- `organizations` (for multi-tenancy checks)
- `admins` (for RBAC validation: superadmin, admin, read_only)
- `interview_submissions` (for immutability checks)

---

## 3. Input Constraints

### From Domain Layer

- Validated domain entities (business rules already enforced)
- Database session/transaction context
- Organization ID for multi-tenancy scoping
- User role for RBAC enforcement (superadmin/admin/read_only)

### Query Parameters

- Filters: organization_id, scope, is_active, content_type, etc.
- Pagination: page, per_page
- Sorting: order_by, direction
- Override resolution flag: include_overrides (boolean)

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
def get_effective_content(base_content_id: int, org_id: int, content_type: str):
    """
    Generic override resolution for any content type.
    Merge base content with tenant override (if exists).
    Returns effective content for given organization.
    
    Supported content_types:
    - template, rubric, role, topic, question, coding_problem
    """
    # 1. Load base content (must be super org)
    base_table = get_table_for_type(content_type)  # e.g., 'interview_templates'
    base = session.query(base_table).filter_by(
        id=base_content_id,
        organization_id=1  # Super org only
    ).one_or_none()
    
    if not base:
        raise NotFoundError(f"Base {content_type} {base_content_id} not found")
    
    # 2. Check for tenant override
    override_table = get_override_table_for_type(content_type)  # e.g., 'template_overrides'
    override = session.query(override_table).filter_by(
        base_content_id=base_content_id,
        organization_id=org_id,
        is_active=True
    ).first()
    
    # 3. Merge if override exists
    if override:
        effective_data = {**base.to_dict(), **override.override_fields}
        return create_entity(content_type, effective_data)
    
    # 4. Return base if no override
    return base

# Example: Query all templates visible to tenant
def list_content_for_org(org_id: int, content_type: str) -> List[Entity]:
    """
    Returns: Super org base content + tenant native content
    Each base content merged with tenant override if exists
    """
    base_table = get_table_for_type(content_type)
    
    # Base content (super org)
    base_content = session.query(base_table).filter_by(
        organization_id=1,  # super org
        is_active=True
    ).all()
    
    # Apply tenant overrides
    effective_content = [
        get_effective_content(c.id, org_id, content_type) for c in base_content
    ]
    
    # Native tenant content
    native_content = session.query(base_table).filter_by(
        organization_id=org_id,
        is_active=True
    ).all()
    
    return effective_content + native_content

# RBAC-aware queries
def list_content_with_rbac(org_id: int, user_role: str, content_type: str):
    """
    Apply RBAC filtering:
    - superadmin: Can query all organizations
    - admin: Can query only own organization
    - read_only: Can query only own organization (read-only)
    """
    if user_role == "superadmin":
        # Superadmin sees everything
        return session.query(get_table_for_type(content_type)).all()
    
    # Admin and read_only see only own org (with overrides applied)
    return list_content_for_org(org_id, content_type)
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
- SHALL NOT create overrides for non-super-org content (base must be org_id=1)
- SHALL NOT bypass RBAC checks in queries
- SHALL NOT allow read_only role to execute write operations
- SHALL NOT allow cross-tenant data access for non-superadmin roles

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
- [ ] Override merge correctly applies tenant-specific fields over base (all content types)
- [ ] Querying base content returns effective (merged) content for tenant
- [ ] Creating override validates base content exists and is super org content (org_id=1)
- [ ] Deleting override reverts tenant view to base content
- [ ] Tenant cannot query other tenant's overrides
- [ ] RBAC filtering applied correctly (superadmin vs admin vs read_only)
- [ ] Superadmin can query cross-tenant data
- [ ] Non-superadmin queries scoped to own organization only
- [ ] Override creation for all content types follows same pattern

---

## 10. Testing Guide

### Unit Tests (Mocked SQLAlchemy)

```python
def test_content_repository_get_by_id():
    # Mock session query
    # Call repository method
    # Assert correct SQL generated

def test_override_resolution_merges_correctly():
    # Mock base content and override
    # Call get_effective_content()
    # Assert override fields take precedence

def test_rbac_filtering_superadmin():
    # Mock superadmin context
    # Query should return all organizations' content

def test_rbac_filtering_admin():
    # Mock admin context
    # Query should return only own org content + overrides
```

### Integration Tests (Real Database)

```python
def test_template_repository_create(db_session):
    repo = TemplateRepository(db_session)
    template = repo.create(template_data)
    assert template.id is not None

def test_question_override_creation(db_session):
    # Create base question (org_id=1)
    # Create override for tenant (org_id=2)
    # Query effective question
    # Assert override applied

def test_cross_tenant_isolation(db_session):
    # Create override for tenant A
    # Query as tenant B
    # Assert tenant B cannot see tenant A's override
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
