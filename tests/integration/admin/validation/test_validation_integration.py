"""
Integration tests for admin/validation.

Tests the full validation stack against:
  • Real sample template JSON from ``docs/``
  • Real entity dataclasses from ``admin/domain``
  • Cross-module wiring (validators ↔ shared errors ↔ entities)

No database required — these validate that the module integrates
correctly with the rest of the codebase at the Python import level
and with realistic production-like data.
"""

import json
import pathlib
from decimal import Decimal
from typing import List

import pytest

from app.admin.domain.entities import (
    ContentType,
    IMMUTABLE_OVERRIDE_FIELDS,
    Role,
    Rubric,
    RubricDimension,
    SUPER_ORG_ID,
    Template,
    TemplateRubric,
    TemplateScope,
)
from app.admin.validation import (
    CrossReferenceValidator,
    OverrideValidator,
    PreActivationValidator,
    RubricValidator,
    TemplateStructureValidator,
    ValidationErrorDetail,
    ValidationResult,
)

_DOCS = pathlib.Path(__file__).resolve().parents[4] / "docs"


# ─────────────────────────────────────────────────────────────────
# Integration: real template JSON from docs/
# ─────────────────────────────────────────────────────────────────


class TestSampleTemplateValidation:
    """Validate the canonical sample_i_template.json passes validation."""

    @pytest.fixture()
    def sample_structure(self) -> dict:
        return json.loads((_DOCS / "sample_i_template.json").read_text())

    def test_sample_template_valid(self, sample_structure):
        result = TemplateStructureValidator.validate(sample_structure)
        assert result.is_valid, [e.message for e in result.errors]


class TestComprehensiveTemplateValidation:
    """Validate the comprehensive template JSON (v2 style with sections dict)."""

    @pytest.fixture()
    def comprehensive_structure(self) -> dict:
        return json.loads((_DOCS / "comprehensive_interview_template.json").read_text())

    def test_comprehensive_template_valid(self, comprehensive_structure):
        result = TemplateStructureValidator.validate(comprehensive_structure)
        # This template uses the v2 "sections" dict format
        assert result.is_valid, [e.message for e in result.errors]


# ─────────────────────────────────────────────────────────────────
# Integration: full override pipeline with real entities
# ─────────────────────────────────────────────────────────────────


class TestOverridePipelineIntegration:
    """
    End-to-end override validation using real ContentType enum values
    and the IMMUTABLE_OVERRIDE_FIELDS constant from entities.
    """

    @pytest.mark.parametrize("content_type", list(ContentType))
    def test_immutable_fields_rejected_for_every_content_type(self, content_type):
        """No content type should allow overriding immutable fields."""
        for field in IMMUTABLE_OVERRIDE_FIELDS:
            result = OverrideValidator.validate_fields(
                {field: "bad", "name": "x"}, content_type,
            )
            assert not result.is_valid, f"{field} not rejected for {content_type}"
            assert any(e.code == "IMMUTABLE_FIELD_OVERRIDE" for e in result.errors)

    def test_full_override_flow(self):
        """Happy path: valid fields + super-org ownership."""
        result = OverrideValidator.validate_full(
            override_fields={"name": "Tenant Name", "description": "Custom"},
            content_type=ContentType.TEMPLATE,
            base_content_org_id=SUPER_ORG_ID,
        )
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Integration: rubric dimension validation with real entities
# ─────────────────────────────────────────────────────────────────


class TestRubricIntegration:
    """Validate rubric dimensions using real RubricDimension entities."""

    def test_realistic_rubric_dimensions(self):
        dims = [
            RubricDimension(
                id=1, rubric_id=1, dimension_name="Technical Proficiency",
                description="Knowledge of algorithms and data structures",
                max_score=Decimal("25"), weight=Decimal("0.35"),
                sequence_order=1,
            ),
            RubricDimension(
                id=2, rubric_id=1, dimension_name="Problem Solving",
                description="Ability to break down complex problems",
                max_score=Decimal("25"), weight=Decimal("0.30"),
                sequence_order=2,
            ),
            RubricDimension(
                id=3, rubric_id=1, dimension_name="Communication",
                description="Clarity of explanation",
                max_score=Decimal("25"), weight=Decimal("0.20"),
                sequence_order=3,
            ),
            RubricDimension(
                id=4, rubric_id=1, dimension_name="Code Quality",
                description="Clean, readable code",
                max_score=Decimal("25"), weight=Decimal("0.15"),
                sequence_order=4,
            ),
        ]
        result = RubricValidator.validate_dimensions(dims)
        assert result.is_valid, [e.message for e in result.errors]


