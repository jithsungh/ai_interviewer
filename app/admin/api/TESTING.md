# Admin API Testing Guide

## Test Structure

```
tests/admin/api/
├── test_template_routes.py      # Template endpoint tests
├── test_rubric_routes.py        # Rubric endpoint tests
├── test_window_routes.py        # Window endpoint tests
├── test_role_routes.py          # Role endpoint tests
├── test_auth_middleware.py      # Authentication/authorization tests
├── test_error_handling.py       # Error response format tests
└── fixtures/
    ├── auth_fixtures.py         # JWT tokens for different roles
    └── request_payloads.py      # Sample request bodies
```

---

## Unit Tests (Mocked Dependencies)

### Template Routes

```python
from unittest.mock import Mock, patch
from app.admin.api import routes

def test_create_template_success():
    """POST /api/v1/admin/templates returns 201"""
    # Mock domain service
    # Call route handler
    # Assert 201 and Location header

def test_create_template_validation_error():
    """POST with invalid payload returns 400"""
    # Test malformed JSON
    # Test missing required fields
    # Assert 400 with error details
```

---

## Integration Tests (Full HTTP Stack)

Run with: `pytest tests/admin/api/ -v`

---

## Authentication & Authorization Tests

(See main TESTING.md for details)

---

## Load Testing Script

```python
# tests/load/admin_api_load.py
from locust import HttpUser, task, between

class AdminUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def list_templates(self):
        self.client.get("/api/v1/admin/templates")

    @task(2)
    def create_template(self):
        self.client.post("/api/v1/admin/templates", json=PAYLOAD)
```

Run: `locust -f tests/load/admin_api_load.py`
