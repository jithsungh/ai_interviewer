"""
Integration Tests — QuestionReadRepository (PostgreSQL Fallback)

Tests read-only question queries against actual PostgreSQL instance.

Requires: Running PostgreSQL with seeded question data.
"""

import os

import dotenv
import pytest

dotenv.load_dotenv()

# Skip if no database URL
pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None and os.getenv("CI") is not None,
    reason="PostgreSQL not available in CI environment",
)

ORG_ID = 1  # Must match seeded data


@pytest.fixture(scope="module")
def db_session():
    """Provide a SQLAlchemy session connected to test database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        engine.dispose()
    except Exception as e:
        pytest.skip(f"Cannot connect to PostgreSQL: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Read-Only Queries
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionReadRepository:
    """Integration tests for QuestionReadRepository."""

    def test_count_available(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        count = repo.count_available(organization_id=ORG_ID)
        # Should return an integer >= 0
        assert isinstance(count, int)
        assert count >= 0

    def test_get_random_returns_list(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        results = repo.get_random(
            organization_id=ORG_ID,
            difficulty=None,
            exclude_ids=None,
            limit=5,
        )
        assert isinstance(results, list)
        # All returned items should be QuestionCandidate
        for c in results:
            assert c.question_id > 0
            assert c.similarity_score == 0.0  # No vector search

    def test_get_by_id_nonexistent(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        result = repo.get_by_id(question_id=999999, organization_id=ORG_ID)
        assert result is None

    def test_filter_by_difficulty(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        results = repo.filter_by_criteria(
            organization_id=ORG_ID,
            difficulty="medium",
            limit=10,
        )
        for c in results:
            assert c.difficulty == "medium"

    def test_exclude_ids(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        # First get some question IDs
        all_qs = repo.get_random(
            organization_id=ORG_ID, limit=3
        )
        if len(all_qs) < 2:
            pytest.skip("Not enough questions in DB")

        exclude = [all_qs[0].question_id]
        results = repo.filter_by_criteria(
            organization_id=ORG_ID,
            exclude_ids=exclude,
            limit=50,
        )
        returned_ids = {c.question_id for c in results}
        assert exclude[0] not in returned_ids

    def test_batch_get_preserves_order(self, db_session):
        from app.question.retrieval.persistence.question_read_repository import (
            QuestionReadRepository,
        )

        repo = QuestionReadRepository(db_session)
        all_qs = repo.get_random(organization_id=ORG_ID, limit=3)
        if len(all_qs) < 2:
            pytest.skip("Not enough questions in DB")

        ids = [c.question_id for c in all_qs]
        batch = repo.get_by_ids_batch(ids, organization_id=ORG_ID)
        batch_ids = [c.question_id for c in batch]
        assert batch_ids == ids
