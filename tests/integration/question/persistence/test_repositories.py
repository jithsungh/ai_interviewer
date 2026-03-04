"""
Integration Tests — Question Persistence Repositories

Tests QuestionRepository, TopicRepository, and CodingProblemRepository
against actual PostgreSQL.

Requires:
  - Running PostgreSQL (DATABASE_URL env var)
  - Seeded questions, topics, coding_problems tables

Run via:
    .venv/bin/python -m pytest tests/integration/question/persistence/ -v
"""

from __future__ import annotations

import os

import dotenv
import pytest

dotenv.load_dotenv()

# Skip entirely when no DB in CI
pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None and os.getenv("CI") is not None,
    reason="PostgreSQL not available in CI environment",
)

ORG_ID = 1  # Must match seeded data


@pytest.fixture(scope="module")
def db_engine():
    """Create a standalone SQLAlchemy engine for tests."""
    from sqlalchemy import create_engine

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    try:
        engine = create_engine(db_url, pool_pre_ping=True, pool_size=2, max_overflow=1)
        yield engine
        engine.dispose()
    except Exception as e:
        pytest.skip(f"Cannot connect to PostgreSQL: {e}")


@pytest.fixture(scope="module")
def tables_exist(db_engine):
    """Verify required tables exist; skip if not."""
    from sqlalchemy import text

    required = ["questions", "topics", "question_topics", "coding_problems", "coding_test_cases"]
    with db_engine.connect() as conn:
        for table in required:
            result = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT FROM information_schema.tables "
                    f"  WHERE table_name = '{table}'"
                    ")"
                )
            )
            if not result.scalar():
                pytest.skip(f"Table '{table}' does not exist — seeding required")


