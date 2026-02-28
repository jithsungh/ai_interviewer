# AI Prompts Module — Human Testing Guide

**Module:** `app.ai.prompts`  
**Purpose:** Verify prompt template retrieval, scope resolution, parsing, and rendering  
**Prerequisites:** PostgreSQL database with schema applied, seed data loaded

---

## Quick Start

### 1. Activate Virtual Environment

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate
```

### 2. Seed Prompt Templates

Run the seed SQL to populate the `prompt_templates` table with the two PEAS-aligned templates:

```bash
# Option A: psql direct
psql -h <host> -U postgres -d interviewer -f app/ai/prompts/seed_prompt_templates.sql

# Option B: via environment variable
psql "$DATABASE_URL" -f app/ai/prompts/seed_prompt_templates.sql
```

**Expected Output:**
```
INSERT 0 1
INSERT 0 1
```

> The seed is idempotent (`ON CONFLICT DO NOTHING`). Re-running is safe.

### 3. Verify Seed Data

```bash
psql "$DATABASE_URL" -c "SELECT id, name, prompt_type, scope, version, is_active FROM prompt_templates WHERE organization_id = 1 ORDER BY id;"
```

**Expected Output (2 rows):**
```
 id |          name           |     prompt_type      | scope  | version | is_active
----+-------------------------+----------------------+--------+---------+-----------
  1 | question_generation_v1  | question_generation  | public |       1 | t
  2 | evaluation_v1           | evaluation           | public |       1 | t
```

---

## Test Scenarios

### Test 1: Repository — Fetch Global Prompt by Type

**Objective:** Verify `SqlPromptTemplateRepository.get_active_by_type` returns the correct global prompt.

```python
# Python REPL
from app.persistence.postgres import init_postgres
from app.persistence.postgres.session import init_session_factory, get_session_factory
from app.config.settings import get_settings

settings = get_settings()
init_postgres(settings.database)
init_session_factory()

factory = get_session_factory()
session = factory()

from app.ai.prompts.repository import SqlPromptTemplateRepository

repo = SqlPromptTemplateRepository(session)
prompt = repo.get_active_by_type("question_generation")
print(f"Name: {prompt.name}")
print(f"Type: {prompt.prompt_type}")
print(f"Scope: {prompt.scope}")
print(f"Version: {prompt.version}")
print(f"Active: {prompt.is_active}")
print(f"Temperature: {prompt.temperature}")
print(f"Max Tokens: {prompt.max_tokens}")

session.close()
```

**Expected Output:**
```
Name: question_generation_v1
Type: question_generation
Scope: public
Version: 1
Active: True
Temperature: 0.7
Max Tokens: 1500
```

---

### Test 2: Repository — Scope Fallback Chain

**Objective:** Verify org → global fallback when no org-scoped prompt exists.

```python
from app.ai.prompts.repository import SqlPromptTemplateRepository

session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)

# Use any valid org_id that does NOT have a 'question_generation' override
result = repo.get_active_by_type("question_generation", organization_id=42)
print(f"Resolved: {result.name}")  # Should fallback to global
print(f"Org ID: {result.organization_id}")  # Should be 1 (SUPER_ORG_ID)

session.close()
```

**Expected Output:**
```
Resolved: question_generation_v1
Org ID: 1
```

---

### Test 3: Template Parser — Variable Extraction

**Objective:** Verify `TemplateParser` correctly extracts `{{variable}}` placeholders.

```python
from app.ai.prompts.parser import TemplateParser

parser = TemplateParser()

# Question generation user prompt has these variables:
template = "Role: {{role}}\nTopic: {{topic}}\nDifficulty: {{difficulty}}"
variables = parser.extract_variables(template)
print(f"Variables: {variables}")
# Expected: ['difficulty', 'role', 'topic'] (sorted)

