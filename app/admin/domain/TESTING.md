# Admin Domain Layer Testing Guide

## Unit Tests

Focus on business logic in isolation with mocked repositories.

```python
# tests/unit/admin/domain/test_template_service.py

def test_create_new_version_when_template_in_use():
    """Template editing triggers versioning"""
    pass

def test_template_activation_workflow():
    """Activation validates and updates state"""
    pass
```

---

## Integration Tests

Test domain services with real database (test transactions).

```python
# tests/integration/admin/domain/test_template_service_integration.py

def test_template_versioning_with_real_db(db_session):
    """End-to-end versioning with database"""
    pass
```

---

## Coverage Target

- ≥95% branch coverage for all domain services
