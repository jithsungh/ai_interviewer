# Human Testing Guide — `admin/validation`

## Module Overview

The `admin/validation` module provides **non-fail-fast** validators that
collect **all** errors before returning. It has no HTTP endpoints — it is
called programmatically by `admin/domain/services.py` and can be exercised
via the automated test suite or the REPL snippets below.

---

## 1. Run the Automated Tests

```bash
# Unit tests (123 tests, ~1 s)
TESTING=1 .venv/bin/python -m pytest tests/unit/admin/validation/ -v

# Integration tests (13 tests, ~0.5 s)
TESTING=1 .venv/bin/python -m pytest tests/integration/admin/validation/ -v

# All validation tests at once
TESTING=1 .venv/bin/python -m pytest tests/unit/admin/validation/ tests/integration/admin/validation/ -v
```

Expected: **136 passed**, 0 failed.

---

## 2. Smoke Test via Python REPL

```bash
TESTING=1 .venv/bin/python
```

### 2a. Template Structure Validation

```python
from app.admin.validation import TemplateStructureValidator
import json, pathlib

# (a) Validate the canonical sample template — should pass
sample = json.loads(pathlib.Path("docs/sample_i_template.json").read_text())
r = TemplateStructureValidator.validate(sample)
assert r.is_valid, r.errors

# (b) Deliberately break it
sample["coding_round"]["difficulty"] = "impossible"
r = TemplateStructureValidator.validate(sample)
print(r.is_valid)   # → False
for e in r.errors:
    print(f"  [{e.code}] {e.field}: {e.message}")
```

### 2b. Rubric Dimension Validation

```python
from decimal import Decimal
from app.admin.domain.entities import RubricDimension
from app.admin.validation import RubricValidator

dims = [
    RubricDimension(id=None, rubric_id=1, dimension_name="D1",
                    description=None, max_score=Decimal("10"),
                    weight=Decimal("0.7"), sequence_order=1),
    RubricDimension(id=None, rubric_id=1, dimension_name="D2",
                    description=None, max_score=Decimal("10"),
                    weight=Decimal("0.3"), sequence_order=2),
]
r = RubricValidator.validate_dimensions(dims)
assert r.is_valid

# Break it: weights sum to 0.5
dims[1] = dims[1].__class__(
    id=None, rubric_id=1, dimension_name="D2", description=None,
    max_score=Decimal("10"), weight=Decimal("-0.2"), sequence_order=2,
)
r = RubricValidator.validate_dimensions(dims)
print(r.is_valid, [(e.code, e.message) for e in r.errors])
```

### 2c. Override Validation

```python
from app.admin.validation import OverrideValidator
from app.admin.domain.entities import ContentType

# Valid
r = OverrideValidator.validate_full(
    {"name": "Custom"}, ContentType.TEMPLATE, base_content_org_id=1,
)
assert r.is_valid

# Immutable field + wrong org
r = OverrideValidator.validate_full(
    {"id": 99, "name": "Custom"}, ContentType.TEMPLATE, base_content_org_id=42,
)
print(r.is_valid)  # → False
for e in r.errors:
    print(f"  [{e.code}] {e.field}: {e.message}")
```

---

## 3. What to Look For

| Check | Expected |
|-------|----------|
| `ValidationResult.is_valid` is `True` for valid input | Green path |
| `ValidationResult.is_valid` is `False` for invalid input | Red path |
| `ValidationResult.errors` is a **tuple** (immutable) | Frozen result |
| Multiple errors collected (not fail-fast) | All issues surfaced |
| `ValidationErrorDetail` has `field`, `message`, `code` | Structured Errors |
| `merge_all()` combines results from different validators | Cross-module |

---

## 4. Edge Cases Worth Exercising Manually

1. **Empty template_structure** — `TemplateStructureValidator.validate({})`
   → `NO_SECTIONS` error.
2. **All sections disabled** — every section has `"enabled": false`
   → `NO_ENABLED_SECTIONS` error.
3. **Rubric weights off by tolerance boundary** — weights sum to 1.0005
   (within 0.001 tolerance) should pass; 1.002 should fail.
4. **Override with only immutable fields** — `{"id": 1, "scope": "public"}`
   → `IMMUTABLE_FIELD_OVERRIDE` errors, no `EMPTY_OVERRIDE`.
5. **Cross-reference with None repos** — validators gracefully skip checks
   when a repository is not provided.

---

## 5. Module Files

| File | Purpose |
|------|---------|
| `result.py` | `ValidationResult`, `ValidationErrorDetail` frozen dataclasses |
| `template_validator.py` | JSONB template_structure validation |
| `rubric_validator.py` | Rubric dimension weight/uniqueness checks |
| `override_validator.py` | Tenant override field & ownership checks |
| `cross_reference_validator.py` | Cross-entity existence lookups |
| `pre_activation_validator.py` | Composite pre-activation readiness check |
| `__init__.py` | Public re-exports |
