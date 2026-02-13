# Admin Module Testing Guide

## Overview

This document provides comprehensive testing scenarios for the Admin module, covering functional correctness, security boundaries, performance benchmarks, and edge cases.

---

## Test Environment Setup

### Prerequisites

```bash
# Database with schema applied
# Test organization and admin users seeded
# JWT tokens for different roles: superadmin, admin, read_only
```

### Test Data Fixtures

```python
# fixtures/admin_test_data.py
ORGANIZATION_A = {"id": 1, "name": "Acme Corp"}
ORGANIZATION_B = {"id": 2, "name": "Beta Inc"}

ADMIN_SUPERADMIN = {"id": 1, "role": "superadmin", "org_id": None}
ADMIN_ORG_A = {"id": 2, "role": "admin", "org_id": 1}
ADMIN_READONLY = {"id": 3, "role": "read_only", "org_id": 1}

GLOBAL_RUBRIC = {"id": 100, "scope": "global", "name": "Standard Rubric"}
ORG_A_RUBRIC = {"id": 101, "scope": "organization", "org_id": 1, "name": "Acme Rubric"}
```

---

## Unit Test Suites

### Template Validation Tests

```python
# tests/unit/admin/domain/test_template_validator.py

def test_valid_template_structure():
    """Valid template passes schema validation"""
    pass

def test_invalid_json_structure_rejected():
    """Malformed JSON fails validation"""
    pass

def test_missing_required_fields_rejected():
    """Template missing 'sections' field fails"""
    pass

def test_template_with_invalid_rubric_reference():
    """Reference to non-existent rubric ID fails"""
    pass

def test_global_template_cannot_reference_org_rubric():
    """Scope violation detected"""
    pass
```

### Rubric Weight Validation Tests

```python
# tests/unit/admin/domain/test_rubric_validator.py

def test_rubric_dimensions_sum_to_one():
    """Dimensions with weights [0.3, 0.4, 0.3] pass"""
    pass

def test_rubric_dimensions_not_sum_to_one_rejected():
    """Dimensions with weights [0.3, 0.4, 0.2] fail"""
    pass

def test_negative_dimension_weight_rejected():
    """Weight -0.1 fails validation"""
    pass
```

### Immutability Enforcement Tests

```python
# tests/unit/admin/domain/test_template_immutability.py

def test_unused_template_can_be_edited():
    """Template with no submissions allows direct edit"""
    pass

def test_used_template_edit_creates_version():
    """Template referenced by submission triggers versioning"""
    pass

def test_version_number_increments_correctly():
    """New version gets old_version + 1"""
    pass
```

---

## Integration Test Suites

### Template CRUD API Tests

```python
# tests/integration/admin/api/test_templates.py

def test_create_template_as_admin(client, admin_token):
    """POST /api/v1/admin/templates"""
    response = client.post(
        "/api/v1/admin/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=VALID_TEMPLATE_PAYLOAD
    )
    assert response.status_code == 201
    assert response.json["id"] is not None

def test_create_template_as_readonly_fails(client, readonly_token):
    """POST /api/v1/admin/templates with read_only role"""
    response = client.post(
        "/api/v1/admin/templates",
        headers={"Authorization": f"Bearer {readonly_token}"},
        json=VALID_TEMPLATE_PAYLOAD
    )
    assert response.status_code == 403

def test_activate_template(client, admin_token):
    """PUT /api/v1/admin/templates/{id}/activate"""
    # Create template
    # Activate it
    # Verify is_active=true

def test_edit_unused_template(client, admin_token):
    """PUT /api/v1/admin/templates/{id}"""
    # Create and edit unused template
    # Verify changes applied to same ID

def test_edit_used_template_creates_version(client, admin_token):
    """PUT /api/v1/admin/templates/{id} when in use"""
    # Create template
    # Create submission referencing it
    # Edit template
    # Verify new template ID created with version++
```

### Window Management Tests

```python
# tests/integration/admin/api/test_windows.py

def test_create_window_with_valid_times(client, admin_token):
    """POST /api/v1/admin/windows"""
    pass

def test_create_window_with_end_before_start_fails(client, admin_token):
    """POST /api/v1/admin/windows with invalid times"""
    pass

def test_create_overlapping_windows_rejected(client, admin_token):
    """POST /api/v1/admin/windows with overlap"""
    pass

def test_window_role_template_mapping(client, admin_token):
    """POST /api/v1/admin/windows with mappings"""
    pass
```

---

## Security Test Suites

### Multi-Tenancy Isolation Tests

```python
# tests/security/test_tenant_isolation.py

def test_org_a_admin_cannot_see_org_b_templates(client):
    """GET /api/v1/admin/templates as Org A admin"""
    # Create template for Org B
    # Authenticate as Org A admin
    # Attempt GET /templates
    # Verify Org B template not in list

def test_org_a_admin_cannot_edit_org_b_template(client):
    """PUT /api/v1/admin/templates/{org_b_template_id}"""
    # Expect 404 or 403

def test_org_a_admin_cannot_delete_org_b_rubric(client):
    """DELETE /api/v1/admin/rubrics/{org_b_rubric_id}"""
    # Expect 403
```

### RBAC Tests

