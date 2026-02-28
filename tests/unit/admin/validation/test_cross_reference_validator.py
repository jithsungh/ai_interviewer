"""
Unit tests for CrossReferenceValidator.

Uses mock repository implementations (compatible with Protocol interfaces)
to test cross-entity reference checks without touching a database.
"""

import pytest
from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import MagicMock

from app.admin.domain.entities import (
    Role,
    Rubric,
    Template,
    TemplateScope,
    Topic,
    CodingTopic,
    CodingTopicType,
    WindowRoleTemplate,
)
from app.admin.validation.cross_reference_validator import CrossReferenceValidator


# ─────────────────────────────────────────────────────────────────
# Fake repository implementations (satisfy Protocol structurally)
# ─────────────────────────────────────────────────────────────────


class FakeRoleRepo:
    """In-memory role repository with id → Role lookup."""

    def __init__(self, roles: Dict[int, Role]):
        self._data = roles

    def get_by_id(self, role_id: int) -> Optional[Role]:
        return self._data.get(role_id)

    # Satisfy remaining protocol methods with no-ops
    def __getattr__(self, name):
        return lambda *a, **kw: None


class FakeRubricRepo:
    """In-memory rubric repository."""

    def __init__(self, rubrics: Dict[int, Rubric], *, dimensions=None):
        self._data = rubrics
        self._dims = dimensions or {}

    def get_by_id(self, rubric_id: int) -> Optional[Rubric]:
        return self._data.get(rubric_id)

    def get_dimensions(self, rubric_id: int):
        return self._dims.get(rubric_id, [])

    def __getattr__(self, name):
        return lambda *a, **kw: None


class FakeTemplateRepo:
    """In-memory template repository."""

    def __init__(self, templates: Dict[int, Template]):
        self._data = templates

    def get_by_id(self, template_id: int) -> Optional[Template]:
        return self._data.get(template_id)

    def __getattr__(self, name):
        return lambda *a, **kw: None


class FakeTopicRepo:
    """In-memory topic repository with ancestor chain support."""

    def __init__(
        self,
        topics: Optional[Dict[int, Topic]] = None,
        ancestors: Optional[Dict[int, List[int]]] = None,
        coding_topics: Optional[Dict[int, CodingTopic]] = None,
        coding_ancestors: Optional[Dict[int, List[int]]] = None,
    ):
        self._topics = topics or {}
        self._ancestors = ancestors or {}
        self._coding_topics = coding_topics or {}
        self._coding_ancestors = coding_ancestors or {}

    def get_topic_by_id(self, topic_id: int) -> Optional[Topic]:
        return self._topics.get(topic_id)

    def get_topic_ancestors(self, topic_id: int) -> List[int]:
        return self._ancestors.get(topic_id, [])

    def get_coding_topic_by_id(self, topic_id: int) -> Optional[CodingTopic]:
        return self._coding_topics.get(topic_id)

    def get_coding_topic_ancestors(self, topic_id: int) -> List[int]:
        return self._coding_ancestors.get(topic_id, [])

    def __getattr__(self, name):
        return lambda *a, **kw: None


# ─────────────────────────────────────────────────────────────────
# Factories
# ─────────────────────────────────────────────────────────────────


def _role(id: int, name: str = "Role") -> Role:
    return Role(id=id, name=name, description=None, scope=TemplateScope.PUBLIC)


def _rubric(id: int, *, active: bool = True) -> Rubric:
    return Rubric(
        id=id, organization_id=1, name=f"Rubric {id}",
        description=None, scope=TemplateScope.PUBLIC, is_active=active,
    )


def _template(id: int, *, active: bool = True) -> Template:
    return Template(
        id=id, name=f"Template {id}", description=None,
        scope=TemplateScope.PUBLIC, organization_id=1,
        template_structure={}, is_active=active,
    )


def _topic(id: int, parent_topic_id: Optional[int] = None) -> Topic:
    return Topic(
        id=id, name=f"Topic {id}", description=None,
        parent_topic_id=parent_topic_id,
    )


def _coding_topic(id: int, parent_topic_id: Optional[int] = None) -> CodingTopic:
    return CodingTopic(
        id=id, name=f"CT {id}", description=None,
        topic_type=CodingTopicType.DATA_STRUCTURE,
        parent_topic_id=parent_topic_id,
    )


# ─────────────────────────────────────────────────────────────────
# Template → Role refs
# ─────────────────────────────────────────────────────────────────


class TestTemplateRoleRefs:
    def test_all_roles_exist(self):
        repo = FakeRoleRepo({1: _role(1), 2: _role(2)})
        v = CrossReferenceValidator(role_repo=repo)
        result = v.validate_template_role_refs([1, 2])
        assert result.is_valid

    def test_missing_role(self):
        repo = FakeRoleRepo({1: _role(1)})
        v = CrossReferenceValidator(role_repo=repo)
        result = v.validate_template_role_refs([1, 99])
        assert not result.is_valid
        assert any(e.code == "INVALID_REFERENCE" and "99" in e.message for e in result.errors)

    def test_no_repo_skips_check(self):
        v = CrossReferenceValidator()
        result = v.validate_template_role_refs([1, 2])
        assert result.is_valid  # gracefully skipped


# ─────────────────────────────────────────────────────────────────
# Template → Rubric refs
# ─────────────────────────────────────────────────────────────────


