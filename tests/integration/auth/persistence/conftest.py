"""
Shared fixtures for auth/persistence integration tests.

Requires a running PostgreSQL instance with the interviewer schema applied.
Database URL defaults to the test-cluster addr; override via TEST_DATABASE_URL.
"""

import os
import uuid
import pytest
from sqlalchemy import text, Table, Column, BigInteger, Text, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    cleanup_postgres,
    get_engine,
)
from app.persistence.postgres.session import (
    init_session_factory,
    get_session_factory,
)
from app.auth.persistence.models import Base as AuthBase


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

    Also registers a stub 'organizations' table in the auth module's
    MetaData so SQLAlchemy can resolve Admin.organization_id FK without
    requiring the admin module's full ORM models.
    """
    init_postgres(postgres_config)
    init_session_factory()

    # Register a minimal 'organizations' table in auth's MetaData so
    # that the Admin mapper can resolve ForeignKey('organizations.id').
    if "organizations" not in AuthBase.metadata.tables:
        Table(
            "organizations",
            AuthBase.metadata,
            Column("id", BigInteger, primary_key=True),
            Column("name", Text, nullable=False),
            Column("organization_type", String(50), nullable=False),
            Column("plan", String(20), nullable=False),
            Column("domain", Text, nullable=True),
            Column("status", String(20), nullable=False),
            Column("policy_config", JSONB, nullable=True),
            Column("metadata", JSONB, nullable=True),
            Column("created_at", TIMESTAMP(timezone=True), nullable=False),
            Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
            keep_existing=True,
        )

    yield
    cleanup_postgres()


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
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def unique_email():
    """Generate a unique email for each test run to avoid collisions."""
    return f"test-{uuid.uuid4().hex[:12]}@integration.test"


@pytest.fixture()
def create_test_user(db_session, unique_email):
    """
    Insert a minimal user row and return its id + email.

    The row is rolled back automatically by the ``db_session`` fixture.
    """
    result = db_session.execute(
        text(
            """
            INSERT INTO users (name, email, password_hash, user_type, status, token_version)
            VALUES (:name, :email, :pw, :utype, :status, :tv)
            RETURNING id, email
            """
        ),
        {
            "name": "Integration Test User",
            "email": unique_email,
            "pw": "$2b$12$testroundhashdataforunittesting",
            "utype": "admin",
            "status": "active",
            "tv": 1,
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {"id": row[0], "email": row[1]}


@pytest.fixture()
def create_test_organization(db_session):
    """
    Insert a minimal organization row and return its id.
    """
    result = db_session.execute(
        text(
            """
            INSERT INTO organizations (name, organization_type, status)
            VALUES (:name, :org_type, :status)
            RETURNING id
            """
        ),
        {
            "name": f"Test Org {uuid.uuid4().hex[:8]}",
            "org_type": "company",
            "status": "active",
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {"id": row[0]}
