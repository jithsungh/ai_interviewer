"""
Unit tests for OverrideValidator.

Tests field validation per content-type, immutable-field rejection,
base-content ownership, and the full composite check.
Pure domain logic — no DB, no mocks.
"""

import pytest

from app.admin.domain.entities import (
    ContentType,
    IMMUTABLE_OVERRIDE_FIELDS,
    SUPER_ORG_ID,
)
from app.admin.validation.override_validator import OverrideValidator


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

_TEMPLATE_GOOD = {"name": "Updated Name", "description": "New desc"}
_RUBRIC_GOOD = {"name": "R2", "schema": {"v": 2}}
_ROLE_GOOD = {"name": "Backend Developer"}
_TOPIC_GOOD = {"name": "Data Structures", "description": "DS"}
_QUESTION_GOOD = {"question_text": "What is X?", "difficulty": "medium"}
_CODING_GOOD = {"title": "FizzBuzz", "difficulty": "easy"}


# ─────────────────────────────────────────────────────────────────
# Valid overrides
# ─────────────────────────────────────────────────────────────────


class TestValidOverrides:
    def test_template_override(self):
        result = OverrideValidator.validate_fields(_TEMPLATE_GOOD, ContentType.TEMPLATE)
        assert result.is_valid, [e.message for e in result.errors]

    def test_rubric_override(self):
        result = OverrideValidator.validate_fields(_RUBRIC_GOOD, ContentType.RUBRIC)
        assert result.is_valid

    def test_role_override(self):
        result = OverrideValidator.validate_fields(_ROLE_GOOD, ContentType.ROLE)
        assert result.is_valid

    def test_topic_override(self):
        result = OverrideValidator.validate_fields(_TOPIC_GOOD, ContentType.TOPIC)
        assert result.is_valid

    def test_question_override(self):
        result = OverrideValidator.validate_fields(_QUESTION_GOOD, ContentType.QUESTION)
        assert result.is_valid

    def test_coding_problem_override(self):
        result = OverrideValidator.validate_fields(_CODING_GOOD, ContentType.CODING_PROBLEM)
        assert result.is_valid

    def test_string_content_type_accepted(self):
        result = OverrideValidator.validate_fields(_TEMPLATE_GOOD, "template")
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Empty override
# ─────────────────────────────────────────────────────────────────


class TestEmptyOverride:
    def test_empty_dict(self):
        result = OverrideValidator.validate_fields({}, ContentType.TEMPLATE)
        assert not result.is_valid
        assert result.errors[0].code == "EMPTY_OVERRIDE"


# ─────────────────────────────────────────────────────────────────
# Immutable field rejection
# ─────────────────────────────────────────────────────────────────


class TestImmutableFieldRejection:
    @pytest.mark.parametrize("field", sorted(IMMUTABLE_OVERRIDE_FIELDS))
    def test_immutable_field_rejected(self, field: str):
        payload = {"name": "ok", field: "forbidden"}
        result = OverrideValidator.validate_fields(payload, ContentType.TEMPLATE)
        assert not result.is_valid
        assert any(e.code == "IMMUTABLE_FIELD_OVERRIDE" for e in result.errors)

    def test_multiple_immutable_fields(self):
        payload = {"id": 99, "scope": "global", "name": "ok"}
        result = OverrideValidator.validate_fields(payload, ContentType.TEMPLATE)
        assert not result.is_valid
        immutable_errors = [e for e in result.errors if e.code == "IMMUTABLE_FIELD_OVERRIDE"]
        assert len(immutable_errors) == 2


# ─────────────────────────────────────────────────────────────────
# Unknown fields
# ─────────────────────────────────────────────────────────────────


class TestUnknownFields:
    def test_unknown_template_field(self):
        payload = {"name": "ok", "totally_made_up": "nope"}
        result = OverrideValidator.validate_fields(payload, ContentType.TEMPLATE)
        assert not result.is_valid
        assert any(e.code == "UNKNOWN_OVERRIDE_FIELD" for e in result.errors)

    def test_unknown_content_type(self):
        payload = {"name": "ok"}
        result = OverrideValidator.validate_fields(payload, "nonexistent_type")
        assert not result.is_valid
        assert any(e.code == "UNKNOWN_CONTENT_TYPE" for e in result.errors)

    def test_role_cannot_override_template_fields(self):
        """template_structure is valid only for ContentType.TEMPLATE."""
        payload = {"template_structure": {}}
        result = OverrideValidator.validate_fields(payload, ContentType.ROLE)
        assert not result.is_valid
        assert any(e.code == "UNKNOWN_OVERRIDE_FIELD" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Base content ownership
# ─────────────────────────────────────────────────────────────────


class TestBaseContentOwnership:
    def test_super_org_owned(self):
        result = OverrideValidator.validate_base_content_ownership(SUPER_ORG_ID)
        assert result.is_valid

    def test_null_org_accepted(self):
        """Global content (org_id=NULL) is managed by super org."""
        result = OverrideValidator.validate_base_content_ownership(None)
        assert result.is_valid

    def test_tenant_org_rejected(self):
        result = OverrideValidator.validate_base_content_ownership(42)
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_BASE_CONTENT"


# ─────────────────────────────────────────────────────────────────
# validate_full composite
# ─────────────────────────────────────────────────────────────────


class TestValidateFull:
    def test_all_valid(self):
        result = OverrideValidator.validate_full(
            _TEMPLATE_GOOD, ContentType.TEMPLATE, SUPER_ORG_ID,
        )
        assert result.is_valid

    def test_bad_fields_and_bad_owner(self):
        """Collects errors from both sub-validators."""
        result = OverrideValidator.validate_full(
            {"id": 1, "unknown_field": "x"},
            ContentType.TEMPLATE,
            42,
        )
        assert not result.is_valid
        codes = {e.code for e in result.errors}
        assert "IMMUTABLE_FIELD_OVERRIDE" in codes
        assert "UNKNOWN_OVERRIDE_FIELD" in codes
        assert "INVALID_BASE_CONTENT" in codes
