"""
Shared fixtures for coding/execution integration tests.

Requires a running PostgreSQL instance with the interviewer schema applied.

The migration ``main-coding-execution-schema.sql`` is applied **idempotently**
by the ``initialized_postgres`` fixture — no manual step needed.

Database URL defaults to the test-cluster address; override via
``TEST_DATABASE_URL``.

Mirrors tests/integration/auth/persistence/conftest.py.
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

    Also:
    - Registers stub tables for FK targets that have no ORM model imported
      (same pattern as auth/persistence/conftest.py for 'organizations').
    - Applies the coding-execution migration idempotently so the DB has the
      ``executed_at``, ``exit_code`` columns and new constraints/enum values.
    """
    init_postgres(postgres_config)
    init_session_factory()

    # ------------------------------------------------------------------
    # Register stub tables so SQLAlchemy MetaData can resolve ForeignKeys
    # ------------------------------------------------------------------
    _meta = Base.metadata

    if "interview_exchanges" not in _meta.tables:
        Table(
            "interview_exchanges",
            _meta,
            Column("id", BigInteger, primary_key=True),
            Column("interview_submission_id", BigInteger, nullable=False),
            Column("sequence_order", Integer, nullable=False),
            Column("question_text", Text, nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), nullable=False),
            keep_existing=True,
        )

    if "coding_problems" not in _meta.tables:
        Table(
            "coding_problems",
            _meta,
            Column("id", BigInteger, primary_key=True),
            Column("title", Text, nullable=False),
            Column("body", Text, nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), nullable=False),
            keep_existing=True,
        )

    if "coding_test_cases" not in _meta.tables:
        Table(
            "coding_test_cases",
            _meta,
            Column("id", BigInteger, primary_key=True),
            Column("coding_problem_id", BigInteger, nullable=False),
            Column("input_data", Text, nullable=False),
            Column("expected_output", Text, nullable=False),
            Column("is_hidden", Boolean, nullable=False),
            Column("weight", Numeric, nullable=False),
            Column("created_at", TIMESTAMP(timezone=True), nullable=False),
            keep_existing=True,
        )

    # ------------------------------------------------------------------
    # Apply the coding-execution migration idempotently
    # ------------------------------------------------------------------
    engine = get_engine()
    _migration_sql = [
        "ALTER TYPE public.code_execution_status ADD VALUE IF NOT EXISTS 'memory_exceeded'",
        "ALTER TABLE public.code_submissions ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE public.code_execution_results ADD COLUMN IF NOT EXISTS exit_code INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_code_submissions_status ON public.code_submissions USING btree (execution_status)",
    ]

    # enum ADD VALUE must run outside a transaction in PG < 12, so use
    # autocommit per statement.
    with engine.connect() as conn:
        for stmt in _migration_sql:
            conn.execute(text(stmt))
            conn.commit()

        # Conditional constraints (check before adding to avoid duplicate errors)
        _add_constraint_if_missing(
            conn,
            "code_submissions",
            "code_submissions_interview_exchange_id_key",
            "ALTER TABLE ONLY public.code_submissions "
            "ADD CONSTRAINT code_submissions_interview_exchange_id_key "
            "UNIQUE (interview_exchange_id)",
        )
        _add_constraint_if_missing(
            conn,
            "code_execution_results",
            "uq_submission_test_case",
            "ALTER TABLE ONLY public.code_execution_results "
            "ADD CONSTRAINT uq_submission_test_case "
            "UNIQUE (code_submission_id, test_case_id)",
        )

    yield
    cleanup_postgres()


def _add_constraint_if_missing(conn, table: str, constraint: str, ddl: str):
    """Add a constraint only if it doesn't already exist."""
    exists = conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = :tbl AND constraint_name = :con"
        ),
        {"tbl": table, "con": constraint},
    ).scalar()
    if not exists:
        conn.execute(text(ddl))
    conn.commit()


