# Admin Domain — Human Testing Guide

> **Module**: `app/admin/domain`
> **Layer**: Pure domain logic (no HTTP, no DB)
> **Dependencies**: `app.shared.errors`, `app.shared.auth_context`

---

## 1. Overview

The admin domain module contains **pure business logic** with no HTTP endpoints or direct database access. It is tested via:

1. **Automated unit tests** (primary) — `tests/unit/admin/domain/`
2. **Python REPL smoke tests** (this guide) — manual verification via service instantiation with mock repos
3. **Integration tests** — once `admin/persistence` and `admin/api` layers are implemented

---

## 2. Running Automated Tests

```bash
# All domain unit tests (108 tests)
.venv/bin/python -m pytest tests/unit/admin/domain/ -v

# Individual test files
.venv/bin/python -m pytest tests/unit/admin/domain/test_entities.py -v
.venv/bin/python -m pytest tests/unit/admin/domain/test_authorization.py -v
.venv/bin/python -m pytest tests/unit/admin/domain/test_services.py -v

# With coverage
.venv/bin/python -m pytest tests/unit/admin/domain/ --cov=app.admin.domain --cov-report=term-missing
```

**Expected result**: 108 passed, 0 failed.

---

## 3. REPL Smoke-Test Walkthrough

Use these steps to manually verify domain logic in a Python REPL.

### 3.1 Setup

```python
import time
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.shared.auth_context.models import AdminRole, IdentityContext, UserType
from app.admin.domain.entities import *
from app.admin.domain.services import *

# Create identities
now = int(time.time())
superadmin = IdentityContext(
    user_id=1, user_type=UserType.ADMIN, organization_id=1,
    admin_role=AdminRole.SUPERADMIN, token_version=1,
    issued_at=now, expires_at=now + 3600,
)
tenant_admin = IdentityContext(
    user_id=2, user_type=UserType.ADMIN, organization_id=5,
    admin_role=AdminRole.ADMIN, token_version=1,
    issued_at=now, expires_at=now + 3600,
)
read_only = IdentityContext(
    user_id=3, user_type=UserType.ADMIN, organization_id=5,
    admin_role=AdminRole.READ_ONLY, token_version=1,
    issued_at=now, expires_at=now + 3600,
)

# Mock repos
template_repo = MagicMock()
rubric_repo = MagicMock()
role_repo = MagicMock()
topic_repo = MagicMock()
question_repo = MagicMock()
problem_repo = MagicMock()
window_repo = MagicMock()
submission_repo = MagicMock()
override_repo = MagicMock()
audit_repo = MagicMock()
```

### 3.2 Template CRUD

```python
svc = TemplateService(
    template_repo=template_repo,
    submission_repo=submission_repo,
    override_repo=override_repo,
    rubric_repo=rubric_repo,
    role_repo=role_repo,
    audit_repo=audit_repo,
)

# ✅ Create template (superadmin, base content)
template_repo.exists_with_name.return_value = False
template_repo.create.return_value = Template(
    id=1, name="Full Loop", description="Senior engineer interview",
    scope=TemplateScope.PUBLIC, organization_id=1,
    template_structure={"sections": []}, version=1,
)
result = svc.create_template(
    Template(id=None, name="Full Loop", description="Senior engineer interview",
             scope=TemplateScope.PUBLIC, organization_id=1,
             template_structure={"sections": []}, version=1),
    superadmin,
)
print(f"Created template: id={result.id}, name={result.name}")
# Expected: Created template: id=1, name=Full Loop

# ❌ Read-only admin blocked from creating
try:
    svc.create_template(
        Template(id=None, name="T", description="", scope=TemplateScope.PUBLIC,
                 organization_id=5, template_structure={}, version=1),
        read_only,
    )
except Exception as e:
    print(f"Blocked: {e}")
# Expected: AuthorizationError — Read-only
```

### 3.3 Template Versioning (Invariant #3)

```python
# When template is in use → new version created
existing = Template(id=1, name="Old", description="", scope=TemplateScope.PUBLIC,
                    organization_id=1, template_structure={}, version=1,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc))
template_repo.get_by_id.return_value = existing
submission_repo.template_is_in_use.return_value = True
template_repo.get_latest_version.return_value = 1
template_repo.create.return_value = Template(
    id=50, name="Updated", description="", scope=TemplateScope.PUBLIC,
    organization_id=1, template_structure={}, version=2,
)

result = svc.update_template(1, {"name": "Updated"}, superadmin)
print(f"Versioned: id={result.id}, version={result.version}")
# Expected: Versioned: id=50, version=2

# When NOT in use → mutate in place
submission_repo.template_is_in_use.return_value = False
template_repo.update.return_value = Template(
    id=1, name="Mutated", description="", scope=TemplateScope.PUBLIC,
    organization_id=1, template_structure={}, version=1,
)

result = svc.update_template(1, {"name": "Mutated"}, superadmin)
print(f"In-place: id={result.id}, version={result.version}")
# Expected: In-place: id=1, version=1
```

