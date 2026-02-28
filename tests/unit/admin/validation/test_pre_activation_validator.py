"""
Unit tests for PreActivationValidator.

Tests the composite pre-activation check that orchestrates:
  1. Template name check
  2. Template structure validation
  3. Role cross-ref checks
  4. Rubric cross-ref checks
  5. Rubric dimension consistency

Uses fake in-memory repos that satisfy Protocol interfaces structurally.
"""

import pytest
from decimal import Decimal
from typing import Dict, List, Optional

from app.admin.domain.entities import (
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRubric,
    TemplateScope,
)
from app.admin.validation.pre_activation_validator import PreActivationValidator


# ─────────────────────────────────────────────────────────────────
# Fake repositories
# ─────────────────────────────────────────────────────────────────


class FakeRoleRepo:
    def __init__(self, roles: Dict[int, Role]):
        self._data = roles

    def get_by_id(self, role_id: int) -> Optional[Role]:
        return self._data.get(role_id)

    def __getattr__(self, name):
        return lambda *a, **kw: None


class FakeRubricRepo:
    def __init__(
        self,
        rubrics: Dict[int, Rubric],
        dimensions: Optional[Dict[int, List[RubricDimension]]] = None,
    ):
        self._data = rubrics
        self._dims = dimensions or {}

    def get_by_id(self, rubric_id: int) -> Optional[Rubric]:
        return self._data.get(rubric_id)

    def get_dimensions(self, rubric_id: int) -> List[RubricDimension]:
        return self._dims.get(rubric_id, [])

    def __getattr__(self, name):
        return lambda *a, **kw: None


class FakeTemplateRepo:
    def __init__(self, templates: Optional[Dict[int, Template]] = None):
        self._data = templates or {}

    def get_by_id(self, template_id: int) -> Optional[Template]:
        return self._data.get(template_id)

    def __getattr__(self, name):
        return lambda *a, **kw: None


# ─────────────────────────────────────────────────────────────────
# Factories
# ─────────────────────────────────────────────────────────────────


def _role(id: int) -> Role:
    return Role(id=id, name=f"Role {id}", description=None, scope=TemplateScope.PUBLIC)


def _rubric(id: int, *, active: bool = True) -> Rubric:
    return Rubric(
        id=id, organization_id=1, name=f"Rubric {id}",
        description=None, scope=TemplateScope.PUBLIC, is_active=active,
    )


def _dim(rubric_id: int, name: str, weight: str, seq: int) -> RubricDimension:
    return RubricDimension(
        id=None, rubric_id=rubric_id, dimension_name=name,
        description=None, max_score=Decimal("10"), weight=Decimal(weight),
        sequence_order=seq,
    )


_VALID_STRUCTURE = {
    "topics_assessment": {
        "weight": 0.5,
        "enabled": True,
    },
    "coding_round": {
        "weight": 0.5,
        "enabled": True,
    },
}


def _template(id: int = 1, *, name: str = "Test Template", active: bool = True) -> Template:
    return Template(
        id=id, name=name, description="desc",
        scope=TemplateScope.PUBLIC, organization_id=1,
        template_structure=_VALID_STRUCTURE, is_active=active,
    )


# ─────────────────────────────────────────────────────────────────
# Fully valid activation
# ─────────────────────────────────────────────────────────────────


class TestFullyValid:
    def test_valid_template_passes(self):
        role_repo = FakeRoleRepo({1: _role(1)})
        rubric_repo = FakeRubricRepo(
            rubrics={10: _rubric(10)},
            dimensions={10: [
                _dim(10, "D1", "0.6", 1),
                _dim(10, "D2", "0.4", 2),
            ]},
        )
        template_repo = FakeTemplateRepo()
        validator = PreActivationValidator(
            template_repo=template_repo,
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )
        template = _template()
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=10)]
        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert result.is_valid, [e.message for e in result.errors]


# ─────────────────────────────────────────────────────────────────
# Missing template name
# ─────────────────────────────────────────────────────────────────


