"""
Unit tests for admin domain entities.

Tests entity construction, enum values, helper methods, and invariants.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.admin.domain.entities import (
    IMMUTABLE_OVERRIDE_FIELDS,
    RUBRIC_WEIGHT_TOLERANCE,
    SUPER_ORG_ID,
    CodingProblem,
    CodingTopic,
    CodingTopicType,
    ContentType,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    Question,
    QuestionType,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRole,
    TemplateRubric,
    TemplateScope,
    Topic,
    Window,
    WindowRoleTemplate,
)


# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

class TestConstants:
    def test_super_org_id(self):
        assert SUPER_ORG_ID == 1

    def test_rubric_weight_tolerance(self):
        assert RUBRIC_WEIGHT_TOLERANCE == 0.001

    def test_immutable_override_fields(self):
        assert "id" in IMMUTABLE_OVERRIDE_FIELDS
        assert "organization_id" in IMMUTABLE_OVERRIDE_FIELDS
        assert "scope" in IMMUTABLE_OVERRIDE_FIELDS
        assert "created_at" in IMMUTABLE_OVERRIDE_FIELDS
        assert "updated_at" in IMMUTABLE_OVERRIDE_FIELDS
        # Should be a frozenset (immutable)
        assert isinstance(IMMUTABLE_OVERRIDE_FIELDS, frozenset)


# ─────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────

class TestEnums:
    def test_template_scope_values(self):
        assert TemplateScope.PUBLIC.value == "public"
        assert TemplateScope.ORGANIZATION.value == "organization"
        assert TemplateScope.PRIVATE.value == "private"

    def test_interview_scope_values(self):
        assert InterviewScope.GLOBAL.value == "global"
        assert InterviewScope.LOCAL.value == "local"
        assert InterviewScope.ONLY_INVITED.value == "only_invited"

    def test_difficulty_level_values(self):
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.MEDIUM.value == "medium"
        assert DifficultyLevel.HARD.value == "hard"

    def test_question_type_values(self):
        assert QuestionType.BEHAVIORAL.value == "behavioral"
        assert QuestionType.TECHNICAL.value == "technical"
        assert QuestionType.SITUATIONAL.value == "situational"
        assert QuestionType.CODING.value == "coding"

    def test_coding_topic_type_values(self):
        assert CodingTopicType.DATA_STRUCTURE.value == "data_structure"
        assert CodingTopicType.ALGORITHM.value == "algorithm"
        assert CodingTopicType.TRAVERSAL.value == "traversal"

    def test_content_type_values(self):
        assert ContentType.TEMPLATE.value == "template"
        assert ContentType.RUBRIC.value == "rubric"
        assert ContentType.ROLE.value == "role"
        assert ContentType.TOPIC.value == "topic"
        assert ContentType.QUESTION.value == "question"
        assert ContentType.CODING_PROBLEM.value == "coding_problem"


# ─────────────────────────────────────────────────────────────────
# Template Entity
# ─────────────────────────────────────────────────────────────────

class TestTemplate:
    def _make_template(self, **overrides):
        defaults = dict(
            id=1,
            name="Senior Engineer Template",
            description="Full loop",
            scope=TemplateScope.PUBLIC,
            organization_id=1,
            template_structure={"sections": [{"name": "behavioral"}]},
            rules={"max_time": 60},
            total_estimated_time_minutes=60,
            version=1,
            is_active=True,
        )
        defaults.update(overrides)
        return Template(**defaults)

    def test_create_basic(self):
        t = self._make_template()
        assert t.id == 1
        assert t.name == "Senior Engineer Template"
        assert t.version == 1
        assert t.is_active is True

    def test_default_values(self):
        t = Template(
            id=None,
            name="Test",
            description=None,
            scope=TemplateScope.PUBLIC,
            organization_id=None,
            template_structure={},
        )
        assert t.version == 1
        assert t.is_active is True
        assert t.rules is None
        assert t.total_estimated_time_minutes is None

    def test_create_new_version(self):
        original = self._make_template(version=2)
        new = original.create_new_version()

        assert new.id is None  # New entity, no DB id yet
        assert new.version == 3  # Incremented
        assert new.name == original.name
        assert new.organization_id == original.organization_id
        assert new.template_structure == original.template_structure
        assert new.created_at is None  # Reset for persistence layer

    def test_create_new_version_deep_copies_structure(self):
        """Mutating the new version's structure should NOT affect the original."""
        original = self._make_template(template_structure={"a": [1, 2, 3]})
        new = original.create_new_version()
        new.template_structure["a"].append(4)

        assert len(original.template_structure["a"]) == 3  # Unchanged
        assert len(new.template_structure["a"]) == 4


# ─────────────────────────────────────────────────────────────────
# Rubric & RubricDimension Entity
# ─────────────────────────────────────────────────────────────────