```python
# tests/security/test_rbac.py

def test_read_only_can_get_templates(client, readonly_token):
    """GET /api/v1/admin/templates"""
    assert response.status_code == 200

def test_read_only_cannot_create_template(client, readonly_token):
    """POST /api/v1/admin/templates"""
    assert response.status_code == 403

def test_admin_can_manage_own_org_templates(client, admin_token):
    """CRUD operations within organization"""
    pass

def test_superadmin_can_manage_global_templates(client, superadmin_token):
    """CRUD operations on global scope"""
    pass
```

---

## Performance Test Suites

### Load Tests

```python
# tests/performance/test_template_load.py

def test_list_templates_performance():
    """GET /api/v1/admin/templates with 1000 templates"""
    # Target: <100ms response time

def test_template_retrieval_with_caching():
    """Repeated GET for same template"""
    # First call: DB query
    # Second call: Redis cache hit
    # Target: <10ms for cached

def test_concurrent_template_activations():
    """50 parallel activation requests"""
    # Verify no deadlocks
    # Verify all succeed or fail cleanly
```

---

## Edge Case Test Suites

### Boundary Condition Tests

```python
# tests/edge_cases/test_boundaries.py

def test_window_submission_at_exact_end_time():
    """Submission timestamp == window.end_time"""
    # Test with allow_after_end_time = true
    # Test with allow_after_end_time = false

def test_template_structure_max_size():
    """Template with 50KB JSON structure"""
    pass

def test_rubric_with_100_dimensions():
    """Validate performance and weight sum"""
    pass
```

### Concurrency Tests

```python
# tests/edge_cases/test_concurrency.py

def test_simultaneous_template_edits():
    """Two admins edit same template at same time"""
    # Verify optimistic locking prevents lost updates

def test_template_edit_during_submission_creation():
    """Admin edits template while candidate creates submission"""
    # Verify transaction isolation prevents inconsistency

def test_version_number_collision():
    """Trigger versioning from two threads simultaneously"""
    # Verify unique constraint catches collision
    # Verify retry succeeds
```

---

## Regression Test Suites

(To be populated as bugs are discovered and fixed)

```python
# tests/regression/test_fixed_bugs.py

def test_bug_123_template_deletion_cascade():
    """Regression test for bug #123"""
    pass
```

---

## End-to-End Test Scenarios

### Template Lifecycle E2E

```python
# tests/e2e/test_template_lifecycle.py

def test_complete_template_lifecycle():
    """
    1. Admin creates template
    2. Admin activates template
    3. Window created with template
    4. Candidate creates submission with template
    5. Admin attempts edit (triggers versioning)
    6. Admin verifies old version still in use
    7. Admin activates new version
    8. New submissions use new version
    """
    pass
```

### Window-Based Interview Setup E2E

```python
# tests/e2e/test_window_setup.py

def test_complete_window_setup():
    """
    1. Admin creates roles
    2. Admin creates rubrics
    3. Admin creates templates linking rubrics
    4. Admin creates window with date range
    5. Admin maps roles to templates in window
    6. Window opens (time-based trigger)
    7. Candidate eligible for role sees available interview
    8. Window closes (time-based trigger)
    9. New candidates cannot start interview
    """
    pass
```

---

## Test Execution Commands

```bash
# Run all admin module tests
pytest tests/unit/admin/ tests/integration/admin/ -v

# Run with coverage
pytest tests/admin/ --cov=app/admin --cov-report=html

# Run only security tests
pytest tests/security/ -v

# Run performance tests (separate CI job)
pytest tests/performance/ --benchmark-only

# Run specific test file
pytest tests/integration/admin/api/test_templates.py -v
```

---

## CI/CD Pipeline Integration

### Test Stages

1. **Unit Tests** - Fast, no external dependencies
2. **Integration Tests** - Requires test database
3. **Security Tests** - RBAC and tenant isolation
4. **Performance Tests** - Load and concurrency (nightly)
5. **E2E Tests** - Full workflow validation (pre-release)

### Coverage Requirements

- Unit tests: ≥90% code coverage
- Integration tests: All API endpoints covered
- Security tests: All authentication/authorization paths covered

---

## Manual Testing Checklist

### Exploratory Testing

- [ ] Test template editor UI with various JSON structures
- [ ] Test rapid create/edit/delete operations
- [ ] Test browser back button during template editing
- [ ] Test concurrent edits in multiple browser tabs
- [ ] Test network failure during template save
- [ ] Test very long template/rubric names (boundary testing)

### Accessibility Testing

- [ ] Keyboard navigation through template creation form
- [ ] Screen reader compatibility for error messages
- [ ] Color contrast for validation errors

---

## Testing Tools & Frameworks

- **pytest** - Test runner
- **pytest-asyncio** - Async test support
- **httpx** - HTTP client for API testing
- **factory_boy** - Test data generation
- **faker** - Fake data generation
- **pytest-benchmark** - Performance benchmarking
- **locust** - Load testing (for performance tests)
- **pytest-xdist** - Parallel test execution

---

## Notes for AI Test Generation

When generating tests for this module:

1. Always include multi-tenancy checks
2. Verify audit log entries for mutations
3. Test both success and failure paths
4. Include transaction rollback verification
5. Mock external dependencies (e.g., Redis cache)
6. Use fixtures for common test data
7. Parameterize tests for multiple scenarios
8. Include descriptive assertion messages
