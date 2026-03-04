"""
Unit Tests — Question Persistence Entities

Tests frozen dataclass construction, field defaults, immutability,
and field types for QuestionEntity, TopicEntity, CodingProblemEntity,
and CodingTestCaseEntity.

No mocks, no I/O.
"""

import pytest
from datetime import datetime, timezone

from app.question.persistence.entities import (
    CodingProblemEntity,
    CodingTestCaseEntity,
    QuestionEntity,
    TopicEntity,
)


# ═══════════════════════════════════════════════════════════════════════
# QuestionEntity
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionEntity:
    """Tests for QuestionEntity frozen dataclass."""

    def _make_entity(self, **overrides) -> QuestionEntity:
        defaults = dict(
            id=1,
            question_text="What is polymorphism?",
            answer_text="Polymorphism allows objects to take many forms.",
            question_type="technical",
            difficulty="medium",
            scope="public",
            organization_id=None,
            source_type=None,
            estimated_time_minutes=5,
            is_active=True,
        )
        defaults.update(overrides)
        return QuestionEntity(**defaults)

    def test_minimal_construction(self):
        q = self._make_entity()
        assert q.id == 1
        assert q.question_text == "What is polymorphism?"
        assert q.question_type == "technical"
        assert q.difficulty == "medium"
        assert q.scope == "public"
        assert q.organization_id is None
        assert q.estimated_time_minutes == 5
        assert q.is_active is True

    def test_optional_fields_default(self):
        q = self._make_entity()
        assert q.created_at is None
        assert q.updated_at is None
        assert q.topic_ids == []

    def test_topic_ids_populated(self):
        q = self._make_entity(topic_ids=[10, 20, 30])
        assert q.topic_ids == [10, 20, 30]

    def test_frozen_immutable(self):
        q = self._make_entity()
        with pytest.raises(AttributeError):
            q.id = 999  # type: ignore[misc]

    def test_frozen_immutable_question_text(self):
        q = self._make_entity()
        with pytest.raises(AttributeError):
            q.question_text = "changed"  # type: ignore[misc]

    def test_answer_text_nullable(self):
        q = self._make_entity(answer_text=None)
        assert q.answer_text is None

    def test_organization_scoped(self):
        q = self._make_entity(scope="organization", organization_id=42)
        assert q.scope == "organization"
        assert q.organization_id == 42

    def test_with_timestamps(self):
        now = datetime.now(timezone.utc)
        q = self._make_entity(created_at=now, updated_at=now)
        assert q.created_at == now
        assert q.updated_at == now

    def test_all_question_types(self):
        for qt in ("behavioral", "technical", "situational", "coding"):
            q = self._make_entity(question_type=qt)
            assert q.question_type == qt

    def test_all_difficulty_levels(self):
        for d in ("easy", "medium", "hard"):
            q = self._make_entity(difficulty=d)
            assert q.difficulty == d

    def test_equality(self):
        q1 = self._make_entity(id=1)
        q2 = self._make_entity(id=1)
        assert q1 == q2

    def test_inequality(self):
        q1 = self._make_entity(id=1)
        q2 = self._make_entity(id=2)
        assert q1 != q2


# ═══════════════════════════════════════════════════════════════════════
# TopicEntity
# ═══════════════════════════════════════════════════════════════════════


class TestTopicEntity:
    """Tests for TopicEntity frozen dataclass."""

    def _make_entity(self, **overrides) -> TopicEntity:
        defaults = dict(
            id=1,
            name="Algorithms",
            description="Basic algorithm concepts.",
            parent_topic_id=None,
            scope="public",
            organization_id=None,
        )
        defaults.update(overrides)
        return TopicEntity(**defaults)

    def test_minimal_construction(self):
        t = self._make_entity()
        assert t.id == 1
        assert t.name == "Algorithms"
        assert t.scope == "public"
        assert t.parent_topic_id is None

    def test_optional_fields_default(self):
        t = self._make_entity()
        assert t.estimated_time_minutes is None
        assert t.created_at is None
        assert t.updated_at is None

    def test_frozen_immutable(self):
        t = self._make_entity()
        with pytest.raises(AttributeError):
            t.name = "Changed"  # type: ignore[misc]

    def test_hierarchical_topic(self):
        parent = self._make_entity(id=1, name="Technical")
        child = self._make_entity(id=2, name="Sorting", parent_topic_id=1)
        assert child.parent_topic_id == parent.id

    def test_organization_scoped(self):
        t = self._make_entity(scope="organization", organization_id=99)
        assert t.scope == "organization"
        assert t.organization_id == 99


