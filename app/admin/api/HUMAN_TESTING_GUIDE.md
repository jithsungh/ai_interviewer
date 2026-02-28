# Admin API — Human Testing Guide

> Endpoint prefix: `http://localhost:8000/api/v1/admin`

## Prerequisites

1. Start the application:
   ```bash
   cd /home/jithsungh/projects/ai_interviewer
   .venv/bin/uvicorn app.bootstrap:create_app --factory --reload --port 8000
   ```

2. Obtain a JWT token by logging in as an admin user:
   ```bash
   # Register an admin (first time only)
   curl -s -X POST http://localhost:8000/api/v1/auth/register/admin \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@test.com",
       "password": "SecurePass123!",
       "organization_id": 1,
       "admin_role": "superadmin"
     }' | jq .

   # Login
   TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "admin@test.com", "password": "SecurePass123!"}' | jq -r '.access_token')
   echo "Token: $TOKEN"
   ```

3. Set the `AUTH` header for subsequent requests:
   ```bash
   AUTH="Authorization: Bearer $TOKEN"
   ```

---

## Templates

### List templates
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/templates | jq .
```

### List templates (paginated + filtered)
```bash
curl -s -H "$AUTH" "http://localhost:8000/api/v1/admin/templates?page=1&per_page=5&is_active=true" | jq .
```

### Create template
```bash
curl -s -X POST http://localhost:8000/api/v1/admin/templates \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "name": "Backend Engineer v1",
    "description": "Standard backend interview template",
    "scope": "public",
    "template_structure": {
      "sections": [
        {"name": "intro", "duration_minutes": 5},
        {"name": "technical", "duration_minutes": 30},
        {"name": "coding", "duration_minutes": 25}
      ]
    },
    "rules": {"max_retakes": 1},
    "total_estimated_time_minutes": 60
  }' | jq .
```

### Get template by ID
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/templates/1 | jq .
```

### Update template
```bash
curl -s -X PUT http://localhost:8000/api/v1/admin/templates/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"description": "Updated description"}' | jq .
```

### Deactivate template (soft-delete)
```bash
curl -s -X DELETE http://localhost:8000/api/v1/admin/templates/1 -H "$AUTH" -w "\nHTTP %{http_code}\n"
# Expect: HTTP 204
```

### Activate template
```bash
curl -s -X PUT http://localhost:8000/api/v1/admin/templates/1/activate -H "$AUTH" | jq .
```

### Create override for a base template
```bash
curl -s -X POST http://localhost:8000/api/v1/admin/templates/1/overrides \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"override_fields": {"description": "Custom org description"}}' | jq .
```

### Get template override
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/templates/1/overrides | jq .
```

### Update template override
```bash
curl -s -X PUT http://localhost:8000/api/v1/admin/templates/1/overrides \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"override_fields": {"description": "Revised override"}}' | jq .
```

### Delete template override
```bash
curl -s -X DELETE http://localhost:8000/api/v1/admin/templates/1/overrides -H "$AUTH" -w "\nHTTP %{http_code}\n"
# Expect: HTTP 204
```

---

## Rubrics

### List rubrics
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/rubrics | jq .
```

### Create rubric (with dimensions)
```bash
curl -s -X POST http://localhost:8000/api/v1/admin/rubrics \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "name": "Technical Competency",
    "description": "Standard technical scoring rubric",
    "scope": "public",
    "dimensions": [
      {"dimension_name": "Problem Solving", "max_score": "10", "weight": "0.4", "criteria": {"1": "Poor", "5": "Average", "10": "Excellent"}},
      {"dimension_name": "Communication", "max_score": "10", "weight": "0.3"},
      {"dimension_name": "Code Quality", "max_score": "10", "weight": "0.3"}
    ]
  }' | jq .
```

### Get rubric
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/rubrics/1 | jq .
```

### Update rubric
```bash
curl -s -X PUT http://localhost:8000/api/v1/admin/rubrics/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"description": "Updated rubric description"}' | jq .
```

### Deactivate rubric
```bash
curl -s -X DELETE http://localhost:8000/api/v1/admin/rubrics/1 -H "$AUTH" -w "\nHTTP %{http_code}\n"
```

### Get rubric dimensions
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/rubrics/1/dimensions | jq .
```