# Validate all required variables are present
errors = parser.validate(template, {"role": "Backend Engineer", "topic": "Python"})
print(f"Errors (missing 'difficulty'): {errors}")
```

**Expected Output:**
```
Variables: ['difficulty', 'role', 'topic']
Errors (missing 'difficulty'): ['Missing required variable: difficulty']
```

---

### Test 4: Prompt Renderer — Full Rendering

**Objective:** Verify `PromptRenderer` substitutes variables into both system_prompt and user_prompt.

```python
from app.ai.prompts.renderer import PromptRenderer
from app.ai.prompts.entities import PromptTemplate

renderer = PromptRenderer()

# Minimal template for testing
template = PromptTemplate(
    id=1,
    name="test",
    prompt_type="question_generation",
    scope="public",
    organization_id=1,
    system_prompt="Generate a {{difficulty}} question about {{topic}}.",
    user_prompt="Topic: {{topic}}\nDifficulty: {{difficulty}}\nRole: {{role}}",
    model_id=None,
    model_config={"temperature": 0.7},
    version=1,
    is_active=True,
)

rendered = renderer.render(template, {
    "topic": "Python decorators",
    "difficulty": "medium",
    "role": "Senior Backend Engineer",
})

print(f"System: {rendered.system_prompt}")
print(f"Text: {rendered.text}")
print(f"Variables used: {rendered.variables_used}")
print(f"Temperature: {rendered.temperature}")
```

**Expected Output:**
```
System: Generate a medium question about Python decorators.
Text: Topic: Python decorators
Difficulty: medium
Role: Senior Backend Engineer
Variables used: ['difficulty', 'role', 'topic']
Temperature: 0.7
```

---

### Test 5: Prompt Service — End-to-End Retrieval + Rendering

**Objective:** Verify `PromptService` orchestrates retrieval and rendering in one call.

```python
from app.ai.prompts.repository import SqlPromptTemplateRepository
from app.ai.prompts.service import PromptService

session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)
service = PromptService(repo)

# Render the question_generation prompt with variables
rendered = service.get_rendered_prompt(
    prompt_type="question_generation",
    variables={
        "role": "Senior Backend Engineer",
        "topic": "Python",
        "subtopic": "Decorators and Metaclasses",
        "difficulty": "hard",
        "question_type": "analytical",
        "remaining_time_minutes": "25",
        "exchange_number": "3",
        "total_exchanges": "8",
        "candidate_context": "5 years Python experience, Django background",
        "last_score_percent": "72",
        "performance_trend": "improving",
        "previously_asked": "1. Explain Python GIL\n2. Compare list vs tuple",
        "rubric_dimensions": "Technical Accuracy (0-10), Code Quality (0-10)",
    },
)

print(f"Prompt type: {rendered.prompt_type}")
print(f"Version: {rendered.version}")
print(f"Variables used: {len(rendered.variables_used)} variables")
print(f"System prompt length: {len(rendered.system_prompt)} chars")
print(f"User prompt length: {len(rendered.text)} chars")
print(f"Temperature: {rendered.temperature}")
print(f"Max tokens: {rendered.max_tokens}")

session.close()
```

**Expected Output (approximate):**
```
Prompt type: question_generation
Version: 1
Variables used: 13 variables
System prompt length: ~1200 chars
User prompt length: ~500 chars
Temperature: 0.7
Max tokens: 1500
```

---

### Test 6: Evaluation Agent Prompt

**Objective:** Verify evaluation prompt rendering with deterministic settings.

```python
session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)
service = PromptService(repo)

rendered = service.get_rendered_prompt(
    prompt_type="evaluation",
    variables={
        "question_text": "Explain the difference between @staticmethod and @classmethod in Python.",
        "candidate_response": "Both are decorators. @staticmethod doesn't take any special first parameter, while @classmethod takes cls as the first parameter which represents the class itself. @classmethod can access class-level attributes and methods.",
        "difficulty": "medium",
        "skill_tag": "Python OOP",
        "question_type": "conceptual",
        "rubric_dimensions": '[{"name": "Technical Accuracy", "max_score": 10, "criteria": "Correctness of explanation"}]',
        "evaluation_instructions": "Score strictly from the rubric. Partial credit allowed.",
    },
)

