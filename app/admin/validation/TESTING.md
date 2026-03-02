# Admin Validation Layer Testing Guide

## Unit Tests (Mocked Dependencies)

```python
# tests/unit/admin/validation/test_template_validator.py

def test_valid_template_structure():
    """Template with valid JSON schema passes"""
    validator = TemplateValidator()
    result = validator.validate_structure(VALID_TEMPLATE)
    assert result.is_valid
    assert len(result.errors) == 0

def test_missing_required_field():
    """Template missing 'sections' field fails"""
    template = {"name": "Test", "description": "..."}
    result = validator.validate_structure(template)
    assert not result.is_valid
    assert any("sections" in err.field for err in result.errors)

def test_invalid_rubric_reference():
    """Reference to non-existent rubric fails"""
    # Mock repository
    with patch('admin.persistence.RubricRepository.get_by_id', return_value=None):
        result = validator.validate_cross_references(template)
        assert not result.is_valid

def test_rubric_weight_sum_not_one():
    """Dimensions with weights summing to 0.95 fail"""
    rubric = {
        "dimensions": [
            {"weight": 0.5},
            {"weight": 0.45}
        ]
    }
    result = RubricValidator.validate_dimension_weights(rubric)
    assert not result.is_valid
    assert "sum to 1.0" in result.errors[0].message
```

---

## Integration Tests (Real Database)

```python
# tests/integration/admin/validation/test_template_validator_integration.py

def test_validate_template_with_real_rubric_lookup(db_session):
    """Validation queries actual rubric from database"""
    # Create rubric in db
    rubric = create_rubric(db_session)

    # Create template referencing rubric
    template = {"rubric_ids": [rubric.id]}

    # Validate
    result = TemplateValidator(db_session).validate(template)
    assert result.is_valid
```

---

## Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(st.floats(min_value=0, max_value=1))
def test_dimension_weight_sum_tolerance(weight1):
    """Test weight sum validation with various inputs"""
    weight2 = 1.0 - weight1
    rubric = {"dimensions": [{"weight": weight1}, {"weight": weight2}]}
    result = RubricValidator.validate_dimension_weights(rubric)
    assert result.is_valid  # Should pass for any valid split
```

---

## Performance Tests

```python
def test_validate_template_with_many_rubrics():
    """Validation of template referencing 50 rubrics completes quickly"""
    template = {"rubric_ids": list(range(1, 51))}
    start = time.perf_counter()
    result = validator.validate(template)
    duration = time.perf_counter() - start
    assert duration < 0.5  # Should complete in <500ms
```

---

## Coverage Target

- ≥95% branch coverage
- All validation rules must have positive and negative test cases
