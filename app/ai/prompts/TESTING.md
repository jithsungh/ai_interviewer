# AI Prompts Layer Testing Guide

## Testing Philosophy

Prompt layer testing focuses on:

1. **Scope resolution logic** (org → global fallback)
2. **Variable substitution accuracy**
3. **Template syntax validation**
4. **Version management**

Most tests use **real database** since prompt retrieval is core functionality.

---

## Test Structure

```
tests/
├── unit/
│   └── ai/
│       └── prompts/
│           ├── test_template_parser.py
│           ├── test_variable_substitution.py
│           └── test_rendering.py
├── integration/
│   └── ai/
│       └── prompts/
│           ├── test_prompt_repository.py
│           ├── test_scope_resolution.py
│           └── test_versioning.py
└── e2e/
    └── ai/
        └── prompts/
            └── test_prompt_workflow.py
```

---

## 1. Unit Tests (Template Logic)

### Template Parser Tests

```python
# tests/unit/ai/prompts/test_template_parser.py

from app.ai.prompts.parser import TemplateParser
from app.ai.prompts.errors import TemplateSyntaxError, VariableMissingError

def test_extract_variables():
    \"\"\"Parser extracts all variables from template\"\"\"
    template = "Hello {{name}}, your score is {{score}}"
    parser = TemplateParser(template)

    variables = parser.extract_variables()
    assert set(variables) == {"name", "score"}

def test_invalid_syntax_raises_error():
    \"\"\"Unclosed braces raise syntax error\"\"\"
    template = "Hello {{name"

    with pytest.raises(TemplateSyntaxError) as exc:
        parser = TemplateParser(template)
        parser.validate()

    assert "unclosed" in str(exc.value).lower()

def test_nested_variables_not_supported():
    \"\"\"Nested variables like {{user_{{type}}}} rejected\"\"\"
    template = "User: {{user_{{type}}}}"

    with pytest.raises(TemplateSyntaxError):
        parser = TemplateParser(template)
        parser.validate()

def test_escaped_braces():
    \"\"\"Escaped braces treated as literals\"\"\"
    template = "Use \\\\{{variable\\\\}} syntax"
    parser = TemplateParser(template)

    variables = parser.extract_variables()
    assert len(variables) == 0  # No actual variables

def test_variable_with_whitespace():
    \"\"\"Variables with surrounding whitespace normalized\"\"\"
    template = "{{ name }} and {{  score  }}"
    parser = TemplateParser(template)

    variables = parser.extract_variables()
    assert set(variables) == {"name", "score"}
```

### Variable Substitution Tests

```python
# tests/unit/ai/prompts/test_variable_substitution.py

from app.ai.prompts.renderer import PromptRenderer

def test_simple_substitution():
    \"\"\"Basic variable substitution works\"\"\"
    template = "Hello {{name}}, you scored {{score}}"
    renderer = PromptRenderer(template)

    result = renderer.render(name="Alice", score=95)
    assert result == "Hello Alice, you scored 95"

def test_missing_variable_raises_error():
    \"\"\"Missing required variable raises error\"\"\"
    template = "Hello {{name}}"
    renderer = PromptRenderer(template)

    with pytest.raises(VariableMissingError) as exc:
        renderer.render()  # name not provided

    assert "name" in str(exc.value)

def test_extra_variables_ignored():
    \"\"\"Extra variables don't break rendering\"\"\"
    template = "Hello {{name}}"
    renderer = PromptRenderer(template)

    result = renderer.render(name="Alice", extra="ignored")
    assert result == "Hello Alice"

def test_none_value_converts_to_empty():
    \"\"\"None values converted to empty string with warning\"\"\"
    template = "Value: {{value}}"
    renderer = PromptRenderer(template)

    result = renderer.render(value=None)
    assert result == "Value: "

def test_list_value_converts_to_json():
    \"\"\"List/dict values serialized as JSON\"\"\"
    template = "Skills: {{skills}}"
    renderer = PromptRenderer(template)

    result = renderer.render(skills=["Python", "SQL"])
    assert "Python" in result
    assert "SQL" in result

def test_large_variable_truncated():
    \"\"\"Very large variables truncated with warning\"\"\"
    template = "Content: {{large_text}}"
    renderer = PromptRenderer(template, max_variable_size=100)

    large_text = "x" * 10000
    result = renderer.render(large_text=large_text)

    assert len(result) < 200  # Truncated
    assert "..." in result or "[truncated]" in result
```

### Rendering Tests

