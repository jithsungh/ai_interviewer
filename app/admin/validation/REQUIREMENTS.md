# Admin Validation Layer Requirements

## 1. Purpose

The validation layer provides **structural and cross-entity validation**:

- Template structure schema validation (JSON schema)
- Rubric dimension consistency checks
- Cross-reference validation (rubric exists, role exists)
- Pre-activation validation workflows

**Responsibilities:** Validation logic that requires database lookups or complex rules
**Not Responsible For:** Simple type/format checks (handled by Pydantic), business logic

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