### 3.4 Rubric Weight Validation

```python
rubric_svc = RubricService(
    rubric_repo=rubric_repo,
    submission_repo=submission_repo,
    override_repo=override_repo,
    audit_repo=audit_repo,
)

rubric_repo.exists_with_name.return_value = False

# ❌ Weights don't sum to 1.0
try:
    rubric_svc.create_rubric(
        Rubric(id=None, organization_id=1, name="Bad", scope=TemplateScope.PUBLIC),
        [
            RubricDimension(rubric_id=0, dimension_name="A", max_score=Decimal("10"),
                           weight=Decimal("0.6"), sequence_order=0),
            RubricDimension(rubric_id=0, dimension_name="B", max_score=Decimal("10"),
                           weight=Decimal("0.6"), sequence_order=1),
        ],
        superadmin,
    )
except Exception as e:
    print(f"Blocked: {e}")
# Expected: ValidationError — weights must sum to 1.0 (got 1.2)

# ✅ Valid weights
rubric_repo.create.return_value = Rubric(id=1, organization_id=1, name="Good", scope=TemplateScope.PUBLIC)
result = rubric_svc.create_rubric(
    Rubric(id=None, organization_id=1, name="Good", scope=TemplateScope.PUBLIC),
    [
        RubricDimension(rubric_id=0, dimension_name="A", max_score=Decimal("10"),
                       weight=Decimal("0.5"), sequence_order=0),
        RubricDimension(rubric_id=0, dimension_name="B", max_score=Decimal("10"),
                       weight=Decimal("0.5"), sequence_order=1),
    ],
    superadmin,
)
print(f"Created rubric: id={result.id}")
# Expected: Created rubric: id=1
```

### 3.5 Window Overlap Detection

```python
window_svc = WindowService(
    window_repo=window_repo,
    role_repo=role_repo,
    template_repo=template_repo,
    submission_repo=submission_repo,
    audit_repo=audit_repo,
)

now_dt = datetime.now(timezone.utc)
role_repo.get_by_id.return_value = Role(id=1, name="Backend Engineer", scope=TemplateScope.PUBLIC, organization_id=1)
template_repo.get_by_id.return_value = Template(
    id=1, name="T", scope=TemplateScope.PUBLIC, organization_id=1,
    template_structure={}, version=1, is_active=True,
)

# ❌ Overlapping windows blocked (allow_resubmission=False)
window_repo.find_overlapping_windows.return_value = [
    Window(id=99, organization_id=5, admin_id=42, name="Existing",
           scope=InterviewScope.GLOBAL, start_time=now_dt, end_time=now_dt + timedelta(days=30),
           timezone="UTC", allow_resubmission=False)
]

try:
    window_svc.create_window(
        Window(id=None, organization_id=5, admin_id=42, name="New Window",
               scope=InterviewScope.GLOBAL,
               start_time=now_dt + timedelta(days=1),
               end_time=now_dt + timedelta(days=15),
               timezone="UTC", allow_resubmission=False),
        [WindowRoleTemplate(id=None, window_id=0, role_id=1, template_id=1, selection_weight=1)],
        tenant_admin,
    )
except Exception as e:
    print(f"Blocked: {e}")
# Expected: ConflictError — Overlapping window
```

### 3.6 Topic Circular Reference Detection

```python
topic_svc = TopicService(
    topic_repo=topic_repo,
    override_repo=override_repo,
    audit_repo=audit_repo,
)

# ❌ Self-referencing parent
try:
    topic_svc.create_topic(
        Topic(id=5, name="Loop", parent_topic_id=5,
              scope=TemplateScope.PUBLIC, organization_id=1),
        superadmin,
    )
except Exception as e:
    print(f"Blocked: {e}")
# Expected: ValidationError — cannot be its own parent

# ❌ Indirect cycle: ancestors contain self
topic_repo.topic_exists_with_name.return_value = False
topic_repo.get_topic_ancestors.return_value = [1, 2, 3]  # 3 is in ancestors
try:
    topic_svc.create_topic(
        Topic(id=3, name="C", parent_topic_id=1,
              scope=TemplateScope.PUBLIC, organization_id=1),
        superadmin,
    )
except Exception as e:
    print(f"Blocked: {e}")
# Expected: ValidationError — Circular reference detected
```

