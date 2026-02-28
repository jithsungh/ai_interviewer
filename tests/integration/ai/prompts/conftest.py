"""
Shared fixtures for ai/prompts integration tests.

Requires a running PostgreSQL instance with the interviewer schema applied.
Override the default DB URL via TEST_DATABASE_URL env var.

Pattern: mirrors tests/integration/auth/persistence/conftest.py
- Module-scoped engine + session factory
- Function-scoped sessions with unconditional rollback
- Raw SQL for test data seeding (auto-cleaned by rollback)
"""

import os
import uuid

import pytest
from sqlalchemy import text

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    cleanup_postgres,
)
from app.persistence.postgres.session import (
    init_session_factory,
    get_session_factory,
)


# ---------------------------------------------------------------------------
# Module-scoped: one engine + session-factory per test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def postgres_config():
    """Test PostgreSQL configuration from env or defaults."""
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
    """Initialize PostgreSQL engine + session factory once per module."""
    init_postgres(postgres_config)
    init_session_factory()
    yield
    cleanup_postgres()


# ---------------------------------------------------------------------------
# Function-scoped: one session per test, always rolled back
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(initialized_postgres):
    """
    Provide a transactional session that is **always rolled back**.

    Guarantees each test sees clean state without polluting the DB.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Data-seeding helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def create_test_organization(db_session):
    """
    Insert a minimal organization row. Rolled back by db_session fixture.

    Returns dict with 'id' key.
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
            "name": f"Prompt Test Org {uuid.uuid4().hex[:8]}",
            "org_type": "company",
            "status": "active",
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {"id": row[0]}


@pytest.fixture()
def seed_global_prompt(db_session):
    """
    Insert a global (scope='public', org_id=1) prompt_template.

    Returns dict with row metadata.
    """
    name = f"test_qgen_{uuid.uuid4().hex[:8]}"
    result = db_session.execute(
        text(
            """
            INSERT INTO prompt_templates
                (name, prompt_type, scope, organization_id,
                 system_prompt, user_prompt, model_config, version, is_active)
            VALUES
                (:name, :ptype, 'public', 1,
                 :sys, :usr, CAST(:cfg AS jsonb), :ver, :active)
            RETURNING id, name, prompt_type, version
            """
        ),
        {
            "name": name,
            "ptype": "question_generation",
            "sys": "You are a test agent.\nGenerate a question for {{topic}}.",
            "usr": "Topic: {{topic}}\nDifficulty: {{difficulty}}",
            "cfg": '{"temperature": 0.7, "max_tokens": 1500}',
            "ver": 1,
            "active": True,
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {
        "id": row[0],
        "name": row[1],
        "prompt_type": row[2],
        "version": row[3],
    }


@pytest.fixture()
def seed_org_prompt(db_session, create_test_organization):
    """
    Insert an org-scoped prompt_template.

    Returns dict with row metadata + organization_id.
    """
    org_id = create_test_organization["id"]
    name = f"test_eval_{uuid.uuid4().hex[:8]}"
    result = db_session.execute(
        text(
            """
            INSERT INTO prompt_templates
                (name, prompt_type, scope, organization_id,
                 system_prompt, user_prompt, model_config, version, is_active)
            VALUES
                (:name, :ptype, 'organization', :org_id,
                 :sys, :usr, CAST(:cfg AS jsonb), :ver, :active)
            RETURNING id, name, prompt_type, version
            """
        ),
        {
            "name": name,
            "ptype": "evaluation",
            "org_id": org_id,
            "sys": "You are a test evaluator.\nScore the {{candidate_response}}.",
            "usr": "Question: {{question_text}}\nResponse: {{candidate_response}}",
            "cfg": '{"temperature": 0.0, "max_tokens": 2000, "deterministic": true}',
            "ver": 1,
            "active": True,
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {
        "id": row[0],
        "name": row[1],
        "prompt_type": row[2],
        "version": row[3],
        "organization_id": org_id,
    }


@pytest.fixture()
def seed_inactive_prompt(db_session):
    """Insert an inactive global prompt_template."""
    name = f"test_inactive_{uuid.uuid4().hex[:8]}"
    result = db_session.execute(
        text(
            """
            INSERT INTO prompt_templates
                (name, prompt_type, scope, organization_id,
                 system_prompt, user_prompt, model_config, version, is_active)
            VALUES
                (:name, :ptype, 'public', 1,
                 :sys, :usr, CAST(:cfg AS jsonb), :ver, false)
            RETURNING id, name, version
            """
        ),
        {
            "name": name,
            "ptype": "question_generation",
            "sys": "Old system prompt.",
            "usr": "Old user prompt: {{topic}}",
            "cfg": '{"temperature": 0.5}',
            "ver": 99,
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {"id": row[0], "name": row[1], "version": row[2]}


@pytest.fixture()
def seed_multi_version_prompts(db_session):
    """
    Insert multiple versions of the same prompt type (global).

    Returns list of dicts sorted by version ascending.
    v1 = inactive, v2 = active.
    """
    base = uuid.uuid4().hex[:8]
    rows = []
    for ver, active in [(1, False), (2, True)]:
        result = db_session.execute(
            text(
                """
                INSERT INTO prompt_templates
                    (name, prompt_type, scope, organization_id,
                     system_prompt, user_prompt, model_config, version, is_active)
                VALUES
                    (:name, :ptype, 'public', 1,
                     :sys, :usr, CAST(:cfg AS jsonb), :ver, :active)
                RETURNING id, name, version, is_active
                """
            ),
            {
                "name": f"test_versioned_{base}",
                "ptype": "report_generation",
                "sys": f"System prompt v{ver}.",
                "usr": f"User prompt v{ver}: {{{{topic}}}}",
                "cfg": '{"temperature": 0.5}',
                "ver": ver,
                "active": active,
            },
        )
        row = result.fetchone()
        rows.append({
            "id": row[0],
            "name": row[1],
            "version": row[2],
            "is_active": row[3],
        })
    db_session.flush()
    return rows
