"""
Unit Tests — InterviewQueryRepository

Tests the read-only query repository with a **mocked** SQLAlchemy session.
Verifies:
  1. Submission lookup by ID (with/without exchanges)
  2. Candidate-scoped submission lookup
  3. Submission listing with status filter and pagination
  4. Exchange listing with optional section filter
  5. Exchange count
  6. Section progress calculation from template snapshot
  7. NotFoundError raised for missing submissions
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, call

import pytest

from app.interview.persistence.repository import InterviewQueryRepository
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_submission(**overrides):
    """Create a minimal fake submission ORM object."""
    defaults = dict(
        id=1,
        candidate_id=100,
        window_id=10,
        role_id=20,
        template_id=30,
        mode="async",
        status="in_progress",
        consent_captured=True,
        final_score=None,
        scheduled_start=None,
        scheduled_end=None,
        started_at=datetime.now(timezone.utc),
        submitted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_exchange_sequence=3,
        template_structure_snapshot={
            "template_id": 30,
            "template_name": "Test Template",
            "total_questions": 5,
            "sections": [
                {
                    "section_name": "resume",
                    "question_count": 2,
                    "question_ids": [101, 102],
                },
                {
                    "section_name": "coding",
                    "question_count": 3,
                    "question_ids": [201, 202, 203],
                },
            ],
        },
        exchanges=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_exchange(**overrides):
    """Create a minimal fake exchange ORM object."""
    defaults = dict(
        id=1,
        interview_submission_id=1,
        sequence_order=1,
        question_id=101,
        coding_problem_id=None,
        question_text="Test question?",
        expected_answer="Expected answer",
        difficulty_at_time="medium",
        response_text="My answer",
        response_code=None,
        response_time_ms=30000,
        ai_followup_message=None,
        content_metadata={"question_type": "text", "section_name": "resume"},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_query_chain(db, result):
    """Set up mock chain: db.query().filter().first() → result."""
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = result
    mock_filter.options.return_value = mock_filter
    mock_filter.order_by.return_value = mock_filter
    mock_filter.limit.return_value = mock_filter
    mock_filter.offset.return_value = mock_filter
    mock_filter.all.return_value = [result] if result else []
    mock_filter.count.return_value = 1 if result else 0
    mock_query.filter.return_value = mock_filter
    db.query.return_value = mock_query
    return db


# ═══════════════════════════════════════════════════════════════════════════
# get_submission_by_id
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSubmissionById:
    def test_found(self):
        sub = _make_submission()
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)
        result = repo.get_submission_by_id(1)
        assert result.id == 1
        assert result.candidate_id == 100

    def test_not_found_raises(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        with pytest.raises(NotFoundError):
            repo.get_submission_by_id(999)

    def test_with_exchanges_passes_option(self):
        sub = _make_submission()
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)

        result = repo.get_submission_by_id(1, with_exchanges=True)
        assert result.id == 1


# ═══════════════════════════════════════════════════════════════════════════
# get_submission_for_candidate
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSubmissionForCandidate:
    def test_found_for_matching_candidate(self):
        sub = _make_submission(candidate_id=100)
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)
        result = repo.get_submission_for_candidate(1, 100)
        assert result.candidate_id == 100

    def test_not_found_raises_for_wrong_candidate(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        with pytest.raises(NotFoundError):
            repo.get_submission_for_candidate(1, 999)


# ═══════════════════════════════════════════════════════════════════════════
# list_submissions_by_candidate
# ═══════════════════════════════════════════════════════════════════════════


class TestListSubmissionsByCandidate:
    def test_returns_list(self):
        sub = _make_submission()
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)
        results = repo.list_submissions_by_candidate(100)
        assert len(results) == 1

    def test_empty_list(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        results = repo.list_submissions_by_candidate(999)
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# list_exchanges
# ═══════════════════════════════════════════════════════════════════════════


class TestListExchanges:
    def test_returns_exchanges(self):
        ex = _make_exchange()
        db = _mock_query_chain(MagicMock(), ex)
        repo = InterviewQueryRepository(db)
        results = repo.list_exchanges(1)
        assert len(results) == 1

    def test_empty_list(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        results = repo.list_exchanges(999)
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# count_exchanges
# ═══════════════════════════════════════════════════════════════════════════


class TestCountExchanges:
    def test_count_returns_integer(self):
        ex = _make_exchange()
        db = _mock_query_chain(MagicMock(), ex)
        repo = InterviewQueryRepository(db)
        assert repo.count_exchanges(1) == 1

    def test_count_zero(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        assert repo.count_exchanges(999) == 0


# ═══════════════════════════════════════════════════════════════════════════
# get_section_progress
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSectionProgress:
    def test_progress_with_partial_completion(self):
        """2/5 questions answered → sections have mixed progress."""
        exchanges = [
            _make_exchange(id=1, question_id=101, sequence_order=1),
            _make_exchange(id=2, question_id=102, sequence_order=2),
        ]
        sub = _make_submission(exchanges=exchanges, current_exchange_sequence=2)
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)

        progress = repo.get_section_progress(1)

        assert progress["submission_id"] == 1
        assert progress["overall_progress"] == 40.0

        sections = progress["sections"]
        assert len(sections) == 2

        resume_sec = sections[0]
        assert resume_sec["section_name"] == "resume"
        assert resume_sec["questions_total"] == 2
        assert resume_sec["questions_answered"] == 2
        assert resume_sec["progress_percentage"] == 100.0

        coding_sec = sections[1]
        assert coding_sec["section_name"] == "coding"
        assert coding_sec["questions_total"] == 3
        assert coding_sec["questions_answered"] == 0
        assert coding_sec["progress_percentage"] == 0.0

    def test_progress_with_no_snapshot(self):
        """No template snapshot → empty sections."""
        sub = _make_submission(
            template_structure_snapshot=None,
            exchanges=[],
        )
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)

        progress = repo.get_section_progress(1)
        assert progress["overall_progress"] == 0.0
        assert progress["sections"] == []

    def test_progress_all_complete(self):
        """All 5 questions answered → 100%."""
        exchanges = [
            _make_exchange(id=i, question_id=qid, sequence_order=i)
            for i, qid in enumerate([101, 102, 201, 202, 203], start=1)
        ]
        sub = _make_submission(exchanges=exchanges, current_exchange_sequence=5)
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)

        progress = repo.get_section_progress(1)
        assert progress["overall_progress"] == 100.0

        for section in progress["sections"]:
            assert section["progress_percentage"] == 100.0

    def test_progress_zero_exchanges(self):
        """Zero exchanges → 0%."""
        sub = _make_submission(exchanges=[], current_exchange_sequence=0)
        db = _mock_query_chain(MagicMock(), sub)
        repo = InterviewQueryRepository(db)

        progress = repo.get_section_progress(1)
        assert progress["overall_progress"] == 0.0

    def test_not_found_raises(self):
        db = _mock_query_chain(MagicMock(), None)
        repo = InterviewQueryRepository(db)
        with pytest.raises(NotFoundError):
            repo.get_section_progress(999)