@pytest.fixture
def db_session(db_engine, tables_exist):
    """Provide a session-per-test that rolls back on exit."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ════════════════════════════════════════════════════════════════════════════
# QuestionRepository Integration Tests
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestQuestionRepositoryIntegration:
    """QuestionRepository integration tests against real PostgreSQL."""

    def test_count_available(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        count = repo.count_available(organization_id=ORG_ID)
        assert isinstance(count, int)
        assert count >= 0

    def test_filter_by_criteria_default(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        results = repo.filter_by_criteria(organization_id=ORG_ID)
        assert isinstance(results, list)
        for q in results:
            assert q.is_active is True

    def test_filter_by_difficulty(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        results = repo.filter_by_criteria(
            organization_id=ORG_ID, difficulty="medium", limit=10
        )
        for q in results:
            assert q.difficulty == "medium"

    def test_filter_by_question_type(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        results = repo.filter_by_criteria(
            organization_id=ORG_ID, question_type="technical", limit=10
        )
        for q in results:
            assert q.question_type == "technical"

    def test_get_by_id_nonexistent(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        result = repo.get_by_id(question_id=999999, organization_id=ORG_ID)
        assert result is None

    def test_get_random(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        results = repo.get_random(organization_id=ORG_ID, limit=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_get_random_with_exclude(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        all_qs = repo.get_random(organization_id=ORG_ID, limit=5)
        if len(all_qs) < 2:
            pytest.skip("Not enough questions in DB")

        exclude_id = all_qs[0].id
        results = repo.get_random(
            organization_id=ORG_ID,
            exclude_ids=[exclude_id],
            limit=50,
        )
        assert all(q.id != exclude_id for q in results)

    def test_batch_get(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        all_qs = repo.get_random(organization_id=ORG_ID, limit=3)
        if not all_qs:
            pytest.skip("No questions in DB")

        ids = [q.id for q in all_qs]
        batch = repo.get_by_ids_batch(ids, organization_id=ORG_ID)
        assert isinstance(batch, dict)
        for qid in ids:
            assert qid in batch

    def test_batch_get_empty_input(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        batch = repo.get_by_ids_batch([], organization_id=ORG_ID)
        assert batch == {}

    def test_topic_ids_loaded(self, db_session):
        from app.question.persistence.repositories import QuestionRepository

        repo = QuestionRepository(db_session)
        all_qs = repo.filter_by_criteria(organization_id=ORG_ID, limit=5)
        # topic_ids should be a list (possibly empty, but a list)
        for q in all_qs:
            assert isinstance(q.topic_ids, list)


# ════════════════════════════════════════════════════════════════════════════
# TopicRepository Integration Tests
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestTopicRepositoryIntegration:
    """TopicRepository integration tests against real PostgreSQL."""

    def test_list_by_organization(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        topics = repo.list_by_organization(organization_id=ORG_ID)
        assert isinstance(topics, list)
        for t in topics:
            assert t.name is not None

    def test_get_by_id_nonexistent(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        result = repo.get_by_id(topic_id=999999)
        assert result is None

    def test_get_topic_tree(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        tree = repo.get_topic_tree()
        assert isinstance(tree, list)
        for node in tree:
            assert "id" in node
            assert "name" in node
            assert "children" in node

    def test_get_descendants(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        topics = repo.list_by_organization(organization_id=ORG_ID, limit=1)
        if not topics:
            pytest.skip("No topics in DB")

        descendants = repo.get_descendants(topics[0].id)
        assert isinstance(descendants, list)
        assert topics[0].id in descendants  # Inclusive

    def test_get_ancestors(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        topics = repo.list_by_organization(organization_id=ORG_ID, limit=1)
        if not topics:
            pytest.skip("No topics in DB")

        ancestors = repo.get_ancestors(topics[0].id)
        assert isinstance(ancestors, list)
        assert topics[0].id in ancestors  # Inclusive

    def test_resolve_topic_path(self, db_session):
        from app.question.persistence.repositories import TopicRepository

        repo = TopicRepository(db_session)
        topics = repo.list_by_organization(organization_id=ORG_ID, limit=1)
        if not topics:
            pytest.skip("No topics in DB")

        path = repo.resolve_topic_path(topics[0].id)
        assert isinstance(path, str)
        assert len(path) > 0


# ════════════════════════════════════════════════════════════════════════════
# CodingProblemRepository Integration Tests
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestCodingProblemRepositoryIntegration:
    """CodingProblemRepository integration tests against real PostgreSQL."""

    def test_count_available(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        count = repo.count_available(organization_id=ORG_ID)
        assert isinstance(count, int)
        assert count >= 0

    def test_filter_by_criteria_default(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        results = repo.filter_by_criteria(organization_id=ORG_ID)
        assert isinstance(results, list)

    def test_filter_by_difficulty(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        results = repo.filter_by_criteria(
            organization_id=ORG_ID, difficulty="easy", limit=5
        )
        for p in results:
            assert p.difficulty == "easy"

    def test_get_by_id_nonexistent(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        result = repo.get_by_id(problem_id=999999, organization_id=ORG_ID)
        assert result is None

    def test_get_by_id_with_test_cases(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        problems = repo.filter_by_criteria(organization_id=ORG_ID, limit=1)
        if not problems:
            pytest.skip("No coding problems in DB")

        full = repo.get_by_id(problem_id=problems[0].id, organization_id=ORG_ID)
        assert full is not None
        assert isinstance(full.test_cases, list)

    def test_hidden_test_case_masking(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        problems = repo.filter_by_criteria(organization_id=ORG_ID, limit=1)
        if not problems:
            pytest.skip("No coding problems in DB")

        # Default: hidden outputs are masked
        full = repo.get_by_id(
            problem_id=problems[0].id,
            organization_id=ORG_ID,
            include_hidden=False,
        )
        for tc in full.test_cases:
            if tc.is_hidden:
                assert tc.expected_output is None

    def test_hidden_test_case_unmasked(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        problems = repo.filter_by_criteria(organization_id=ORG_ID, limit=1)
        if not problems:
            pytest.skip("No coding problems in DB")

        # include_hidden=True: all outputs visible
        full = repo.get_by_id(
            problem_id=problems[0].id,
            organization_id=ORG_ID,
            include_hidden=True,
        )
        for tc in full.test_cases:
            # When included, expected_output should be a string
            assert isinstance(tc.expected_output, str)

    def test_get_starter_code(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        problems = repo.filter_by_criteria(organization_id=ORG_ID, limit=1)
        if not problems:
            pytest.skip("No coding problems in DB")

        code = repo.get_starter_code(problem_id=problems[0].id, language="python")
        # May be None if no Python snippet exists — that's OK
        assert code is None or isinstance(code, str)

    def test_get_starter_code_nonexistent(self, db_session):
        from app.question.persistence.repositories import CodingProblemRepository

        repo = CodingProblemRepository(db_session)
        code = repo.get_starter_code(problem_id=999999, language="python")
        assert code is None

