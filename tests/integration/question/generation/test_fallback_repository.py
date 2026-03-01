"""
Integration Tests — Question Generation Module

Tests FallbackQuestionRepository against actual PostgreSQL.

Requires:
  - Running PostgreSQL (DATABASE_URL env var)
  - DEV-37 migration applied (generic_fallback_questions table)

Run via:
    .venv/bin/python -m pytest tests/integration/question/generation/ -v
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import dotenv
import pytest

dotenv.load_dotenv()

# Skip entirely when no DB in CI
pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None and os.getenv("CI") is not None,
    reason="PostgreSQL not available in CI environment",
)


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
def table_exists(db_engine):
    """Check that the generic_fallback_questions table exists; skip if not."""
    from sqlalchemy import text

    with db_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_name = 'generic_fallback_questions'"
                ")"
            )
        )
        exists = result.scalar()

    if not exists:
        pytest.skip(
            "generic_fallback_questions table does not exist — "
            "run DEV-37 migration first"
        )


@pytest.fixture
def db_session(db_engine, table_exists):
    """Provide a session-per-test that rolls back on exit."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def seed_fallbacks(db_session):
    """Insert temporary test rows. Rolled back automatically."""
    from app.question.generation.persistence.models import GenericFallbackQuestion

    rows = [
        GenericFallbackQuestion(
            question_type="technical",
            difficulty="easy",
            topic="algorithms",
            question_text="What is a binary search?",
            expected_answer="Search sorted array by halving.",
            estimated_time_seconds=90,
            is_active=True,
            usage_count=0,
        ),
        GenericFallbackQuestion(
            question_type="technical",
            difficulty="medium",
            topic="algorithms",
            question_text="Explain quicksort.",
            expected_answer="Divide-and-conquer sort.",
            estimated_time_seconds=120,
            is_active=True,
            usage_count=5,
        ),
        GenericFallbackQuestion(
            question_type="behavioral",
            difficulty="medium",
            topic="leadership",
            question_text="Describe a leadership experience.",
            expected_answer="Candidate provides structured answer.",
            estimated_time_seconds=120,
            is_active=True,
            usage_count=0,
        ),
        GenericFallbackQuestion(
            question_type="technical",
            difficulty="medium",
            topic="algorithms",
            question_text="What is a hash table?",
            expected_answer="Key-value data structure with O(1) lookup.",
            estimated_time_seconds=120,
            is_active=True,
            usage_count=10,
        ),
        GenericFallbackQuestion(
            question_type="technical",
            difficulty="hard",
            topic="databases",
            question_text="Explain MVCC.",
            expected_answer="Multi-Version Concurrency Control.",
            estimated_time_seconds=180,
            is_active=False,  # inactive
            usage_count=0,
        ),
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


# ════════════════════════════════════════════════════════════════════════════
# FallbackQuestionRepository Integration Tests
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestFallbackRepositoryIntegration:
    """Repository integration tests against real PostgreSQL."""

    def test_table_exists(self, db_session):
        """Verify the generic_fallback_questions table is accessible."""
        from sqlalchemy import text

        result = db_session.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_name = 'generic_fallback_questions'"
                ")"
            )
        )
        assert result.scalar() is True

    def test_get_by_difficulty_and_topic(self, db_session, seed_fallbacks):
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)
        fb = repo.get_by_difficulty_and_topic("medium", "algorithms")

        assert fb is not None
        assert fb.difficulty == "medium"
        assert fb.topic == "algorithms"
        # Should return least-used (usage_count=5 before 10)
        assert fb.question_text == "Explain quicksort."

    def test_get_by_difficulty_and_topic_no_match(self, db_session, seed_fallbacks):
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)
        fb = repo.get_by_difficulty_and_topic("hard", "algorithms")

        # No active hard+algorithms in seed data
        assert fb is None

    def test_get_by_difficulty(self, db_session, seed_fallbacks):
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)
        fb = repo.get_by_difficulty("easy")

        assert fb is not None
        assert fb.difficulty == "easy"

    def test_get_any_active(self, db_session, seed_fallbacks):
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)
        fb = repo.get_any_active()

        assert fb is not None
        assert fb.is_active is True

    def test_get_any_active_excludes_inactive(self, db_session, seed_fallbacks):
        """Inactive rows (hard/databases) should not be returned."""
        from sqlalchemy import text

        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)

        # Deactivate all active rows
        db_session.execute(
            text(
                "UPDATE generic_fallback_questions SET is_active = false "
                "WHERE is_active = true"
            )
        )
        db_session.flush()

        fb = repo.get_any_active()
        assert fb is None

    def test_increment_usage(self, db_session, seed_fallbacks):
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )
        from app.question.generation.persistence.models import GenericFallbackQuestion

        repo = FallbackQuestionRepository(db_session)

        fb = repo.get_by_difficulty_and_topic("easy", "algorithms")
        assert fb is not None
        original_count = fb.usage_count

        repo.increment_usage(fb.id)
        db_session.flush()
        db_session.expire(fb)

        refreshed = (
            db_session.query(GenericFallbackQuestion)
            .filter(GenericFallbackQuestion.id == fb.id)
            .first()
        )
        assert refreshed.usage_count == original_count + 1

    def test_least_used_ordering(self, db_session, seed_fallbacks):
        """get_by_difficulty returns the row with smallest usage_count."""
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )

        repo = FallbackQuestionRepository(db_session)
        fb = repo.get_by_difficulty("medium")

        assert fb is not None
        # leadership(0) or algorithms-quicksort(5), not hash-table(10)
        assert fb.usage_count <= 5


# ════════════════════════════════════════════════════════════════════════════
# Service + Repository Integration Test
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestServiceFallbackIntegration:
    """
    End-to-end: Service with mocked LLM but real DB fallback.
    Proves the service→repo→DB chain works under failure conditions.
    """

    @pytest.mark.asyncio
    async def test_service_uses_real_fallback_on_llm_failure(
        self, db_session, seed_fallbacks
    ):
        from app.ai.llm.errors import LLMProviderError
        from app.ai.prompts.entities import RenderedPrompt
        from app.question.generation.contracts import GenerationRequest, GenerationStatus
        from app.question.generation.persistence.fallback_repository import (
            FallbackQuestionRepository,
        )
        from app.question.generation.service import QuestionGenerationService

        # LLM always fails
        llm_provider = AsyncMock()
        llm_provider.generate_structured = AsyncMock(
            side_effect=LLMProviderError(provider="groq", message="fail")
        )
        llm_provider.get_provider_name = MagicMock(return_value="groq")

        # Prompt service returns a valid prompt (no real DB lookup needed)
        prompt_service = MagicMock()
        prompt_service.get_rendered_prompt = MagicMock(
            return_value=RenderedPrompt(
                text="Generate a question.",
                system_prompt="You are an interviewer.",
                model_config={"model": "llama-3.3-70b-versatile"},
                version=1,
                prompt_type="question_generation",
            )
        )

        repo = FallbackQuestionRepository(db_session)
        svc = QuestionGenerationService(
            llm_provider=llm_provider,
            prompt_service=prompt_service,
            fallback_repo=repo,
        )

        request = GenerationRequest(
            submission_id=1,
            organization_id=42,
            difficulty="medium",
            topic="algorithms",
            max_retries=1,  # Minimize retries for speed
        )

        result = await svc.generate(request)

        assert result.status == GenerationStatus.FALLBACK_USED
        assert result.source_type == "fallback_generic"
        assert result.question_text is not None
        assert result.fallback_question_id is not None