### 3.7 Override Management

```python
# ✅ Tenant admin creates override on super-org content
template_repo.get_by_id.return_value = Template(
    id=1, name="Base", scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
    template_structure={}, version=1,
)
override_repo.get_override.return_value = None
override_repo.create_override.return_value = OverrideRecord(
    id=1, organization_id=5, base_content_id=1,
    content_type=ContentType.TEMPLATE,
    override_fields={"name": "Custom Template"},
)

result = svc.create_template_override(1, {"name": "Custom Template"}, tenant_admin)
print(f"Override created: org={result.organization_id}, fields={result.override_fields}")
# Expected: Override created: org=5, fields={'name': 'Custom Template'}

# ❌ Immutable field blocked
try:
    svc.create_template_override(1, {"id": 999}, tenant_admin)
except Exception as e:
    print(f"Blocked: {e}")
# Expected: ValidationError — immutable fields

# ❌ Override on non-super-org content blocked
template_repo.get_by_id.return_value = Template(
    id=2, name="Tenant", scope=TemplateScope.PUBLIC, organization_id=99,
    template_structure={}, version=1,
)
try:
    svc.create_template_override(2, {"name": "X"}, tenant_admin)
except Exception as e:
    print(f"Blocked: {e}")
# Expected: AuthorizationError — super-org
```

---

## 4. Invariant Checklist

| # | Invariant | Service | Test Coverage |
|---|-----------|---------|---------------|
| 1 | **Template immutability** — in-use templates create new version | `TemplateService.update_template` | `test_update_in_use_template_creates_new_version` |
| 2 | **Rubric weights sum = 1.0** (±0.001 tolerance) | `RubricService.create_rubric` | `test_create_rubric_weight_sum_invalid`, `test_create_rubric_weight_within_tolerance` |
| 3 | **Unique sequence_order** per rubric dimension | `RubricService.create_rubric` | `test_create_rubric_duplicate_sequence_order` |
| 4 | **No topic cycles** — parent cannot create circular reference | `TopicService.create_topic/update_topic` | `test_circular_reference_self_parent`, `test_circular_reference_via_ancestors` |
| 5 | **Window end > start** | `WindowService.create_window` | `test_create_window_end_before_start` |
| 6 | **No overlapping windows** (when allow_resubmission=false) | `WindowService.create_window` | `test_create_window_overlap_rejected` |
| 7 | **Override immutable field guard** | `_validate_override_fields` | `test_create_override_with_immutable_field_fails` |
| 8 | **RBAC: read-only blocked from mutations** | All services | `test_create_template_read_only_blocked` |
| 9 | **RBAC: tenant isolation** | All getter methods | `test_get_template_tenant_isolation`, `test_get_window_tenant_isolation` |
| 10 | **RBAC: superadmin-only for base content** | All create methods | `test_create_base_template_blocked_for_tenant_admin` |
| 11 | **Deactivation cascades** — marks overrides stale | Template/Rubric deactivation | `test_deactivate_cascades_to_overrides` |

---

## 5. Error Type Reference

All domain errors reuse `app.shared.errors`:

| Error Type | HTTP Status | When Raised |
|------------|-------------|-------------|
| `NotFoundError` | 404 | Entity not found or tenant-isolated |
| `ConflictError` | 409 | Duplicate name, duplicate override, overlapping window |
| `ValidationError` | 422 | Weight sum mismatch, cycle detected, immutable field, invalid time range |
| `AuthorizationError` | 403 | RBAC violation (read-only, tenant, non-superadmin) |
| `TenantIsolationViolation` | 403 | Cross-tenant access attempt |

---

## 6. File Manifest

| File | Description | Tests |
|------|-------------|-------|
| `entities.py` | 14 dataclass entities, 6 enums, constants | 45 tests |
| `protocols.py` | 10 repository protocol interfaces | (validated via type-checking) |
| `authorization.py` | 3 RBAC functions | 15 tests |
| `services.py` | 7 domain services | 63 tests |
| `__init__.py` | Public API exports | (import smoke test) |

**Total**: 108 unit tests, 0 integration tests (pending persistence layer).