```python
# tests/unit/ai/prompts/test_rendering.py

from app.ai.prompts.renderer import PromptRenderer

def test_system_and_user_prompt_separation():
    \"\"\"System and user prompts rendered separately\"\"\"
    from app.ai.prompts.models import PromptTemplate

    template = PromptTemplate(
        id=1,
        prompt_type="test",
        organization_id=None,
        version=1,
        content="User prompt: {{input}}",
        system_prompt="You are a helpful assistant",
        is_active=True
    )

    rendered = render_prompt_template(template, variables={"input": "test"})

    assert rendered.text == "User prompt: test"
    assert rendered.system_prompt == "You are a helpful assistant"

def test_suggested_model_passed_through():
    \"\"\"Model ID from template included in output\"\"\"
    template = PromptTemplate(
        id=1,
        prompt_type="test",
        organization_id=None,
        version=1,
        content="Test",
        model_id="gpt-4",
        temperature=0.7,
        max_tokens=500,
        is_active=True
    )

    rendered = render_prompt_template(template, variables={})

    assert rendered.model_id == "gpt-4"
    assert rendered.temperature == 0.7
    assert rendered.max_tokens == 500
```

---

## 2. Integration Tests (Database Access)

### Prompt Repository Tests

```python
# tests/integration/ai/prompts/test_prompt_repository.py

import pytest
from app.ai.prompts.repository import PromptRepository
from app.ai.prompts.errors import PromptNotFoundError

@pytest.fixture
def db_with_prompts(db_session):
    \"\"\"Seed database with test prompts\"\"\"
    from app.persistence.models import PromptTemplate

    # Global prompt
    global_prompt = PromptTemplate(
        prompt_type="test_type",
        organization_id=None,
        version=1,
        is_active=True,
        content="Global: {{input}}"
    )
    db_session.add(global_prompt)

    # Organization-scoped prompt
    org_prompt = PromptTemplate(
        prompt_type="test_type",
        organization_id=45,
        version=1,
        is_active=True,
        content="Org 45: {{input}}"
    )
    db_session.add(org_prompt)

    db_session.commit()
    return db_session

def test_retrieve_global_prompt(db_with_prompts):
    \"\"\"Retrieve active global prompt\"\"\"
    repo = PromptRepository(db_with_prompts)
    prompt = repo.get_active_prompt(prompt_type="test_type")

    assert prompt is not None
    assert prompt.content.startswith("Global:")
    assert prompt.organization_id is None

def test_retrieve_org_scoped_prompt(db_with_prompts):
    \"\"\"Retrieve active org-scoped prompt\"\"\"
    repo = PromptRepository(db_with_prompts)
    prompt = repo.get_active_prompt(
        prompt_type="test_type",
        organization_id=45
    )

    assert prompt is not None
    assert prompt.content.startswith("Org 45:")
    assert prompt.organization_id == 45

def test_nonexistent_prompt_raises_error(db_with_prompts):
    \"\"\"Requesting nonexistent prompt raises error\"\"\"
    repo = PromptRepository(db_with_prompts)

    with pytest.raises(PromptNotFoundError):
        repo.get_active_prompt(prompt_type="nonexistent_type")
```

### Scope Resolution Tests

```python
# tests/integration/ai/prompts/test_scope_resolution.py

def test_org_prompt_preferred_over_global(db_session):
    \"\"\"Organization prompt takes precedence\"\"\"
    # Create both global and org prompts
    global_prompt = PromptTemplate(
        prompt_type="eval",
        organization_id=None,
        version=1,
        is_active=True,
        content="Global eval"
    )
    org_prompt = PromptTemplate(
        prompt_type="eval",
        organization_id=45,
        version=1,
        is_active=True,
        content="Org 45 eval"
    )
    db_session.add_all([global_prompt, org_prompt])
    db_session.commit()

    repo = PromptRepository(db_session)
    prompt = repo.get_active_prompt(prompt_type="eval", organization_id=45)

    assert prompt.content == "Org 45 eval"
    assert prompt.organization_id == 45

def test_fallback_to_global_when_org_missing(db_session):
    \"\"\"Fallback to global if org-scoped not found\"\"\"
    global_prompt = PromptTemplate(
        prompt_type="eval",
        organization_id=None,
        version=1,
        is_active=True,
        content="Global eval"
    )
    db_session.add(global_prompt)
    db_session.commit()

    repo = PromptRepository(db_session)
    prompt = repo.get_active_prompt(
        prompt_type="eval",
        organization_id=99,  # No org-scoped prompt
        fallback_to_global=True
    )

    assert prompt.content == "Global eval"
    assert prompt.organization_id is None

def test_no_fallback_raises_error(db_session):
    \"\"\"Without fallback, missing org prompt raises error\"\"\"
    global_prompt = PromptTemplate(
        prompt_type="eval",
        organization_id=None,
        version=1,
        is_active=True,
        content="Global eval"
    )
    db_session.add(global_prompt)
    db_session.commit()

    repo = PromptRepository(db_session)

    with pytest.raises(PromptNotFoundError):
        repo.get_active_prompt(
            prompt_type="eval",
            organization_id=99,
            fallback_to_global=False
        )
```