# ─────────────────────────────────────────────────────────────────
# Integration: pre-activation with realistic repos
# ─────────────────────────────────────────────────────────────────


class _InMemoryRoleRepo:
    def __init__(self, roles):
        self._data = {r.id: r for r in roles}

    def get_by_id(self, role_id):
        return self._data.get(role_id)

    def __getattr__(self, name):
        return lambda *a, **kw: None


class _InMemoryRubricRepo:
    def __init__(self, rubrics, dims_by_rubric=None):
        self._data = {r.id: r for r in rubrics}
        self._dims = dims_by_rubric or {}

    def get_by_id(self, rubric_id):
        return self._data.get(rubric_id)

    def get_dimensions(self, rubric_id):
        return self._dims.get(rubric_id, [])

    def __getattr__(self, name):
        return lambda *a, **kw: None


class _InMemoryTemplateRepo:
    def get_by_id(self, template_id):
        return None

    def __getattr__(self, name):
        return lambda *a, **kw: None


class TestPreActivationIntegration:
    """Full pre-activation validation with realistic sample data."""

    @pytest.fixture()
    def sample_structure(self) -> dict:
        return json.loads((_DOCS / "sample_i_template.json").read_text())

    def test_activation_happy_path(self, sample_structure):
        role = Role(id=1, name="Backend Engineer", description=None, scope=TemplateScope.PUBLIC)
        rubric = Rubric(
            id=10, organization_id=1, name="Technical Rubric",
            description=None, scope=TemplateScope.PUBLIC, is_active=True,
        )
        dims = [
            RubricDimension(
                id=1, rubric_id=10, dimension_name="Problem Solving",
                description=None, max_score=Decimal("10"),
                weight=Decimal("0.5"), sequence_order=1,
            ),
            RubricDimension(
                id=2, rubric_id=10, dimension_name="Communication",
                description=None, max_score=Decimal("10"),
                weight=Decimal("0.5"), sequence_order=2,
            ),
        ]

        template = Template(
            id=1, name="Backend Interview",
            description="Standard backend interview",
            scope=TemplateScope.PUBLIC, organization_id=1,
            template_structure=sample_structure, is_active=False,
        )
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=10)]

        validator = PreActivationValidator(
            template_repo=_InMemoryTemplateRepo(),
            rubric_repo=_InMemoryRubricRepo([rubric], {10: dims}),
            role_repo=_InMemoryRoleRepo([role]),
        )

        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert result.is_valid, [e.message for e in result.errors]

    def test_activation_fails_with_multiple_issues(self):
        """Ensure multiple issues are collected, not just the first."""
        validator = PreActivationValidator(
            template_repo=_InMemoryTemplateRepo(),
            rubric_repo=_InMemoryRubricRepo([]),
            role_repo=_InMemoryRoleRepo([]),
        )
        bad_template = Template(
            id=1, name="", description=None,
            scope=TemplateScope.PUBLIC, organization_id=1,
            template_structure={},
        )
        result = validator.validate(bad_template, role_ids=[], rubric_mappings=[])
        assert not result.is_valid
        assert len(result.errors) >= 2  # at least MISSING_NAME + NO_ROLES


# ─────────────────────────────────────────────────────────────────
# Integration: ValidationResult merge across modules
# ─────────────────────────────────────────────────────────────────


class TestCrossModuleMerge:
    """
    Validate that results from different validators can be merged into
    a single coherent report.
    """

    def test_merge_results_from_different_validators(self):
        template_result = TemplateStructureValidator.validate({})
        rubric_result = RubricValidator.validate_dimensions([])
        override_result = OverrideValidator.validate_fields({}, ContentType.TEMPLATE)

        merged = ValidationResult.merge_all(template_result, rubric_result, override_result)
        assert not merged.is_valid
        # Errors from all three validators present
        codes = {e.code for e in merged.errors}
        assert "NO_SECTIONS" in codes or "EMPTY_SECTIONS" in codes
        assert "EMPTY_DIMENSIONS" in codes
        assert "EMPTY_OVERRIDE" in codes
