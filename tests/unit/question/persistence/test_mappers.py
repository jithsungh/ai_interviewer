"""
Unit Tests — Question Persistence Mappers

Tests ORM → entity conversion functions including:
- QuestionModel → QuestionEntity
- TopicModel → TopicEntity
- CodingTestCaseModel → CodingTestCaseEntity (hidden output masking)
- CodingProblemModel → CodingProblemEntity

Uses mock ORM objects to avoid real DB dependency.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.question.persistence.mappers import (
    coding_problem_model_to_entity,
    coding_test_case_model_to_entity,
    question_model_to_entity,
    topic_model_to_entity,
)
from app.question.persistence.entities import (
    CodingProblemEntity,
    CodingTestCaseEntity,
    QuestionEntity,
    TopicEntity,
)


# ── Factory helpers ────────────────────────────────────────────────


def _mock_question_model(**overrides):
    """Create a mock QuestionModel ORM object."""
    now = datetime.now(timezone.utc)
    m = MagicMock()
    defaults = dict(
        id=1,
        question_text="What is Big-O notation?",
        answer_text="A way to classify algorithm efficiency.",
        question_type="technical",
        difficulty="medium",
        scope="public",
        organization_id=None,
        source_type=None,
        estimated_time_minutes=5,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_topic_model(**overrides):
    """Create a mock TopicModel ORM object."""
    now = datetime.now(timezone.utc)
    m = MagicMock()
    defaults = dict(
        id=1,
        name="Data Structures",
        description="Core data structure concepts.",
        parent_topic_id=None,
        scope="public",
        organization_id=None,
        estimated_time_minutes=10,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_test_case_model(**overrides):
    """Create a mock CodingTestCaseModel ORM object."""
    m = MagicMock()
    defaults = dict(
        id=1,
        coding_problem_id=10,
        input_data='[1, 2, 3]',
        expected_output="6",
        is_hidden=False,
        weight=1.0,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_coding_problem_model(**overrides):
    """Create a mock CodingProblemModel ORM object."""
    now = datetime.now(timezone.utc)
    m = MagicMock()
    defaults = dict(
        id=1,
        title="Two Sum",
        body="Given an array of integers...",
        difficulty="easy",
        scope="public",
        organization_id=None,
        description="Find two numbers matching target.",
        constraints="1 <= nums.length <= 10^4",
        estimated_time_minutes=30,
        is_active=True,
        source_name="leetcode",
        source_id="1",
        source_slug="two-sum",
        raw_content=None,
        examples=[{"input": "[2,7]", "output": "[0,1]"}],
        constraints_structured=[{"type": "range", "value": "1 <= n <= 10^4"}],
        hints=[{"text": "Use a hash map"}],
        stats={"acceptance": 48.5},
        code_snippets={"python": "def twoSum(nums, target):"},
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ═══════════════════════════════════════════════════════════════════════
# question_model_to_entity
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionModelToEntity:
    """Tests for question_model_to_entity mapper."""

    def test_basic_conversion(self):
        m = _mock_question_model()
        entity = question_model_to_entity(m)
        assert isinstance(entity, QuestionEntity)
        assert entity.id == 1
        assert entity.question_text == "What is Big-O notation?"
        assert entity.difficulty == "medium"

    def test_topic_ids_passed_through(self):
        m = _mock_question_model()
        entity = question_model_to_entity(m, topic_ids=[5, 10, 15])
        assert entity.topic_ids == [5, 10, 15]

    def test_topic_ids_default_empty(self):
        m = _mock_question_model()
        entity = question_model_to_entity(m, topic_ids=None)
        assert entity.topic_ids == []

    def test_all_fields_mapped(self):
        m = _mock_question_model(
            answer_text="Some answer",
            organization_id=42,
            source_type="manual",
        )
        entity = question_model_to_entity(m)
        assert entity.answer_text == "Some answer"
        assert entity.organization_id == 42
        assert entity.source_type == "manual"

    def test_timestamps_preserved(self):
        now = datetime.now(timezone.utc)
        m = _mock_question_model(created_at=now, updated_at=now)
        entity = question_model_to_entity(m)
        assert entity.created_at == now
        assert entity.updated_at == now

    def test_result_is_frozen(self):
        m = _mock_question_model()
        entity = question_model_to_entity(m)
        with pytest.raises(AttributeError):
            entity.id = 999  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════
# topic_model_to_entity
# ═══════════════════════════════════════════════════════════════════════


class TestTopicModelToEntity:
    """Tests for topic_model_to_entity mapper."""

    def test_basic_conversion(self):
        m = _mock_topic_model()
        entity = topic_model_to_entity(m)
        assert isinstance(entity, TopicEntity)
        assert entity.id == 1
        assert entity.name == "Data Structures"

    def test_parent_topic_preserved(self):
        m = _mock_topic_model(parent_topic_id=5)
        entity = topic_model_to_entity(m)
        assert entity.parent_topic_id == 5

    def test_all_fields_mapped(self):
        m = _mock_topic_model(
            description="Desc",
            scope="organization",
            organization_id=10,
            estimated_time_minutes=15,
        )
        entity = topic_model_to_entity(m)
        assert entity.description == "Desc"
        assert entity.scope == "organization"
        assert entity.organization_id == 10
        assert entity.estimated_time_minutes == 15

    def test_result_is_frozen(self):
        m = _mock_topic_model()
        entity = topic_model_to_entity(m)
        with pytest.raises(AttributeError):
            entity.name = "Changed"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════
# coding_test_case_model_to_entity
# ═══════════════════════════════════════════════════════════════════════


class TestCodingTestCaseModelToEntity:
    """Tests for coding_test_case_model_to_entity mapper."""

    def test_visible_case_full_output(self):
        m = _mock_test_case_model(is_hidden=False, expected_output="42")
        entity = coding_test_case_model_to_entity(m)
        assert entity.expected_output == "42"
        assert entity.is_hidden is False

    def test_hidden_case_output_masked(self):
        """Hidden test cases mask expected_output by default."""
        m = _mock_test_case_model(is_hidden=True, expected_output="secret")
        entity = coding_test_case_model_to_entity(m)
        assert entity.expected_output is None  # masked
        assert entity.is_hidden is True

    def test_hidden_case_output_included_when_requested(self):
        """include_hidden_output=True reveals hidden test case output."""
        m = _mock_test_case_model(is_hidden=True, expected_output="secret")
        entity = coding_test_case_model_to_entity(m, include_hidden_output=True)
        assert entity.expected_output == "secret"

    def test_weight_converted_to_float(self):
        from decimal import Decimal
        m = _mock_test_case_model(weight=Decimal("2.5"))
        entity = coding_test_case_model_to_entity(m)
        assert entity.weight == 2.5
        assert isinstance(entity.weight, float)

    def test_result_type(self):
        m = _mock_test_case_model()
        entity = coding_test_case_model_to_entity(m)
        assert isinstance(entity, CodingTestCaseEntity)


# ═══════════════════════════════════════════════════════════════════════
# coding_problem_model_to_entity
# ═══════════════════════════════════════════════════════════════════════


class TestCodingProblemModelToEntity:
    """Tests for coding_problem_model_to_entity mapper."""

    def test_basic_conversion(self):
        m = _mock_coding_problem_model()
        entity = coding_problem_model_to_entity(m)
        assert isinstance(entity, CodingProblemEntity)
        assert entity.id == 1
        assert entity.title == "Two Sum"
        assert entity.difficulty == "easy"

    def test_no_test_cases(self):
        m = _mock_coding_problem_model()
        entity = coding_problem_model_to_entity(m, test_cases=None)
        assert entity.test_cases == []

    def test_with_test_cases_hidden_masked(self):
        m = _mock_coding_problem_model()
        tc1 = _mock_test_case_model(id=1, is_hidden=False, expected_output="3")
        tc2 = _mock_test_case_model(id=2, is_hidden=True, expected_output="secret")

        entity = coding_problem_model_to_entity(m, test_cases=[tc1, tc2])
        assert len(entity.test_cases) == 2
        assert entity.test_cases[0].expected_output == "3"
        assert entity.test_cases[1].expected_output is None  # masked

    def test_with_test_cases_hidden_included(self):
        m = _mock_coding_problem_model()
        tc = _mock_test_case_model(is_hidden=True, expected_output="secret")

        entity = coding_problem_model_to_entity(
            m, test_cases=[tc], include_hidden_output=True
        )
        assert entity.test_cases[0].expected_output == "secret"

    def test_json_fields_default_empty(self):
        m = _mock_coding_problem_model(
            examples=None,
            constraints_structured=None,
            hints=None,
            code_snippets=None,
        )
        entity = coding_problem_model_to_entity(m)
        assert entity.examples == []
        assert entity.constraints_structured == []
        assert entity.hints == []
        assert entity.code_snippets == {}

    def test_all_scalar_fields(self):
        m = _mock_coding_problem_model(
            source_slug="two-sum",
            stats={"acceptance": 48.5},
        )
        entity = coding_problem_model_to_entity(m)
        assert entity.source_slug == "two-sum"
        assert entity.stats["acceptance"] == 48.5

    def test_result_is_frozen(self):
        m = _mock_coding_problem_model()
        entity = coding_problem_model_to_entity(m)
        with pytest.raises(AttributeError):
            entity.title = "Changed"  # type: ignore[misc]