---

## Roles

### List roles
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/roles | jq .
```

### Create role
```bash
curl -s -X POST http://localhost:8000/api/v1/admin/roles \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Backend Developer", "description": "Backend engineering role", "scope": "public"}' | jq .
```

### Get role
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/roles/1 | jq .
```

### Update role
```bash
curl -s -X PUT http://localhost:8000/api/v1/admin/roles/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"description": "Senior backend engineering role"}' | jq .
```

---

## Topics

### List + Create + Get + Update
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/topics | jq .

curl -s -X POST http://localhost:8000/api/v1/admin/topics \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Data Structures", "scope": "public", "estimated_time_minutes": 20}' | jq .

curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/topics/1 | jq .

curl -s -X PUT http://localhost:8000/api/v1/admin/topics/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"estimated_time_minutes": 25}' | jq .
```

---

## Questions

### List + Create + Get + Update + Deactivate
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/questions | jq .

curl -s -X POST http://localhost:8000/api/v1/admin/questions \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "question_text": "Describe the SOLID principles",
    "question_type": "technical",
    "difficulty": "medium",
    "scope": "public",
    "estimated_time_minutes": 10
  }' | jq .

curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/questions/1 | jq .

curl -s -X PUT http://localhost:8000/api/v1/admin/questions/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"answer_text": "S=Single Responsibility, O=Open/Closed, ..."}' | jq .

curl -s -X DELETE http://localhost:8000/api/v1/admin/questions/1 -H "$AUTH" -w "\nHTTP %{http_code}\n"
```

### Create question override
```bash
curl -s -X POST http://localhost:8000/api/v1/admin/questions/1/overrides \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"override_fields": {"question_text": "Custom question text for our org"}}' | jq .
```

---

## Coding Problems

### List + Create + Get + Update + Deactivate
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/coding-problems | jq .

curl -s -X POST http://localhost:8000/api/v1/admin/coding-problems \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "title": "Two Sum",
    "body": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
    "difficulty": "easy",
    "scope": "public",
    "estimated_time_minutes": 20,
    "examples": [{"input": "nums = [2,7,11,15], target = 9", "output": "[0,1]"}],
    "hints": [{"text": "Try using a hash map"}],
    "code_snippets": {"python": "def twoSum(self, nums: List[int], target: int) -> List[int]:"}
  }' | jq .

curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/coding-problems/1 | jq .

curl -s -X PUT http://localhost:8000/api/v1/admin/coding-problems/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"difficulty": "medium"}' | jq .

curl -s -X DELETE http://localhost:8000/api/v1/admin/coding-problems/1 -H "$AUTH" -w "\nHTTP %{http_code}\n"
```

---

## Windows

### List + Create + Get + Update
```bash
curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/windows | jq .

curl -s -X POST http://localhost:8000/api/v1/admin/windows \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "name": "Spring 2024 Hiring",
    "scope": "global",
    "start_time": "2024-03-01T00:00:00Z",
    "end_time": "2024-03-15T23:59:59Z",
    "timezone": "UTC",
    "max_allowed_submissions": 100,
    "mappings": [
      {"role_id": 1, "template_id": 1, "selection_weight": 1}
    ]
  }' | jq .

curl -s -H "$AUTH" http://localhost:8000/api/v1/admin/windows/1 | jq .

curl -s -X PUT http://localhost:8000/api/v1/admin/windows/1 \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name": "Spring 2024 Hiring (Extended)"}' | jq .
```

---

## Error Cases to Test

| Scenario | Expected |
|---|---|
| No Authorization header | 401 or 403 |
| Invalid JSON body | 422 |
| Missing required field (e.g. template with no name) | 422 |
| Non-existent resource ID | 404 |
| Duplicate name creation | 409 |
| Rubric dimension weights don't sum to 1.0 | 422 |
| Window end_time before start_time | 422 |
| Override on immutable field (id, scope) | 422 |
| Empty mappings array on window create | 422 |

---

## OpenAPI Docs

Once the server is running, browse the auto-generated OpenAPI documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
