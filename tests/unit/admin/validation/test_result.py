"""
Unit tests for ValidationResult and ValidationErrorDetail.

Pure domain logic — no mocks, no DB.
"""

import pytest

from app.admin.validation.result import ValidationErrorDetail, ValidationResult


# ─────────────────────────────────────────────────────────────────
# ValidationErrorDetail
# ─────────────────────────────────────────────────────────────────


class TestValidationErrorDetail:
    def test_construction(self):
        err = ValidationErrorDetail(
            field="template_structure.sections",
            message="sections must be non-empty",
            code="EMPTY_SECTIONS",
        )
        assert err.field == "template_structure.sections"
        assert err.message == "sections must be non-empty"
        assert err.code == "EMPTY_SECTIONS"

    def test_is_frozen(self):
        err = ValidationErrorDetail(field="f", message="m", code="c")
        with pytest.raises(AttributeError):
            err.field = "other"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────
# ValidationResult — factory methods
# ─────────────────────────────────────────────────────────────────


class TestValidationResultFactories:
    def test_success(self):
        r = ValidationResult.success()
        assert r.is_valid is True
        assert len(r.errors) == 0

    def test_failure_non_empty(self):
        errs = [
            ValidationErrorDetail(field="a", message="bad a", code="E1"),
            ValidationErrorDetail(field="b", message="bad b", code="E2"),
        ]
        r = ValidationResult.failure(errs)
        assert r.is_valid is False
        assert len(r.errors) == 2
        assert r.errors[0].field == "a"
        assert r.errors[1].field == "b"

    def test_failure_empty_list_returns_success(self):
        r = ValidationResult.failure([])
        assert r.is_valid is True
        assert len(r.errors) == 0

    def test_from_single(self):
        r = ValidationResult.from_single("f", "msg", "CODE")
        assert r.is_valid is False
        assert len(r.errors) == 1
        assert r.errors[0].field == "f"
        assert r.errors[0].message == "msg"
        assert r.errors[0].code == "CODE"


# ─────────────────────────────────────────────────────────────────
# ValidationResult — merge
# ─────────────────────────────────────────────────────────────────


class TestValidationResultMerge:
    def test_merge_two_successes(self):
        r = ValidationResult.success().merge(ValidationResult.success())
        assert r.is_valid is True

    def test_merge_success_and_failure(self):
        ok = ValidationResult.success()
        fail = ValidationResult.from_single("f", "m", "c")
        merged = ok.merge(fail)
        assert merged.is_valid is False
        assert len(merged.errors) == 1

    def test_merge_two_failures(self):
        f1 = ValidationResult.from_single("a", "m1", "c1")
        f2 = ValidationResult.from_single("b", "m2", "c2")
        merged = f1.merge(f2)
        assert merged.is_valid is False
        assert len(merged.errors) == 2

    def test_merge_all_empty(self):
        r = ValidationResult.merge_all()
        assert r.is_valid is True

    def test_merge_all_mixed(self):
        ok = ValidationResult.success()
        f1 = ValidationResult.from_single("x", "m", "c")
        f2 = ValidationResult.failure([
            ValidationErrorDetail(field="y", message="m2", code="c2"),
            ValidationErrorDetail(field="z", message="m3", code="c3"),
        ])
        merged = ValidationResult.merge_all(ok, f1, f2)
        assert merged.is_valid is False
        assert len(merged.errors) == 3

    def test_errors_are_tuple(self):
        """Errors collection is immutable (tuple, not list)."""
        r = ValidationResult.from_single("f", "m", "c")
        assert isinstance(r.errors, tuple)

    def test_is_frozen(self):
        r = ValidationResult.success()
        with pytest.raises(AttributeError):
            r.is_valid = False  # type: ignore[misc]