class TestRubric:
    def test_create_rubric(self):
        r = Rubric(
            id=1,
            organization_id=1,
            name="Technical Rubric",
            description="Coding evaluation",
            scope=TemplateScope.PUBLIC,
            schema={"dimensions": []},
            is_active=True,
        )
        assert r.name == "Technical Rubric"
        assert r.is_active is True

    def test_rubric_dimension(self):
        d = RubricDimension(
            id=1,
            rubric_id=1,
            dimension_name="Problem Solving",
            description="Ability to solve complex problems",
            max_score=Decimal("10.0"),
            weight=Decimal("0.4"),
            criteria={"levels": [{"score": 1, "desc": "Poor"}]},
            sequence_order=0,
        )
        assert d.weight == Decimal("0.4")
        assert d.sequence_order == 0


# ─────────────────────────────────────────────────────────────────
# Role Entity
# ─────────────────────────────────────────────────────────────────

class TestRole:
    def test_create_role(self):
        r = Role(
            id=1,
            name="Backend Engineer",
            description="Backend role",
            scope=TemplateScope.PUBLIC,
            organization_id=1,
        )
        assert r.name == "Backend Engineer"
        assert r.scope == TemplateScope.PUBLIC


# ─────────────────────────────────────────────────────────────────
# Topic Entity
# ─────────────────────────────────────────────────────────────────

class TestTopic:
    def test_create_topic(self):
        t = Topic(
            id=1,
            name="System Design",
            description="Architecture topics",
            parent_topic_id=None,
            scope=TemplateScope.PUBLIC,
            organization_id=1,
        )
        assert t.parent_topic_id is None

    def test_coding_topic(self):
        ct = CodingTopic(
            id=1,
            name="Binary Trees",
            description="Tree problems",
            topic_type=CodingTopicType.DATA_STRUCTURE,
            parent_topic_id=None,
            scope=TemplateScope.PUBLIC,
            organization_id=1,
            display_order=1,
        )
        assert ct.topic_type == CodingTopicType.DATA_STRUCTURE
        assert ct.display_order == 1


# ─────────────────────────────────────────────────────────────────
# Question Entity
# ─────────────────────────────────────────────────────────────────

class TestQuestion:
    def test_create_question(self):
        q = Question(
            id=1,
            question_text="Tell me about a time...",
            answer_text=None,
            question_type=QuestionType.BEHAVIORAL,
            difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC,
            organization_id=1,
        )
        assert q.estimated_time_minutes == 5  # default
        assert q.is_active is True


# ─────────────────────────────────────────────────────────────────
# CodingProblem Entity
# ─────────────────────────────────────────────────────────────────

class TestCodingProblem:
    def test_create_coding_problem(self):
        cp = CodingProblem(
            id=1,
            title="Two Sum",
            body="Given an array...",
            difficulty=DifficultyLevel.EASY,
            scope=TemplateScope.PUBLIC,
            organization_id=1,
        )
        assert cp.estimated_time_minutes == 30  # default
        assert cp.examples == []
        assert cp.hints == []
        assert cp.code_snippets == {}


# ─────────────────────────────────────────────────────────────────
# Window & WindowRoleTemplate Entity
# ─────────────────────────────────────────────────────────────────

class TestWindow:
    def test_create_window(self):
        w = Window(
            id=1,
            organization_id=1,
            admin_id=42,
            name="March 2026 Sprint",
            scope=InterviewScope.GLOBAL,
            start_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 15, tzinfo=timezone.utc),
            timezone="UTC",
        )
        assert w.allow_resubmission is False
        assert w.max_allowed_submissions is None

    def test_window_role_template(self):
        wrt = WindowRoleTemplate(
            id=1,
            window_id=1,
            role_id=2,
            template_id=3,
            selection_weight=5,
        )
        assert wrt.selection_weight == 5


# ─────────────────────────────────────────────────────────────────
# OverrideRecord
# ─────────────────────────────────────────────────────────────────

class TestOverrideRecord:
    def test_create_override(self):
        o = OverrideRecord(
            id=1,
            organization_id=2,
            base_content_id=10,
            content_type=ContentType.TEMPLATE,
            override_fields={"name": "Custom Name"},
            is_active=True,
        )
        assert o.content_type == ContentType.TEMPLATE
        assert o.override_fields == {"name": "Custom Name"}

    def test_override_default_active(self):
        o = OverrideRecord(
            id=None,
            organization_id=2,
            base_content_id=10,
            content_type=ContentType.RUBRIC,
            override_fields={},
        )
        assert o.is_active is True


# ─────────────────────────────────────────────────────────────────
# TemplateRole & TemplateRubric
# ─────────────────────────────────────────────────────────────────

class TestMappingEntities:
    def test_template_role(self):
        tr = TemplateRole(interview_template_id=1, role_id=2)
        assert tr.interview_template_id == 1

    def test_template_rubric(self):
        tr = TemplateRubric(
            id=None,
            interview_template_id=1,
            rubric_id=3,
            section_name="coding",
        )
        assert tr.section_name == "coding"
