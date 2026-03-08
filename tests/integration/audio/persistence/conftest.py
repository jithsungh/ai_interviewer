"""
Shared fixtures for audio/persistence integration tests.

Requires a running PostgreSQL instance with the interviewer schema applied.
Seeds the FK parent chain so audio_analytics rows can be inserted.

Database URL defaults to the test-cluster address; override via
``TEST_DATABASE_URL``.
"""

import os
import uuid
import pytest
from sqlalchemy import text, Table, Column, BigInteger, Integer, Text, Boolean, Numeric, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    cleanup_postgres,
    get_engine,
)
from app.persistence.postgres.base import Base
from app.persistence.postgres.session import (
    init_session_factory,
    get_session_factory,
)


# ---------------------------------------------------------------------------
# Module-scoped: one engine + session-factory per test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def postgres_config():
    """Test PostgreSQL configuration."""
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:interviewer%40password@100.95.213.103/interviewer",
    )
    return DatabaseSettings(
        database_url=database_url,
        db_pool_size=5,
        db_max_overflow=2,
        db_pool_timeout=10,
        db_query_timeout=30,
        db_echo=False,
    )


@pytest.fixture(scope="module")
def initialized_postgres(postgres_config):
    """
    Initialize PostgreSQL engine + session factory once per module.

    Registers stub tables for FK targets that have no ORM model imported,
    and applies the audio-persistence migration idempotently.
    """
    init_postgres(postgres_config)
    init_session_factory()

    _meta = Base.metadata

    if "interview_exchanges" not in _meta.tables:
        Table(
            "interview_exchanges",
            _meta,
            Column("id", BigInteger, primary_key=True),
            Column("interview_submission_id", BigInteger, nullable=False),
            Column("sequence_order", Integer, nullable=False),
            Column("question_text", Text, nullable=False),
            Column("coding_problem_id", BigInteger, nullable=True),
            Column("difficulty_at_time", Text, nullable=True),
            Column("created_at", TIMESTAMP(timezone=True), nullable=False),
            keep_existing=True,
        )

    # Apply audio-persistence migration idempotently
    engine = get_engine()
    _migration_sql = [
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS transcript_finalized BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS language_detected VARCHAR(10) DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS speech_state VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS pause_duration_ms INTEGER DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS long_pause_count INTEGER DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS filler_rate NUMERIC(5,2) DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS hesitation_detected BOOLEAN DEFAULT false",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS frustration_detected BOOLEAN DEFAULT false",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS audio_quality_score NUMERIC(3,2) DEFAULT NULL",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS background_noise_detected BOOLEAN DEFAULT false",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
        "ALTER TABLE public.audio_analytics ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP WITH TIME ZONE DEFAULT NULL",
        "CREATE INDEX IF NOT EXISTS idx_audio_analytics_finalized ON public.audio_analytics (transcript_finalized) WHERE transcript_finalized = true",
    ]
    with engine.connect() as conn:
        for stmt in _migration_sql:
            conn.execute(text(stmt))
            conn.commit()

    yield
    cleanup_postgres()