print(f"Prompt type: {rendered.prompt_type}")
print(f"Temperature: {rendered.temperature}")  # Should be 0.0 (deterministic)
print(f"Deterministic: {rendered.model_config.get('deterministic')}")

session.close()
```

**Expected Output:**
```
Prompt type: evaluation
Temperature: 0.0
Deterministic: True
```

---

### Test 7: List Active Types

**Objective:** Verify type enumeration works.

```python
session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)
service = PromptService(repo)

types = service.list_available_types()
print(f"Active types: {types}")

session.close()
```

**Expected Output:**
```
Active types: ['evaluation', 'question_generation']
```

---

### Test 8: Error Handling — Missing Variables

**Objective:** Verify `VariableMissingError` is raised when required variables are missing.

```python
from app.ai.prompts.errors import VariableMissingError

session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)
service = PromptService(repo)

try:
    service.get_rendered_prompt(
        prompt_type="question_generation",
        variables={"role": "Engineer"},  # Missing most required variables
    )
except VariableMissingError as e:
    print(f"Error: {e.message}")
    print(f"Missing: {e.missing_variables}")
    print(f"Status code: {e.status_code}")

session.close()
```

**Expected Output:**
```
Error: Missing required template variables
Missing: ['candidate_context', 'difficulty', 'exchange_number', ...]
Status code: 422
```

---

### Test 9: Error Handling — Prompt Not Found

**Objective:** Verify `PromptNotFoundError` for non-existent prompt types.

```python
from app.ai.prompts.errors import PromptNotFoundError

session = get_session_factory()()
repo = SqlPromptTemplateRepository(session)
service = PromptService(repo)

try:
    service.get_prompt("nonexistent_type")
except PromptNotFoundError as e:
    print(f"Error: {e.message}")
    print(f"Status code: {e.status_code}")

session.close()
```

**Expected Output:**
```
Error: No active prompt template found for type 'nonexistent_type'
Status code: 404
```

---

## Running Automated Tests

### Unit Tests (no DB required)

```bash
python -m pytest tests/unit/ai/prompts/ -v --tb=short
```

**Expected:** 100 tests passed

### Integration Tests (requires PostgreSQL)

```bash
# Optional: override test DB URL
export TEST_DATABASE_URL="postgresql://postgres:password@localhost/interviewer"

python -m pytest tests/integration/ai/prompts/ -v --tb=short
```

**Expected:** 35 tests passed

### All Prompts Tests

```bash
python -m pytest tests/unit/ai/prompts/ tests/integration/ai/prompts/ -v --tb=short
```

**Expected:** 135 tests passed

---

## Module Architecture

```
app/ai/prompts/
├── __init__.py          # Public API exports
├── entities.py          # PromptTemplate, RenderedPrompt, PromptType (dataclasses)
├── errors.py            # PromptNotFoundError, VariableMissingError, TemplateSyntaxError
├── mappers.py           # ORM ↔ Entity bidirectional mappers
├── models.py            # PromptTemplateModel (SQLAlchemy ORM)
├── parser.py            # TemplateParser ({{variable}} extraction/validation)
├── protocols.py         # PromptTemplateRepository (Protocol)
├── renderer.py          # PromptRenderer (variable substitution + sanitization)
├── repository.py        # SqlPromptTemplateRepository (concrete implementation)
├── service.py           # PromptService (orchestration layer)
└── seed_prompt_templates.sql  # Idempotent seed data for PEAS agents
```

**Key Design Decisions:**
- **Read-only module** — prompt management (CRUD) is in the admin module
- **Protocol-based repository** — domain logic depends on protocol, not SQL implementation
- **Scope fallback** — org-scoped → global → None resolution chain
- **SUPER_ORG_ID = 1** — organization_id=1 with scope='public' marks global templates
- **Deterministic evaluation** — evaluation template uses temperature=0.0, top_p=1.0