### Versioning Tests

```python
# tests/integration/ai/prompts/test_versioning.py

def test_only_active_version_returned(db_session):
    \"\"\"Only active version retrieved, not older versions\"\"\"
    # Create multiple versions, only one active
    v1 = PromptTemplate(
        prompt_type="test",
        organization_id=None,
        version=1,
        is_active=False,
        content="Version 1"
    )
    v2 = PromptTemplate(
        prompt_type="test",
        organization_id=None,
        version=2,
        is_active=True,
        content="Version 2"
    )
    db_session.add_all([v1, v2])
    db_session.commit()

    repo = PromptRepository(db_session)
    prompt = repo.get_active_prompt(prompt_type="test")

    assert prompt.version == 2
    assert prompt.content == "Version 2"

def test_unique_active_constraint(db_session):
    \"\"\"Database enforces unique active version\"\"\"
    v1 = PromptTemplate(
        prompt_type="test",
        organization_id=None,
        version=1,
        is_active=True,
        content="V1"
    )
    v2 = PromptTemplate(
        prompt_type="test",
        organization_id=None,
        version=2,
        is_active=True,  # Should violate unique constraint
        content="V2"
    )

    db_session.add(v1)
    db_session.commit()

    db_session.add(v2)

    with pytest.raises(IntegrityError):
        db_session.commit()
```

---

## 3. E2E Tests (Full Workflow)

```python
# tests/e2e/ai/prompts/test_prompt_workflow.py

@pytest.mark.e2e
def test_full_prompt_retrieval_and_rendering(db_session):
    \"\"\"Complete workflow: retrieve + render\"\"\"
    # Setup: Create prompt in DB
    prompt_model = PromptTemplate(
        prompt_type="evaluation",
        organization_id=45,
        version=2,
        is_active=True,
        content="Evaluate: {{question}}\\n\\nResponse: {{answer}}",
        system_prompt="You are an evaluator",
        model_id="gpt-4",
        temperature=0.0
    )
    db_session.add(prompt_model)
    db_session.commit()

    # Step 1: Retrieve prompt
    from app.ai.prompts import get_prompt
    prompt = get_prompt(
        prompt_type="evaluation",
        organization_id=45
    )

    assert prompt.version == 2
    assert prompt.model_id == "gpt-4"

    # Step 2: Render with variables
    from app.ai.prompts import render_prompt
    rendered = render_prompt(
        prompt,
        variables={
            "question": "What is Python?",
            "answer": "A programming language"
        }
    )

    assert "What is Python?" in rendered.text
    assert "A programming language" in rendered.text
    assert rendered.system_prompt == "You are an evaluator"
    assert rendered.model_id == "gpt-4"
    assert rendered.temperature == 0.0
    assert rendered.version == 2
```

---

## 4. Edge Case Tests

```python
# tests/unit/ai/prompts/test_edge_cases.py

def test_empty_template():
    \"\"\"Empty template is valid (no variables)\"\"\"
    template = ""
    renderer = PromptRenderer(template)
    result = renderer.render()
    assert result == ""

def test_template_with_only_whitespace():
    \"\"\"Whitespace-only template preserved\"\"\"
    template = "   \\n\\n   "
    renderer = PromptRenderer(template)
    result = renderer.render()
    assert result == "   \\n\\n   "

def test_unicode_variables():
    \"\"\"Unicode in variables handled correctly\"\"\"
    template = "Name: {{name}}"
    renderer = PromptRenderer(template)
    result = renderer.render(name="François \\u00e9\\u00e8\\u00ea")
    assert "François" in result

def test_very_long_template():
    \"\"\"Large templates (100KB+) render correctly\"\"\"
    template = "Start {{var}} " + ("x" * 100000) + " End"
    renderer = PromptRenderer(template)
    result = renderer.render(var="TEST")
    assert "Start TEST" in result
    assert len(result) > 100000

def test_multiple_same_variable():
    \"\"\"Same variable appears multiple times\"\"\"
    template = "{{name}} said {{name}} again"
    renderer = PromptRenderer(template)
    result = renderer.render(name="Alice")
    assert result == "Alice said Alice again"
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% coverage
- **Integration Tests:** All scope resolution paths
- **E2E Tests:** Full retrieval + rendering workflow
- **Edge Cases:** All template syntax edge cases

---

## Running Tests

```bash
# Unit tests (template logic)
pytest tests/unit/ai/prompts/ -v

# Integration tests (database)
pytest tests/integration/ai/prompts/ -v --db

# E2E tests
pytest tests/e2e/ai/prompts/ -v --e2e

# Coverage
pytest tests/ai/prompts/ --cov=app/ai/prompts --cov-report=html
```

---

**End of AI Prompts Testing Guide**