# ---------------------------------------------------------------------------
# Function-scoped: one session per test, always rolled back
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(initialized_postgres):
    """Provide a transactional session — always rolled back."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def _unique_suffix():
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def seed_organization(db_session, _unique_suffix):
    result = db_session.execute(
        text("INSERT INTO organizations (name, organization_type) VALUES (:name, :org_type) RETURNING id"),
        {"name": f"Test Org {_unique_suffix}", "org_type": "company"},
    )
    org_id = result.scalar_one()
    db_session.flush()
    return org_id


@pytest.fixture()
def seed_admin_user(db_session, _unique_suffix):
    result = db_session.execute(
        text("INSERT INTO users (name, email, password_hash, user_type) VALUES (:name, :email, :pw, :utype) RETURNING id"),
        {"name": "Admin Seed", "email": f"admin-{_unique_suffix}@seed.test", "pw": "$2b$12$seedroundhashdataforinttesting", "utype": "admin"},
    )
    user_id = result.scalar_one()
    db_session.flush()
    return user_id


@pytest.fixture()
def seed_admin(db_session, seed_admin_user, seed_organization):
    result = db_session.execute(
        text("INSERT INTO admins (user_id, organization_id, role) VALUES (:uid, :oid, :role) RETURNING id"),
        {"uid": seed_admin_user, "oid": seed_organization, "role": "admin"},
    )
    admin_id = result.scalar_one()
    db_session.flush()
    return admin_id


@pytest.fixture()
def seed_candidate_user(db_session, _unique_suffix):
    result = db_session.execute(
        text("INSERT INTO users (name, email, password_hash, user_type) VALUES (:name, :email, :pw, :utype) RETURNING id"),
        {"name": "Candidate Seed", "email": f"candidate-{_unique_suffix}@seed.test", "pw": "$2b$12$seedroundhashdataforinttesting", "utype": "candidate"},
    )
    user_id = result.scalar_one()
    db_session.flush()
    return user_id


@pytest.fixture()
def seed_candidate(db_session, seed_candidate_user):
    result = db_session.execute(
        text("INSERT INTO candidates (user_id) VALUES (:uid) RETURNING id"),
        {"uid": seed_candidate_user},
    )
    candidate_id = result.scalar_one()
    db_session.flush()
    return candidate_id


@pytest.fixture()
def seed_role(db_session, _unique_suffix):
    result = db_session.execute(
        text("INSERT INTO roles (name, scope) VALUES (:name, :scope) RETURNING id"),
        {"name": f"Role {_unique_suffix}", "scope": "public"},
    )
    role_id = result.scalar_one()
    db_session.flush()
    return role_id


@pytest.fixture()
def seed_template(db_session, _unique_suffix):
    result = db_session.execute(
        text("INSERT INTO interview_templates (name, scope, template_structure) VALUES (:name, :scope, :ts) RETURNING id"),
        {"name": f"Template {_unique_suffix}", "scope": "public", "ts": '{"sections":[]}'},
    )
    template_id = result.scalar_one()
    db_session.flush()
    return template_id


@pytest.fixture()
def seed_window(db_session, seed_organization, seed_admin, _unique_suffix):
    result = db_session.execute(
        text(
            "INSERT INTO interview_submission_windows "
            "(organization_id, admin_id, name, scope, start_time, end_time, timezone) "
            "VALUES (:oid, :aid, :name, :scope, :start, :stop, :tz) RETURNING id"
        ),
        {
            "oid": seed_organization, "aid": seed_admin,
            "name": f"Window {_unique_suffix}", "scope": "global",
            "start": "2025-01-01T00:00:00Z", "stop": "2026-12-31T23:59:59Z", "tz": "UTC",
        },
    )
    window_id = result.scalar_one()
    db_session.flush()
    return window_id


@pytest.fixture()
def seed_submission(db_session, seed_candidate, seed_window, seed_role, seed_template):
    result = db_session.execute(
        text(
            "INSERT INTO interview_submissions (candidate_id, window_id, role_id, template_id) "
            "VALUES (:cid, :wid, :rid, :tid) RETURNING id"
        ),
        {"cid": seed_candidate, "wid": seed_window, "rid": seed_role, "tid": seed_template},
    )
    submission_id = result.scalar_one()
    db_session.flush()
    return submission_id


@pytest.fixture()
def seed_question(db_session, _unique_suffix):
    """Insert a minimal question for FK references."""
    db_session.execute(text(
        "SELECT setval('questions_id_seq', COALESCE((SELECT MAX(id) FROM questions), 0))"
    ))
    result = db_session.execute(
        text(
            "INSERT INTO questions (question_text, question_type, difficulty, scope) "
            "VALUES (:qt, :qtype, :diff, :scope) RETURNING id"
        ),
        {"qt": f"Question {_unique_suffix}", "qtype": "behavioral", "diff": "easy", "scope": "public"},
    )
    question_id = result.scalar_one()
    db_session.flush()
    return question_id


@pytest.fixture()
def seed_exchange(db_session, seed_submission, seed_question):
    """Insert a minimal interview exchange for audio analytics."""
    result = db_session.execute(
        text(
            "INSERT INTO interview_exchanges "
            "(interview_submission_id, sequence_order, question_id, question_text, difficulty_at_time) "
            "VALUES (:isid, :seq, :qid, :qt, :dat) RETURNING id"
        ),
        {"isid": seed_submission, "seq": 1, "qid": seed_question, "qt": "Describe your experience.", "dat": "easy"},
    )
    exchange_id = result.scalar_one()
    db_session.flush()
    return exchange_id


@pytest.fixture()
def seed_exchange_pair(db_session, seed_submission, seed_question):
    """Insert two exchanges for the same submission."""
    ids = []
    for seq in (1, 2):
        result = db_session.execute(
            text(
                "INSERT INTO interview_exchanges "
                "(interview_submission_id, sequence_order, question_id, question_text, difficulty_at_time) "
                "VALUES (:isid, :seq, :qid, :qt, :dat) RETURNING id"
            ),
            {"isid": seed_submission, "seq": seq, "qid": seed_question, "qt": f"Question {seq}", "dat": "easy"},
        )
        ids.append(result.scalar_one())
    db_session.flush()
    return ids


@pytest.fixture()
def audio_seed(db_session, seed_exchange, seed_submission):
    """Full seed chain for audio persistence tests."""
    return {
        "exchange_id": seed_exchange,
        "submission_id": seed_submission,
    }
