# Admin Validation Layer Requirements

## 1. Purpose

The validation layer provides **structural and cross-entity validation** for all admin content types:

- Template structure schema validation (JSON schema)
- Rubric dimension consistency checks
- Cross-reference validation (rubric exists, role exists, etc.)
- Pre-activation validation workflows
- **Override field validation (ensures override fields are valid subsets of base content)**
- **RBAC validation support (validates user has permission to perform operation)**

**Responsibilities:** Validation logic that requires database lookups or complex rules, override integrity checks
**Not Responsible For:** Simple type/format checks (handled by Pydantic), business logic, authorization enforcement

---

## 2. Owned Tables

**None** - Validation layer is read-only, queries via persistence layer

---

## 3. Input Constraints

### From Domain Layer

- Entity to validate (Template, Rubric, Window)
- Organization context for scope resolution

### Validation Rules

- Template structure must match expected JSON schema
- Rubric dimensions must have valid criteria JSONB
- Window mappings must reference existing active roles/templates
- **Override Validation:**
  - Override fields must be valid subset of base content schema
  - Cannot override immutable fields (id, organization_id, scope, created_at)
  - Base content must exist and be owned by super org (org_id=1)
  - Override must not break structural integrity of base content
- **Cross-content validation:**
  - Questions must reference valid topics
  - Coding problems must reference valid coding topics
  - Templates must reference valid rubrics and roles

---

## 4. Output Guarantees

### Return Types

- Success: `ValidationResult(is_valid=True)`
- Failure: `ValidationResult(is_valid=False, errors=[...])`

### Error Format

```python
ValidationError(
    field="template_structure.sections[0].rubric_id",
    message="Referenced rubric ID 999 not found",
    code="INVALID_REFERENCE"
)

# Override-specific errors
ValidationError(
    field="override_fields.id",
    message="Cannot override immutable field 'id'",
    code="IMMUTABLE_FIELD_OVERRIDE"
)

ValidationError(
    field="base_template_id",
    message="Base template must be owned by super org (org_id=1)",
    code="INVALID_BASE_CONTENT"
)
```

---

## 5. Invariants

### Validation is Read-Only

- Validation SHALL NOT modify entities
- Validation SHALL NOT have side effects

### Comprehensive Error Reporting

- All validation errors collected and returned together (not fail-fast)

---

## 6. Forbidden Behaviors

- SHALL NOT perform mutations during validation
- SHALL NOT validate already-persisted entities (validation is pre-save)
- SHALL NOT raise exceptions (return ValidationResult)

---

## 7. Dependent Modules

### Dependencies

- `admin/persistence` - Query existing entities for cross-reference checks
- JSON Schema library for template structure validation

### Dependents

- `admin/domain` - Calls validators before save/activate

---

## 8. Event Contracts Emitted

**None** - Validation is passive

---

## 9. Acceptance Criteria

- [ ] Valid native template passes all checks
- [ ] Valid override passes all checks
- [ ] Invalid template structure fails with detailed errors
- [ ] Attempting to override non-super-org template fails
- [ ] Attempting to override protected fields (id, org_id, scope) fails
- [ ] Override with invalid field names fails
- [ ] Non-existent rubric reference detected
- [ ] Dimension weight sum != 1.0 detected

---

## 10. Testing Guide

### Unit Tests (Mocked Repository Queries)

```python
def test_template_structure_validation():
    """Valid JSON schema passes"""
    result = TemplateValidator.validate_structure(VALID_TEMPLATE)
    assert result.is_valid

def test_invalid_rubric_reference():
    """Non-existent rubric ID fails validation"""
    # Mock repository to return None for rubric lookup
    result = TemplateValidator.validate(template)
    assert not result.is_valid
    assert "rubric ID 999 not found" in result.errors

def test_override_immutable_field_validation():
    """Cannot override immutable fields"""
    override_fields = {"id": 999, "organization_id": 2, "name": "Modified"}
    result = OverrideValidator.validate_fields(override_fields, "template")
    assert not result.is_valid
    assert "Cannot override immutable field 'id'" in result.errors

def test_override_base_content_ownership():
    """Base content must be super org owned"""
    # Mock repository to return template with org_id=2
    result = OverrideValidator.validate_base(base_template_id=123)
    assert not result.is_valid
    assert "must be owned by super org" in result.errors

def test_question_override_validation():
    """Question override with valid fields passes"""
    override_fields = {"text": "Modified question?", "difficulty": "hard"}
    result = OverrideValidator.validate_fields(override_fields, "question")
    assert result.is_valid

def test_coding_problem_override_validation():
    """Coding problem override maintains structure"""
    override_fields = {
        "title": "Modified Title",
        "description": "New description"
    }
    result = OverrideValidator.validate_fields(override_fields, "coding_problem")
    assert result.is_valid
```

---

## 11. Edge Cases

- Template references 50 rubrics → Validate all exist
- Circular topic references → Detect cycle
- Very deep JSON structure → Handle recursion

---

## 12. Concurrency Concerns

- Read-only operations are safe for concurrent execution
- No locking required
