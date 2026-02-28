"""
Integration Tests – CandidateRepository

Tests CRUD + JSONB merge against a real PostgreSQL database.
Each test is rolled back automatically.
"""

import pytest
from sqlalchemy import text

from app.auth.persistence.candidate_repository import CandidateRepository
from app.shared.errors.exceptions import ConflictError, DatabaseError


pytestmark = pytest.mark.integration


@pytest.fixture()
def candidate_user(db_session, unique_email):
    """Create a user with user_type='candidate' for candidate tests."""
    result = db_session.execute(
        text(
            """
            INSERT INTO users (name, email, password_hash, user_type, status, token_version)
            VALUES (:name, :email, :pw, 'candidate', 'active', 1)
            RETURNING id
            """
        ),
        {
            "name": "Candidate User",
            "email": unique_email,
            "pw": "$2b$12$testroundhashdataforunittesting",
        },
    )
    row = result.fetchone()
    db_session.flush()
    return {"id": row[0]}


class TestCandidateRepositoryCreateIntegration:

    def test_create_candidate_persists_row(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        candidate = repo.create(user_id=candidate_user["id"])

        assert candidate.id is not None
        assert candidate.user_id == candidate_user["id"]
        assert candidate.plan == "free"
        assert candidate.status == "active"

    def test_create_candidate_with_metadata(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        meta = {"full_name": "Alice Wonderland", "phone": "+1"}
        candidate = repo.create(
            user_id=candidate_user["id"],
            profile_metadata=meta,
        )

        assert candidate.profile_metadata["full_name"] == "Alice Wonderland"

    def test_create_candidate_duplicate_user_raises_conflict(
        self, db_session, candidate_user
    ):
        repo = CandidateRepository(db_session)
        repo.create(user_id=candidate_user["id"])
        db_session.flush()

        with pytest.raises(ConflictError):
            repo.create(user_id=candidate_user["id"])


class TestCandidateRepositoryReadIntegration:

    def test_get_by_id_returns_candidate(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        created = repo.create(user_id=candidate_user["id"])
        db_session.flush()

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    def test_find_by_user_id(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        repo.create(user_id=candidate_user["id"])
        db_session.flush()

        found = repo.find_by_user_id(candidate_user["id"])
        assert found is not None
        assert found.user_id == candidate_user["id"]


class TestCandidateRepositoryUpdateIntegration:

    def test_update_profile_merges_jsonb(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        repo.create(
            user_id=candidate_user["id"],
            profile_metadata={"full_name": "Old", "phone": "111"},
        )
        db_session.flush()

        candidate = repo.find_by_user_id(candidate_user["id"])
        repo.update_profile(candidate.id, {"full_name": "New", "city": "NYC"})
        db_session.flush()
        db_session.expire_all()

        refreshed = repo.find_by_user_id(candidate_user["id"])
        assert refreshed.profile_metadata["full_name"] == "New"
        assert refreshed.profile_metadata["phone"] == "111"
        assert refreshed.profile_metadata["city"] == "NYC"

    def test_update_profile_creates_metadata_from_none(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        repo.create(user_id=candidate_user["id"])
        db_session.flush()

        candidate = repo.find_by_user_id(candidate_user["id"])
        repo.update_profile(candidate.id, {"full_name": "Created"})
        db_session.flush()
        db_session.expire_all()

        refreshed = repo.find_by_user_id(candidate_user["id"])
        assert refreshed.profile_metadata == {"full_name": "Created"}

    def test_update_status_changes_status(self, db_session, candidate_user):
        repo = CandidateRepository(db_session)
        repo.create(user_id=candidate_user["id"])
        db_session.flush()

        candidate = repo.find_by_user_id(candidate_user["id"])
        repo.update_status(candidate.id, "inactive")
        db_session.flush()
        db_session.expire_all()

        refreshed = repo.find_by_user_id(candidate_user["id"])
        assert refreshed.status == "inactive"


class TestCandidateRepositoryConstraints:

    def test_foreign_key_user_id_enforced(self, db_session):
        repo = CandidateRepository(db_session)
        with pytest.raises(DatabaseError):
            repo.create(user_id=999_999_999)
