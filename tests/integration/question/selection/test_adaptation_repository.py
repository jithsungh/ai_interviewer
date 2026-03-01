"""
Integration Tests — AdaptationLogRepository (PostgreSQL)

Tests INSERT and read operations on difficulty_adaptation_log table.

Requires: Running PostgreSQL with the DEV-38 migration applied.
"""

import os
from datetime import datetime

import dotenv
import pytest

dotenv.load_dotenv()

pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None and os.getenv("CI") is not None,
    reason="PostgreSQL not available in CI environment",
)


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
        session.rollback()
        session.close()
        engine.dispose()
    except Exception as e:
        pytest.skip(f"Cannot connect to PostgreSQL: {e}")


@pytest.fixture()
def clean_session(db_session):
    """Session that rolls back after each test."""
    yield db_session
    db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# Adaptation Repository
# ═══════════════════════════════════════════════════════════════════════


class TestAdaptationLogRepository:
    """Integration tests for AdaptationLogRepository."""

    def test_log_decision_inserts(self, clean_session):
        from app.question.selection.contracts import AdaptationDecision
        from app.question.selection.persistence.adaptation_repository import (
            AdaptationLogRepository,
        )

        repo = AdaptationLogRepository(clean_session)
        decision = AdaptationDecision(
            submission_id=9999,
            exchange_sequence_order=1,
            previous_difficulty=None,
            previous_score=None,
            previous_question_id=None,
            adaptation_rule="first_question_in_section",
            threshold_up=80.0,
            threshold_down=50.0,
            max_difficulty_jump=1,
            next_difficulty="medium",
            adaptation_reason="first_question_in_section",
            difficulty_changed=False,
            decided_at=datetime.utcnow(),
            rule_version="1.0.0",
        )
        row_id = repo.log_decision(decision)

        # Should return a positive integer ID
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_get_by_submission(self, clean_session):
        from app.question.selection.contracts import AdaptationDecision
        from app.question.selection.persistence.adaptation_repository import (
            AdaptationLogRepository,
        )

        repo = AdaptationLogRepository(clean_session)

        # Insert two decisions for same submission
        for seq in (1, 2):
            decision = AdaptationDecision(
                submission_id=8888,
                exchange_sequence_order=seq,
                adaptation_rule="escalate",
                threshold_up=80.0,
                threshold_down=50.0,
                max_difficulty_jump=1,
                next_difficulty="hard" if seq == 2 else "medium",
                adaptation_reason="escalate" if seq == 2 else "first_question",
                difficulty_changed=seq == 2,
                decided_at=datetime.utcnow(),
                rule_version="1.0.0",
            )
            repo.log_decision(decision)

        results = repo.get_by_submission(8888)
        assert len(results) >= 2
        # Should be ordered by exchange_sequence_order
        orders = [r.exchange_sequence_order for r in results]
        assert orders == sorted(orders)

    def test_get_latest_for_submission(self, clean_session):
        from app.question.selection.contracts import AdaptationDecision
        from app.question.selection.persistence.adaptation_repository import (
            AdaptationLogRepository,
        )

        repo = AdaptationLogRepository(clean_session)

        for seq in (1, 2, 3):
            decision = AdaptationDecision(
                submission_id=7777,
                exchange_sequence_order=seq,
                adaptation_rule="maintain",
                threshold_up=80.0,
                threshold_down=50.0,
                max_difficulty_jump=1,
                next_difficulty="medium",
                adaptation_reason="maintain",
                difficulty_changed=False,
                decided_at=datetime.utcnow(),
                rule_version="1.0.0",
            )
            repo.log_decision(decision)

        latest = repo.get_latest_for_submission(7777)
        assert latest is not None
        assert latest.exchange_sequence_order == 3

    def test_get_by_nonexistent_submission(self, clean_session):
        from app.question.selection.persistence.adaptation_repository import (
            AdaptationLogRepository,
        )

        repo = AdaptationLogRepository(clean_session)
        results = repo.get_by_submission(999999)
        assert results == []