# ═══════════════════════════════════════════════════════════════════════
# CodingTestCaseEntity
# ═══════════════════════════════════════════════════════════════════════


class TestCodingTestCaseEntity:
    """Tests for CodingTestCaseEntity frozen dataclass."""

    def _make_entity(self, **overrides) -> CodingTestCaseEntity:
        defaults = dict(
            id=1,
            coding_problem_id=10,
            input_data='{"nums": [1,2,3]}',
            expected_output="6",
            is_hidden=False,
            weight=1.0,
        )
        defaults.update(overrides)
        return CodingTestCaseEntity(**defaults)

    def test_minimal_construction(self):
        tc = self._make_entity()
        assert tc.id == 1
        assert tc.coding_problem_id == 10
        assert tc.input_data == '{"nums": [1,2,3]}'
        assert tc.expected_output == "6"
        assert tc.is_hidden is False
        assert tc.weight == 1.0

    def test_hidden_case_masked(self):
        """Hidden test cases can have expected_output set to None."""
        tc = self._make_entity(is_hidden=True, expected_output=None)
        assert tc.is_hidden is True
        assert tc.expected_output is None

    def test_visible_case_has_output(self):
        tc = self._make_entity(is_hidden=False, expected_output="42")
        assert tc.expected_output == "42"

    def test_frozen_immutable(self):
        tc = self._make_entity()
        with pytest.raises(AttributeError):
            tc.weight = 2.0  # type: ignore[misc]

    def test_custom_weight(self):
        tc = self._make_entity(weight=2.5)
        assert tc.weight == 2.5


# ═══════════════════════════════════════════════════════════════════════
# CodingProblemEntity
# ═══════════════════════════════════════════════════════════════════════


class TestCodingProblemEntity:
    """Tests for CodingProblemEntity frozen dataclass."""

    def _make_entity(self, **overrides) -> CodingProblemEntity:
        defaults = dict(
            id=1,
            title="Two Sum",
            body="Given an array of integers...",
            difficulty="easy",
            scope="public",
            organization_id=None,
            description="Find two numbers that add up to target.",
            constraints="1 <= nums.length <= 10^4",
            estimated_time_minutes=30,
            is_active=True,
            source_name="leetcode",
            source_id="1",
        )
        defaults.update(overrides)
        return CodingProblemEntity(**defaults)

    def test_minimal_construction(self):
        p = self._make_entity()
        assert p.id == 1
        assert p.title == "Two Sum"
        assert p.difficulty == "easy"
        assert p.scope == "public"
        assert p.is_active is True
        assert p.source_name == "leetcode"

    def test_optional_fields_default(self):
        p = self._make_entity()
        assert p.source_slug is None
        assert p.raw_content is None
        assert p.examples == []
        assert p.constraints_structured == []
        assert p.hints == []
        assert p.stats is None
        assert p.code_snippets == {}
        assert p.test_cases == []

    def test_frozen_immutable(self):
        p = self._make_entity()
        with pytest.raises(AttributeError):
            p.title = "Three Sum"  # type: ignore[misc]

    def test_with_test_cases(self):
        tc1 = CodingTestCaseEntity(
            id=1, coding_problem_id=1, input_data="[1,2]",
            expected_output="3", is_hidden=False, weight=1.0,
        )
        tc2 = CodingTestCaseEntity(
            id=2, coding_problem_id=1, input_data="[3,4]",
            expected_output="7", is_hidden=True, weight=1.0,
        )
        p = self._make_entity(test_cases=[tc1, tc2])
        assert len(p.test_cases) == 2
        assert p.test_cases[0].expected_output == "3"
        assert p.test_cases[1].is_hidden is True

    def test_with_code_snippets(self):
        snippets = {"python": "def twoSum(nums, target):", "java": "class Solution {}"}
        p = self._make_entity(code_snippets=snippets)
        assert p.code_snippets["python"] == "def twoSum(nums, target):"
        assert "java" in p.code_snippets

    def test_with_examples(self):
        examples = [
            {"input": "[2,7,11,15], target=9", "output": "[0,1]"},
        ]
        p = self._make_entity(examples=examples)
        assert len(p.examples) == 1
        assert p.examples[0]["output"] == "[0,1]"

    def test_organization_scoped(self):
        p = self._make_entity(scope="organization", organization_id=5)
        assert p.scope == "organization"
        assert p.organization_id == 5

    def test_equality(self):
        p1 = self._make_entity(id=1)
        p2 = self._make_entity(id=1)
        assert p1 == p2