class TestTemplateRubricRefs:
    def test_all_rubrics_exist_and_active(self):
        repo = FakeRubricRepo({1: _rubric(1), 2: _rubric(2)})
        v = CrossReferenceValidator(rubric_repo=repo)
        result = v.validate_template_rubric_refs([1, 2])
        assert result.is_valid

    def test_missing_rubric(self):
        repo = FakeRubricRepo({1: _rubric(1)})
        v = CrossReferenceValidator(rubric_repo=repo)
        result = v.validate_template_rubric_refs([1, 99])
        assert not result.is_valid
        assert any(e.code == "INVALID_REFERENCE" for e in result.errors)

    def test_inactive_rubric(self):
        repo = FakeRubricRepo({1: _rubric(1, active=False)})
        v = CrossReferenceValidator(rubric_repo=repo)
        result = v.validate_template_rubric_refs([1])
        assert not result.is_valid
        assert any(e.code == "INACTIVE_REFERENCE" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Window mappings
# ─────────────────────────────────────────────────────────────────


class TestWindowMappings:
    def test_valid_mappings(self):
        roles = FakeRoleRepo({1: _role(1)})
        templates = FakeTemplateRepo({10: _template(10)})
        v = CrossReferenceValidator(role_repo=roles, template_repo=templates)
        mappings = [WindowRoleTemplate(id=None, window_id=1, role_id=1, template_id=10)]
        result = v.validate_window_mappings(mappings)
        assert result.is_valid

    def test_missing_role_in_mapping(self):
        roles = FakeRoleRepo({})
        templates = FakeTemplateRepo({10: _template(10)})
        v = CrossReferenceValidator(role_repo=roles, template_repo=templates)
        mappings = [WindowRoleTemplate(id=None, window_id=1, role_id=99, template_id=10)]
        result = v.validate_window_mappings(mappings)
        assert not result.is_valid

    def test_inactive_template_in_mapping(self):
        roles = FakeRoleRepo({1: _role(1)})
        templates = FakeTemplateRepo({10: _template(10, active=False)})
        v = CrossReferenceValidator(role_repo=roles, template_repo=templates)
        mappings = [WindowRoleTemplate(id=None, window_id=1, role_id=1, template_id=10)]
        result = v.validate_window_mappings(mappings)
        assert not result.is_valid
        assert any(e.code == "INACTIVE_REFERENCE" for e in result.errors)

    def test_empty_mappings_valid(self):
        v = CrossReferenceValidator()
        result = v.validate_window_mappings([])
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Topic parent validation
# ─────────────────────────────────────────────────────────────────


class TestTopicParent:
    def test_valid_parent(self):
        repo = FakeTopicRepo({10: _topic(10)})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_topic_parent(topic_id=20, parent_topic_id=10)
        assert result.is_valid

    def test_self_reference(self):
        repo = FakeTopicRepo({5: _topic(5)})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_topic_parent(topic_id=5, parent_topic_id=5)
        assert not result.is_valid
        assert result.errors[0].code == "SELF_REFERENCE"

    def test_missing_parent(self):
        repo = FakeTopicRepo({})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_topic_parent(topic_id=20, parent_topic_id=99)
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_REFERENCE"

    def test_circular_reference(self):
        """If topic_id appears in the ancestor chain of parent → cycle."""
        repo = FakeTopicRepo(
            topics={10: _topic(10)},
            ancestors={10: [5, 20]},  # 20 is in the ancestor chain
        )
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_topic_parent(topic_id=20, parent_topic_id=10)
        assert not result.is_valid
        assert result.errors[0].code == "CIRCULAR_REFERENCE"

    def test_new_topic_skips_cycle_check(self):
        """topic_id=None means new entity — cycle detection skipped."""
        repo = FakeTopicRepo(topics={10: _topic(10)})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_topic_parent(topic_id=None, parent_topic_id=10)
        assert result.is_valid

    def test_no_repo_skips(self):
        v = CrossReferenceValidator()
        result = v.validate_topic_parent(topic_id=1, parent_topic_id=2)
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Coding topic parent validation
# ─────────────────────────────────────────────────────────────────


class TestCodingTopicParent:
    def test_valid_coding_parent(self):
        repo = FakeTopicRepo(coding_topics={10: _coding_topic(10)})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_coding_topic_parent(topic_id=20, parent_topic_id=10)
        assert result.is_valid

    def test_self_reference_coding(self):
        repo = FakeTopicRepo(coding_topics={5: _coding_topic(5)})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_coding_topic_parent(topic_id=5, parent_topic_id=5)
        assert not result.is_valid
        assert result.errors[0].code == "SELF_REFERENCE"

    def test_missing_coding_parent(self):
        repo = FakeTopicRepo(coding_topics={})
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_coding_topic_parent(topic_id=20, parent_topic_id=99)
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_REFERENCE"

    def test_circular_coding_reference(self):
        repo = FakeTopicRepo(
            coding_topics={10: _coding_topic(10)},
            coding_ancestors={10: [5, 20]},
        )
        v = CrossReferenceValidator(topic_repo=repo)
        result = v.validate_coding_topic_parent(topic_id=20, parent_topic_id=10)
        assert not result.is_valid
        assert result.errors[0].code == "CIRCULAR_REFERENCE"
