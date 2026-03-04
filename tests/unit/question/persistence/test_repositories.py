"""
Unit Tests — Question Persistence Repositories

Tests QuestionRepository, TopicRepository, and CodingProblemRepository
with mocked SQLAlchemy sessions (no real DB).

Validates:
- Multi-tenant filter construction
- Query method parameter handling
- Batch loading logic
- Entity mapping integration
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call

from app.question.persistence.repositories import (
    CodingProblemRepository,
    QuestionRepository,
    TopicRepository,
)
from app.question.persistence.entities import (
    CodingProblemEntity,
    QuestionEntity,
    TopicEntity,
)


# ── Factory helpers ────────────────────────────────────────────────


def _mock_session():
    """Create a mock SQLAlchemy session with chainable query methods."""
    session = MagicMock()
    # Make query().filter().first() etc. chainable
    query_mock = MagicMock()
    session.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.limit.return_value = query_mock
    return session


def _mock_question_model(**overrides):
    """Create a mock QuestionModel row."""
    m = MagicMock()
    defaults = dict(
        id=1,
        question_text="What is OOP?",
        answer_text="Object-oriented programming.",
        question_type="technical",
        difficulty="medium",
        scope="public",
        organization_id=None,
        source_type=None,
        estimated_time_minutes=5,
        is_active=True,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_topic_model(**overrides):
    """Create a mock TopicModel row."""
    m = MagicMock()
    defaults = dict(
        id=1,
        name="Algorithms",
        description="Core algorithms.",
        parent_topic_id=None,
        scope="public",
        organization_id=None,
        estimated_time_minutes=10,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_coding_problem_model(**overrides):
    """Create a mock CodingProblemModel row."""
    m = MagicMock()
    defaults = dict(
        id=1,
        title="Two Sum",
        body="Given an array...",
        difficulty="easy",
        scope="public",
        organization_id=None,
        description="Find two numbers.",
        constraints=None,
        estimated_time_minutes=30,
        is_active=True,
        source_name="leetcode",
        source_id="1",
        source_slug="two-sum",
        raw_content=None,
        examples=[],
        constraints_structured=[],
        hints=[],
        stats=None,
        code_snippets={"python": "def twoSum():"},
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ═══════════════════════════════════════════════════════════════════════
# QuestionRepository
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionRepositoryInit:
    """Tests for QuestionRepository construction."""

    def test_accepts_session(self):
        session = MagicMock()
        repo = QuestionRepository(session)
        assert repo._session is session


class TestQuestionRepositoryGetById:
    """Tests for QuestionRepository.get_by_id()."""

    def test_returns_entity_when_found(self):
        session = _mock_session()
        row = _mock_question_model(id=42)
        session.query.return_value.filter.return_value.first.return_value = row
        # Mock topic loading to return empty
        session.query.return_value.filter.return_value.all.return_value = []

        repo = QuestionRepository(session)

        # Patch _load_topic_ids to avoid complex query chain
        with patch.object(repo, "_load_topic_ids", return_value={42: [1, 2]}):
            result = repo.get_by_id(question_id=42, organization_id=1)

        assert result is not None
        assert isinstance(result, QuestionEntity)
        assert result.id == 42
        assert result.topic_ids == [1, 2]

    def test_returns_none_when_not_found(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        repo = QuestionRepository(session)
        result = repo.get_by_id(question_id=999, organization_id=1)
        assert result is None


class TestQuestionRepositoryFilterByCriteria:
    """Tests for QuestionRepository.filter_by_criteria()."""

    def test_returns_list_of_entities(self):
        session = _mock_session()
        rows = [
            _mock_question_model(id=1),
            _mock_question_model(id=2),
        ]
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = rows

        repo = QuestionRepository(session)
        with patch.object(repo, "_load_topic_ids", return_value={1: [10], 2: [20]}):
            results = repo.filter_by_criteria(organization_id=1)

        assert len(results) == 2
        assert all(isinstance(r, QuestionEntity) for r in results)

    def test_empty_results(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        repo = QuestionRepository(session)
        with patch.object(repo, "_load_topic_ids", return_value={}):
            results = repo.filter_by_criteria(organization_id=1)

        assert results == []


class TestQuestionRepositoryGetRandom:
    """Tests for QuestionRepository.get_random()."""

    def test_returns_entities(self):
        session = _mock_session()
        row = _mock_question_model(id=7)
        session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [row]

        repo = QuestionRepository(session)
        with patch.object(repo, "_load_topic_ids", return_value={7: []}):
            results = repo.get_random(organization_id=1, limit=1)

        assert len(results) == 1
        assert results[0].id == 7

    def test_excludes_ids(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        repo = QuestionRepository(session)
        with patch.object(repo, "_load_topic_ids", return_value={}):
            results = repo.get_random(
                organization_id=1, exclude_ids=[1, 2, 3], limit=5
            )

        assert results == []


class TestQuestionRepositoryBatchGet:
    """Tests for QuestionRepository.get_by_ids_batch()."""

    def test_returns_dict(self):
        session = _mock_session()
        rows = [_mock_question_model(id=10), _mock_question_model(id=20)]
        session.query.return_value.filter.return_value.all.return_value = rows

        repo = QuestionRepository(session)
        with patch.object(repo, "_load_topic_ids", return_value={10: [], 20: []}):
            result = repo.get_by_ids_batch([10, 20], organization_id=1)

        assert isinstance(result, dict)
        assert 10 in result
        assert 20 in result

    def test_empty_input_returns_empty_dict(self):
        session = _mock_session()
        repo = QuestionRepository(session)
        result = repo.get_by_ids_batch([], organization_id=1)
        assert result == {}


class TestQuestionRepositoryCount:
    """Tests for QuestionRepository.count_available()."""

    def test_count_returns_int(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.scalar.return_value = 42

        repo = QuestionRepository(session)
        count = repo.count_available(organization_id=1)
        assert count == 42

    def test_count_returns_zero_for_none(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.scalar.return_value = None

        repo = QuestionRepository(session)
        count = repo.count_available(organization_id=1)
        assert count == 0


class TestQuestionRepositoryLoadTopicIds:
    """Tests for QuestionRepository._load_topic_ids()."""

    def test_empty_ids_returns_empty(self):
        session = _mock_session()
        repo = QuestionRepository(session)
        result = repo._load_topic_ids([])
        assert result == {}

    def test_groups_by_question_id(self):
        session = _mock_session()
        # Simulate junction table rows
        session.query.return_value.filter.return_value.all.return_value = [
            (1, 10),
            (1, 20),
            (2, 30),
        ]
        repo = QuestionRepository(session)
        result = repo._load_topic_ids([1, 2])
        assert result == {1: [10, 20], 2: [30]}


# ═══════════════════════════════════════════════════════════════════════
# TopicRepository
# ═══════════════════════════════════════════════════════════════════════


class TestTopicRepositoryGetById:
    """Tests for TopicRepository.get_by_id()."""

    def test_returns_entity(self):
        session = MagicMock()
        row = _mock_topic_model(id=5, name="Sorting")
        session.get.return_value = row

        repo = TopicRepository(session)
        result = repo.get_by_id(topic_id=5)

        assert result is not None
        assert isinstance(result, TopicEntity)
        assert result.name == "Sorting"

    def test_returns_none_when_not_found(self):
        session = MagicMock()
        session.get.return_value = None

        repo = TopicRepository(session)
        result = repo.get_by_id(topic_id=999)
        assert result is None


class TestTopicRepositoryResolvePath:
    """Tests for TopicRepository.resolve_topic_path()."""

    def test_single_topic_no_parent(self):
        session = MagicMock()
        repo = TopicRepository(session)

        # Mock get_ancestors to return just the topic itself
        with patch.object(repo, "get_ancestors", return_value=[1]):
            root = _mock_topic_model(id=1, name="Technical")
            with patch.object(repo, "get_by_id", return_value=TopicEntity(
                id=1, name="Technical", description=None, parent_topic_id=None,
                scope="public", organization_id=None,
            )):
                path = repo.resolve_topic_path(topic_id=1)

        assert path == "Technical"

    def test_nested_path(self):
        session = MagicMock()
        repo = TopicRepository(session)

        # Simulate: Sorting → Algorithms → Technical (leaf-to-root)
        with patch.object(repo, "get_ancestors", return_value=[5, 2, 1]):
            entities = {
                1: TopicEntity(id=1, name="Technical", description=None, parent_topic_id=None, scope="public", organization_id=None),
                2: TopicEntity(id=2, name="Algorithms", description=None, parent_topic_id=1, scope="public", organization_id=None),
                5: TopicEntity(id=5, name="Sorting", description=None, parent_topic_id=2, scope="public", organization_id=None),
            }
            with patch.object(repo, "get_by_id", side_effect=lambda tid: entities.get(tid)):
                path = repo.resolve_topic_path(topic_id=5)

        assert path == "Technical > Algorithms > Sorting"


class TestTopicRepositoryListByOrganization:
    """Tests for TopicRepository.list_by_organization()."""

    def test_returns_entities(self):
        session = _mock_session()
        rows = [_mock_topic_model(id=1), _mock_topic_model(id=2)]
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = rows

        repo = TopicRepository(session)
        results = repo.list_by_organization(organization_id=1)

        assert len(results) == 2
        assert all(isinstance(r, TopicEntity) for r in results)


class TestTopicRepositoryGetTopicTree:
    """Tests for TopicRepository.get_topic_tree()."""

    def test_full_tree_builds_hierarchy(self):
        session = _mock_session()
        rows = [
            _mock_topic_model(id=1, name="Technical", parent_topic_id=None),
            _mock_topic_model(id=2, name="Algorithms", parent_topic_id=1),
            _mock_topic_model(id=3, name="Sorting", parent_topic_id=2),
        ]
        session.query.return_value.all.return_value = rows

        repo = TopicRepository(session)
        tree = repo.get_topic_tree(root_topic_id=None)

        assert len(tree) == 1  # Only root
        assert tree[0]["name"] == "Technical"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["name"] == "Algorithms"
        assert len(tree[0]["children"][0]["children"]) == 1
        assert tree[0]["children"][0]["children"][0]["name"] == "Sorting"


# ═══════════════════════════════════════════════════════════════════════
# CodingProblemRepository
# ═══════════════════════════════════════════════════════════════════════


class TestCodingProblemRepositoryGetById:
    """Tests for CodingProblemRepository.get_by_id()."""

    def test_returns_entity_with_test_cases(self):
        session = _mock_session()
        row = _mock_coding_problem_model(id=10)
        session.query.return_value.filter.return_value.first.return_value = row

        tc = MagicMock()
        tc.id = 1
        tc.coding_problem_id = 10
        tc.input_data = "[1]"
        tc.expected_output = "1"
        tc.is_hidden = False
        tc.weight = 1.0
        session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [tc]

        repo = CodingProblemRepository(session)
        result = repo.get_by_id(problem_id=10, organization_id=1)

        assert result is not None
        assert isinstance(result, CodingProblemEntity)
        assert result.id == 10
        assert len(result.test_cases) == 1

    def test_returns_none_when_not_found(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        repo = CodingProblemRepository(session)
        result = repo.get_by_id(problem_id=999, organization_id=1)
        assert result is None


class TestCodingProblemRepositoryFilterByCriteria:
    """Tests for CodingProblemRepository.filter_by_criteria()."""

    def test_returns_list(self):
        session = _mock_session()
        rows = [_mock_coding_problem_model(id=1), _mock_coding_problem_model(id=2)]
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = rows

        repo = CodingProblemRepository(session)
        results = repo.filter_by_criteria(organization_id=1)

        assert len(results) == 2
        assert all(isinstance(r, CodingProblemEntity) for r in results)

    def test_empty_results(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        repo = CodingProblemRepository(session)
        results = repo.filter_by_criteria(organization_id=1)
        assert results == []


class TestCodingProblemRepositoryGetStarterCode:
    """Tests for CodingProblemRepository.get_starter_code()."""

    def test_returns_code_for_language(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = (
            {"python": "def solution():", "java": "class Solution {}"},
        )

        repo = CodingProblemRepository(session)
        code = repo.get_starter_code(problem_id=1, language="python")
        assert code == "def solution():"

    def test_returns_none_for_missing_language(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = (
            {"python": "def solution():"},
        )

        repo = CodingProblemRepository(session)
        code = repo.get_starter_code(problem_id=1, language="rust")
        assert code is None

    def test_returns_none_for_missing_problem(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        repo = CodingProblemRepository(session)
        code = repo.get_starter_code(problem_id=999, language="python")
        assert code is None

    def test_returns_none_for_null_snippets(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = (None,)

        repo = CodingProblemRepository(session)
        code = repo.get_starter_code(problem_id=1, language="python")
        assert code is None


class TestCodingProblemRepositoryCount:
    """Tests for CodingProblemRepository.count_available()."""

    def test_count_returns_int(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.scalar.return_value = 15

        repo = CodingProblemRepository(session)
        count = repo.count_available(organization_id=1)
        assert count == 15

    def test_count_returns_zero_for_none(self):
        session = _mock_session()
        session.query.return_value.filter.return_value.scalar.return_value = None

        repo = CodingProblemRepository(session)
        count = repo.count_available(organization_id=1)
        assert count == 0

