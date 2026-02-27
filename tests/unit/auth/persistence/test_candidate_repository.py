"""
Unit Tests for CandidateRepository

Tests candidate CRUD operations with a mocked SQLAlchemy session.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.persistence.candidate_repository import CandidateRepository
from app.auth.persistence.models import Candidate
from app.shared.errors import ConflictError, DatabaseError


class TestCandidateRepositoryCreate:
    """Tests for CandidateRepository.create()"""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = CandidateRepository(self.session)

    def test_create_candidate_adds_to_session_and_flushes(self):
        """Verify candidate is added and flushed."""
        self.repo.create(user_id=1)
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert added.user_id == 1
        assert added.plan == "free"
        assert added.status == "active"
        assert added.profile_metadata is None

    def test_create_candidate_with_profile_metadata(self):
        """Verify profile_metadata is stored."""
        metadata = {"full_name": "Alice", "phone": "+1234567890"}
        self.repo.create(user_id=1, profile_metadata=metadata)
        added = self.session.add.call_args[0][0]
        assert added.profile_metadata == metadata

    def test_create_candidate_custom_plan(self):
        """Verify custom plan is respected."""
        self.repo.create(user_id=1, plan="pro")
        added = self.session.add.call_args[0][0]
        assert added.plan == "pro"

    def test_create_candidate_duplicate_user_raises_conflict(self):
        """Verify ConflictError on duplicate user_id UNIQUE violation."""
        orig = Exception("candidates_user_id_key")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(ConflictError) as exc_info:
            self.repo.create(user_id=1)
        assert "already exists" in str(exc_info.value.message)

    def test_create_candidate_other_integrity_error_raises_database_error(self):
        """Verify DatabaseError on non-UNIQUE IntegrityError."""
        orig = Exception("some_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DatabaseError):
            self.repo.create(user_id=1)


class TestCandidateRepositoryRead:
    """Tests for CandidateRepository read methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = CandidateRepository(self.session)

    def test_get_by_id_returns_candidate(self):
        mock_candidate = Mock(spec=Candidate)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_candidate
        )
        result = self.repo.get_by_id(1)
        assert result is mock_candidate

    def test_get_by_id_returns_none(self):
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.get_by_id(999) is None

    def test_find_by_user_id_returns_candidate(self):
        mock_candidate = Mock(spec=Candidate)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_candidate
        )
        result = self.repo.find_by_user_id(1)
        assert result is mock_candidate

    def test_find_by_user_id_returns_none(self):
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.find_by_user_id(999) is None


class TestCandidateRepositoryUpdate:
    """Tests for CandidateRepository update methods."""

    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = CandidateRepository(self.session)

    def test_update_profile_merges_metadata(self):
        """Verify update_profile merges with existing metadata."""
        mock_candidate = Mock(spec=Candidate)
        mock_candidate.profile_metadata = {"full_name": "Old Name", "phone": "111"}
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_candidate
        )

        with patch(
            "sqlalchemy.orm.attributes.flag_modified"
        ) as mock_flag:
            self.repo.update_profile(1, {"full_name": "New Name", "resume_url": "http://r.com"})
            mock_flag.assert_called_once_with(mock_candidate, "profile_metadata")

        assert mock_candidate.profile_metadata["full_name"] == "New Name"
        assert mock_candidate.profile_metadata["phone"] == "111"
        assert mock_candidate.profile_metadata["resume_url"] == "http://r.com"

    def test_update_profile_creates_metadata_if_none(self):
        """Verify update_profile works when existing metadata is None."""
        mock_candidate = Mock(spec=Candidate)
        mock_candidate.profile_metadata = None
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_candidate
        )

        with patch(
            "sqlalchemy.orm.attributes.flag_modified"
        ):
            self.repo.update_profile(1, {"full_name": "Alice"})

        assert mock_candidate.profile_metadata == {"full_name": "Alice"}

    def test_update_profile_noop_when_candidate_not_found(self):
        """Verify update_profile is a no-op for missing candidate."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        # Should not raise
        self.repo.update_profile(999, {"full_name": "Ghost"})

    def test_update_status(self):
        """Verify update_status calls session update."""
        self.repo.update_status(1, "inactive")
        self.session.query.return_value.filter.return_value.update.assert_called_once()
        update_dict = (
            self.session.query.return_value.filter.return_value.update.call_args[0][0]
        )
        assert update_dict["status"] == "inactive"
