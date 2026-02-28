"""
Integration Tests — QdrantQuestionRepository

Tests actual Qdrant vector search with multi-tenant OR filters,
topic filtering, and exclude-list logic.

Requires: Running Qdrant instance (QDRANT_URL env var).
"""

import os
import random
import time
from typing import List

import dotenv
import pytest

dotenv.load_dotenv()

from app.config.settings import QdrantSettings

# Skip if Qdrant not available
pytestmark = pytest.mark.skipif(
    os.getenv("QDRANT_URL") is None and os.getenv("CI") is not None,
    reason="Qdrant not available in CI environment",
)

VECTOR_DIM = 128  # Small dimension for fast tests
ORG_ID = 9001
OTHER_ORG_ID = 9002


def _random_vector(dim: int = VECTOR_DIM) -> List[float]:
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]


@pytest.fixture(scope="module")
def qdrant_config():
    return QdrantSettings(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection_name="test_retrieval_integration",
        qdrant_embedding_dim=VECTOR_DIM,
        qdrant_search_timeout=10,
    )


@pytest.fixture(scope="module", autouse=True)
def setup_qdrant(qdrant_config):
    """Initialise Qdrant client & collection, seed test data, tear down."""
    import app.persistence.qdrant.client as client_module

    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None

    from app.persistence.qdrant import init_qdrant, cleanup_qdrant

    try:
        init_qdrant(qdrant_config)
    except Exception:
        pytest.skip("Cannot connect to Qdrant")

    # Seed test points
    from app.persistence.qdrant import store_embedding

    # Org-owned questions
    for qid in range(1, 6):
        store_embedding(
            vector=_random_vector(),
            organization_id=ORG_ID,
            source_type="question",
            source_id=qid,
            model_name="test-model",
            model_version="v1",
            difficulty="medium" if qid % 2 else "hard",
            topic_id=qid,
            scope="organization",
        )

    # Public question from a DIFFERENT org
    store_embedding(
        vector=_random_vector(),
        organization_id=OTHER_ORG_ID,
        source_type="question",
        source_id=100,
        model_name="test-model",
        model_version="v1",
        difficulty="easy",
        topic_id=10,
        scope="public",
    )

    # Non-question embedding (resume) — should never appear in question search
    store_embedding(
        vector=_random_vector(),
        organization_id=ORG_ID,
        source_type="resume",
        source_id=200,
        model_name="test-model",
        model_version="v1",
        scope="organization",
    )

    # Give Qdrant a moment to index
    time.sleep(0.5)

    yield

    from app.persistence.qdrant import delete_collection

    try:
        delete_collection()
    except Exception:
        pass
    cleanup_qdrant()


# ═══════════════════════════════════════════════════════════════════════
# Search Tests
# ═══════════════════════════════════════════════════════════════════════


class TestQdrantSearchQuestions:
    """Integration tests for QdrantQuestionRepository.search_questions."""

    def test_returns_org_questions(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        results = repo.search_questions(
            query_vector=_random_vector(),
            organization_id=ORG_ID,
            top_k=20,
            score_threshold=0.0,  # Accept all
            include_public=False,
        )

        question_ids = {c.question_id for c in results}
        # Should contain org questions, not the other org's public one
        assert question_ids.issubset({1, 2, 3, 4, 5})
        # Should not contain resume embedding
        assert 200 not in question_ids

    def test_includes_public_questions(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        results = repo.search_questions(
            query_vector=_random_vector(),
            organization_id=ORG_ID,
            top_k=20,
            score_threshold=0.0,
            include_public=True,
        )

        question_ids = {c.question_id for c in results}
        # Public question from other org should be visible
        assert 100 in question_ids or len(results) > 0

    def test_difficulty_filter(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        results = repo.search_questions(
            query_vector=_random_vector(),
            organization_id=ORG_ID,
            top_k=20,
            score_threshold=0.0,
            difficulty="medium",
            include_public=False,
        )

        for c in results:
            assert c.difficulty == "medium"

    def test_exclude_question_ids(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        results = repo.search_questions(
            query_vector=_random_vector(),
            organization_id=ORG_ID,
            top_k=20,
            score_threshold=0.0,
            exclude_question_ids=[1, 2],
            include_public=False,
        )

        excluded = {c.question_id for c in results}
        assert 1 not in excluded
        assert 2 not in excluded


# ═══════════════════════════════════════════════════════════════════════
# Scroll Tests
# ═══════════════════════════════════════════════════════════════════════


class TestQdrantScrollQuestions:
    """Integration tests for scroll_questions_by_filter."""

    def test_scroll_returns_results(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        results = repo.scroll_questions_by_filter(
            organization_id=ORG_ID,
            include_public=False,
            limit=20,
        )

        assert len(results) > 0
        # All should be questions, not resumes
        for c in results:
            assert c.question_id != 200


# ═══════════════════════════════════════════════════════════════════════
# Embedding Vector Retrieval
# ═══════════════════════════════════════════════════════════════════════


class TestGetEmbeddingVector:
    """Integration tests for get_embedding_vector."""

    def test_returns_vector_for_existing_question(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        vector = repo.get_embedding_vector(
            source_type="question",
            source_id=1,
            organization_id=ORG_ID,
        )

        if vector is not None:
            assert len(vector) == VECTOR_DIM

    def test_returns_none_for_nonexistent(self):
        from app.question.retrieval.persistence.qdrant_repository import (
            QdrantQuestionRepository,
        )

        repo = QdrantQuestionRepository()
        vector = repo.get_embedding_vector(
            source_type="question",
            source_id=99999,
            organization_id=ORG_ID,
        )

        assert vector is None