# ---------------------------------------------------------------------------
# Function-scoped: one session per test, always rolled back
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(initialized_postgres):
    """
    Provide a transactional session that is **always rolled back**.

    This guarantees each test sees a clean state without polluting
    the shared database.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Seed helpers — insert the full FK parent chain needed for coding tables
# ---------------------------------------------------------------------------

@pytest.fixture()
def _unique_suffix():
    """Unique suffix to avoid collisions between parallel test runs."""
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def seed_organization(db_session, _unique_suffix):
    """Insert a minimal organization row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO organizations (name, organization_type)
            VALUES (:name, :org_type)
            RETURNING id
            """
        ),
        {"name": f"Test Org {_unique_suffix}", "org_type": "company"},
    )
    org_id = result.scalar_one()
    db_session.flush()
    return org_id


@pytest.fixture()
def seed_admin_user(db_session, _unique_suffix):
    """Insert a minimal admin user row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO users (name, email, password_hash, user_type)
            VALUES (:name, :email, :pw, :utype)
            RETURNING id
            """
        ),
        {
            "name": "Admin Seed",
            "email": f"admin-{_unique_suffix}@seed.test",
            "pw": "$2b$12$seedroundhashdataforinttesting",
            "utype": "admin",
        },
    )
    user_id = result.scalar_one()
    db_session.flush()
    return user_id


@pytest.fixture()
def seed_admin(db_session, seed_admin_user, seed_organization):
    """Insert a minimal admin row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO admins (user_id, organization_id, role)
            VALUES (:uid, :oid, :role)
            RETURNING id
            """
        ),
        {"uid": seed_admin_user, "oid": seed_organization, "role": "admin"},
    )
    admin_id = result.scalar_one()
    db_session.flush()
    return admin_id


@pytest.fixture()
def seed_candidate_user(db_session, _unique_suffix):
    """Insert a minimal candidate user row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO users (name, email, password_hash, user_type)
            VALUES (:name, :email, :pw, :utype)
            RETURNING id
            """
        ),
        {
            "name": "Candidate Seed",
            "email": f"candidate-{_unique_suffix}@seed.test",
            "pw": "$2b$12$seedroundhashdataforinttesting",
            "utype": "candidate",
        },
    )
    user_id = result.scalar_one()
    db_session.flush()
    return user_id


@pytest.fixture()
def seed_candidate(db_session, seed_candidate_user):
    """Insert a minimal candidate row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO candidates (user_id)
            VALUES (:uid)
            RETURNING id
            """
        ),
        {"uid": seed_candidate_user},
    )
    candidate_id = result.scalar_one()
    db_session.flush()
    return candidate_id


@pytest.fixture()
def seed_role(db_session, _unique_suffix):
    """Insert a minimal role row."""
    result = db_session.execute(
        text(
            """
            INSERT INTO roles (name, scope)
            VALUES (:name, :scope)
            RETURNING id
            """
        ),
        {"name": f"Role {_unique_suffix}", "scope": "public"},
    )
    role_id = result.scalar_one()
    db_session.flush()
    return role_id


@pytest.fixture()
def seed_template(db_session, _unique_suffix):
    """Insert a minimal interview template."""
    result = db_session.execute(
        text(
            """
            INSERT INTO interview_templates (name, scope, template_structure)
            VALUES (:name, :scope, :ts)
            RETURNING id
            """
        ),
        {
            "name": f"Template {_unique_suffix}",
            "scope": "public",
            "ts": '{"sections":[]}',
        },
    )
    template_id = result.scalar_one()
    db_session.flush()
    return template_id


@pytest.fixture()
def seed_window(
    db_session, seed_organization, seed_admin, _unique_suffix,
):
    """Insert a minimal interview submission window."""
    result = db_session.execute(
        text(
            """
            INSERT INTO interview_submission_windows
                (organization_id, admin_id, name, scope, start_time, end_time, timezone)
            VALUES (:oid, :aid, :name, :scope, :start, :stop, :tz)
            RETURNING id
            """
        ),
        {
            "oid": seed_organization,
            "aid": seed_admin,
            "name": f"Window {_unique_suffix}",
            "scope": "global",
            "start": "2025-01-01T00:00:00Z",
            "stop": "2026-12-31T23:59:59Z",
            "tz": "UTC",
        },
    )
    window_id = result.scalar_one()
    db_session.flush()
    return window_id


@pytest.fixture()
def seed_submission(
    db_session, seed_candidate, seed_window, seed_role, seed_template,
):
    """Insert a minimal interview submission."""
    result = db_session.execute(
        text(
            """
            INSERT INTO interview_submissions
                (candidate_id, window_id, role_id, template_id)
            VALUES (:cid, :wid, :rid, :tid)
            RETURNING id
            """
        ),
        {
            "cid": seed_candidate,
            "wid": seed_window,
            "rid": seed_role,
            "tid": seed_template,
        },
    )
    submission_id = result.scalar_one()
    db_session.flush()
    return submission_id


@pytest.fixture()
def seed_coding_problem(db_session, _unique_suffix):
    """Insert a minimal coding problem."""
    db_session.execute(text(
        "SELECT setval('coding_problems_id_seq', COALESCE((SELECT MAX(id) FROM coding_problems), 0))"
    ))
    result = db_session.execute(
        text(
            """
            INSERT INTO coding_problems
                (body, difficulty, scope, source_name, source_id, title)
            VALUES (:body, :diff, :scope, :src_name, :src_id, :title)
            RETURNING id
            """
        ),
        {
            "body": "Return the square of the input.",
            "diff": "easy",
            "scope": "public",
            "src_name": "leetcode",
            "src_id": f"test-seed-{_unique_suffix}",
            "title": "Square It",
        },
    )
    problem_id = result.scalar_one()
    db_session.flush()
    return problem_id


@pytest.fixture()
def seed_exchange(db_session, seed_submission, seed_coding_problem):
    """Insert a minimal interview exchange (coding type)."""
    result = db_session.execute(
        text(
            """
            INSERT INTO interview_exchanges
                (interview_submission_id, sequence_order,
                 coding_problem_id, question_text, difficulty_at_time)
            VALUES (:isid, :seq, :cpid, :qt, :dat)
            RETURNING id
            """
        ),
        {
            "isid": seed_submission,
            "seq": 1,
            "cpid": seed_coding_problem,
            "qt": "Solve the square problem.",
            "dat": "easy",
        },
    )
    exchange_id = result.scalar_one()
    db_session.flush()
    return exchange_id


@pytest.fixture()
def seed_test_cases(db_session, seed_coding_problem):
    """Insert two coding test cases and return their IDs."""
    ids = []
    for input_data, expected in [("5\n", "25\n"), ("3\n", "9\n")]:
        result = db_session.execute(
            text(
                """
                INSERT INTO coding_test_cases
                    (coding_problem_id, input_data, expected_output)
                VALUES (:cpid, :inp, :exp)
                RETURNING id
                """
            ),
            {"cpid": seed_coding_problem, "inp": input_data, "exp": expected},
        )
        ids.append(result.scalar_one())
    db_session.flush()
    return ids


# ---------------------------------------------------------------------------
# Composite fixtures — frequently used combos
# ---------------------------------------------------------------------------

@pytest.fixture()
def coding_seed(
    db_session,
    seed_exchange,
    seed_coding_problem,
    seed_test_cases,
):
    """
    Full seed chain ready for coding repository tests.

    Returns a dict with:
    - exchange_id: interview_exchanges.id
    - coding_problem_id: coding_problems.id
    - test_case_ids: list of coding_test_cases.id
    """
    return {
        "exchange_id": seed_exchange,
        "coding_problem_id": seed_coding_problem,
        "test_case_ids": seed_test_cases,
    }