class TestMissingName:
    def test_empty_name(self):
        validator = _build_validator()
        template = _template(name="")
        result = validator.validate(template, role_ids=[1], rubric_mappings=[])
        assert not result.is_valid
        assert any(e.code == "MISSING_NAME" for e in result.errors)

    def test_whitespace_name(self):
        validator = _build_validator()
        template = _template(name="   ")
        result = validator.validate(template, role_ids=[1], rubric_mappings=[])
        assert not result.is_valid
        assert any(e.code == "MISSING_NAME" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# No roles assigned
# ─────────────────────────────────────────────────────────────────


class TestNoRoles:
    def test_empty_role_ids(self):
        validator = _build_validator()
        template = _template()
        result = validator.validate(template, role_ids=[], rubric_mappings=[])
        assert not result.is_valid
        assert any(e.code == "NO_ROLES" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Role cross-reference failure
# ─────────────────────────────────────────────────────────────────


class TestRoleCrossRef:
    def test_missing_role(self):
        role_repo = FakeRoleRepo({1: _role(1)})  # only role 1
        validator = PreActivationValidator(
            template_repo=FakeTemplateRepo(),
            rubric_repo=FakeRubricRepo({}),
            role_repo=role_repo,
        )
        template = _template()
        result = validator.validate(template, role_ids=[1, 999], rubric_mappings=[])
        assert not result.is_valid
        assert any(e.code == "INVALID_REFERENCE" and "999" in e.message for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Rubric cross-reference failure
# ─────────────────────────────────────────────────────────────────


class TestRubricCrossRef:
    def test_missing_rubric(self):
        rubric_repo = FakeRubricRepo({})  # empty
        role_repo = FakeRoleRepo({1: _role(1)})
        validator = PreActivationValidator(
            template_repo=FakeTemplateRepo(),
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )
        template = _template()
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=99)]
        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert not result.is_valid
        assert any(e.code == "INVALID_REFERENCE" for e in result.errors)

    def test_inactive_rubric(self):
        rubric_repo = FakeRubricRepo({10: _rubric(10, active=False)})
        role_repo = FakeRoleRepo({1: _role(1)})
        validator = PreActivationValidator(
            template_repo=FakeTemplateRepo(),
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )
        template = _template()
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=10)]
        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert not result.is_valid
        assert any(e.code == "INACTIVE_REFERENCE" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Rubric dimension consistency failure
# ─────────────────────────────────────────────────────────────────


class TestRubricDimensionConsistency:
    def test_empty_dimensions_flagged(self):
        rubric_repo = FakeRubricRepo(
            rubrics={10: _rubric(10)},
            dimensions={10: []},  # no dims
        )
        role_repo = FakeRoleRepo({1: _role(1)})
        validator = PreActivationValidator(
            template_repo=FakeTemplateRepo(),
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )
        template = _template()
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=10)]
        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert not result.is_valid
        assert any(e.code == "EMPTY_DIMENSIONS" for e in result.errors)

    def test_bad_weight_sum(self):
        rubric_repo = FakeRubricRepo(
            rubrics={10: _rubric(10)},
            dimensions={10: [
                _dim(10, "D1", "0.3", 1),
                _dim(10, "D2", "0.3", 2),
            ]},  # sum=0.6 ≠ 1
        )
        role_repo = FakeRoleRepo({1: _role(1)})
        validator = PreActivationValidator(
            template_repo=FakeTemplateRepo(),
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )
        template = _template()
        mappings = [TemplateRubric(id=None, interview_template_id=1, rubric_id=10)]
        result = validator.validate(template, role_ids=[1], rubric_mappings=mappings)
        assert not result.is_valid
        assert any(e.code == "WEIGHT_SUM_MISMATCH" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Multiple errors accumulated
# ─────────────────────────────────────────────────────────────────


class TestMultipleErrors:
    def test_several_issues_collected(self):
        """
        Bad name + no roles + bad structure all collected together.
        """
        validator = _build_validator()
        bad_template = Template(
            id=1, name="", description=None,
            scope=TemplateScope.PUBLIC, organization_id=1,
            template_structure="not-a-dict",  # type: ignore[arg-type]
        )
        result = validator.validate(bad_template, role_ids=[], rubric_mappings=[])
        assert not result.is_valid
        codes = {e.code for e in result.errors}
        assert "MISSING_NAME" in codes
        assert "NO_ROLES" in codes
        # Template structure validation should also fail
        assert len(result.errors) >= 3


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────


def _build_validator() -> PreActivationValidator:
    """Build a validator with minimal valid fake repos."""
    return PreActivationValidator(
        template_repo=FakeTemplateRepo(),
        rubric_repo=FakeRubricRepo({}),
        role_repo=FakeRoleRepo({1: _role(1)}),
    )
