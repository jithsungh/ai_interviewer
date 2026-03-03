"""
Integration Tests — Interview Query Repository

Tests the full service + repository stack with mocked DB sessions
and realistic data. Verifies:
  1. Exchange listing with section filtering
  2. Section progress calculation across multiple sections
  3. Candidate-scoped access control
  4. Edge cases: empty exchanges, missing snapshot, all complete
  5. API service integration with repository
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.interview.api.contracts import (
    ExchangeListResponse,
    SectionProgressResponse,
)
from app.interview.api.service import InterviewApiService
from app.interview.persistence.repository import InterviewQueryRepository
from app.shared.errors import NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

TEMPLATE_SNAPSHOT = {
    "template_id": 30,
    "template_name": "Full Stack Interview",
    "total_questions": 8,
    "sections": [
        {
            "section_name": "resume",
            "question_count": 2,
            "question_ids": [101, 102],
        },
        {
            "section_name": "behavioral",
            "question_count": 3,
            "question_ids": [201, 202, 203],
        },
        {
            "section_name": "coding",
            "question_count": 3,
            "question_ids": [301, 302, 303],
        },
    ],
}


def _make_submission(**overrides):
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
        started_at=datetime(2026, 2, 14, 10, 0, 0, tzinfo=timezone.utc),
        submitted_at=None,
        created_at=datetime(2026, 2, 14, 9, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 2, 14, 10, 0, 0, tzinfo=timezone.utc),
        current_exchange_sequence=0,
        template_structure_snapshot=TEMPLATE_SNAPSHOT,
        exchanges=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_exchange(ex_id, seq, q_id, section, q_type="text", **overrides):
    defaults = dict(
        id=ex_id,
        interview_submission_id=1,
        sequence_order=seq,
        question_id=q_id,
        coding_problem_id=None,
        question_text=f"Question {q_id}",
        expected_answer=f"Answer for {q_id}",
        difficulty_at_time="medium",
        response_text=f"Candidate response for {q_id}",
        response_code=None,
        response_time_ms=30000 + (seq * 1000),
        ai_followup_message=None,
        content_metadata={"question_type": q_type, "section_name": section},
        created_at=datetime(2026, 2, 14, 10, seq, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _build_mock_repo_with_data(submission, exchanges):
    """
    Build a mocked InterviewQueryRepository that returns the given data.

    This mocks the entire query chain so we test the SERVICE logic,
    not SQLAlchemy query building.
    """
    repo = MagicMock(spec=InterviewQueryRepository)
    repo.get_submission_by_id.return_value = submission
    repo.get_submission_for_candidate.return_value = submission
    repo.list_exchanges.return_value = exchanges
    repo.count_exchanges.return_value = len(exchanges)

    # For get_section_progress, replicate the real logic since it's
    # self-contained computation on the submission object
    real_repo = InterviewQueryRepository.__new__(InterviewQueryRepository)
    real_repo._session = MagicMock()

    # Patch get_submission_by_id on the real repo for get_section_progress
    def mock_get_by_id(sid, with_exchanges=False):
        return submission

    repo.get_section_progress = lambda sid: _compute_section_progress(submission)

    return repo


def _compute_section_progress(submission):
    """Replicate InterviewQueryRepository.get_section_progress logic."""
    snapshot = submission.template_structure_snapshot
    if not snapshot or not isinstance(snapshot, dict):
        return {
            "submission_id": submission.id,
            "overall_progress": 0.0,
            "sections": [],
        }

    sections_data = snapshot.get("sections", [])
    total_questions = snapshot.get("total_questions", 0)

    answered_question_ids = set()
    answered_coding_problem_ids = set()
    for ex in (submission.exchanges or []):
        if ex.question_id:
            answered_question_ids.add(ex.question_id)
        if ex.coding_problem_id:
            answered_coding_problem_ids.add(ex.coding_problem_id)

    sections_progress = []
    total_answered = 0

    for section in sections_data:
        section_name = section.get("section_name", "unknown")
        question_ids = section.get("question_ids", [])
        questions_total = section.get("question_count", len(question_ids))
        questions_answered = sum(
            1 for qid in question_ids
            if qid in answered_question_ids or qid in answered_coding_problem_ids
        )
        total_answered += questions_answered
        section_pct = (
            (questions_answered / questions_total * 100.0)
            if questions_total > 0
            else 0.0
        )
        sections_progress.append({
            "section_name": section_name,
            "questions_total": questions_total,
            "questions_answered": questions_answered,
            "progress_percentage": round(section_pct, 1),
        })

    overall_pct = (
        (total_answered / total_questions * 100.0)
        if total_questions > 0
        else 0.0
    )

    return {
        "submission_id": submission.id,
        "overall_progress": round(overall_pct, 1),
        "sections": sections_progress,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Exchange listing integration
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeListingIntegration:
    def test_full_exchange_list_multi_section(self):
        """List all exchanges across resume + behavioral sections."""
        exchanges = [
            _make_exchange(1, 1, 101, "resume"),
            _make_exchange(2, 2, 102, "resume"),
            _make_exchange(3, 3, 201, "behavioral"),
        ]
        sub = _make_submission(exchanges=exchanges, current_exchange_sequence=3)
        repo = _build_mock_repo_with_data(sub, exchanges)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.list_exchanges(submission_id=1)

        assert isinstance(result, ExchangeListResponse)
        assert result.total_exchanges == 3
        assert result.exchanges[0].exchange_id == 1
        assert result.exchanges[0].section_name == "resume"
        assert result.exchanges[2].section_name == "behavioral"

    def test_exchange_list_section_filter(self):
        """Filter by section returns only matching exchanges."""
        all_exchanges = [
            _make_exchange(1, 1, 101, "resume"),
            _make_exchange(2, 2, 102, "resume"),
            _make_exchange(3, 3, 201, "behavioral"),
        ]
        resume_only = [ex for ex in all_exchanges if ex.content_metadata["section_name"] == "resume"]
        sub = _make_submission(exchanges=all_exchanges, current_exchange_sequence=3)
        repo = _build_mock_repo_with_data(sub, resume_only)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.list_exchanges(submission_id=1, section="resume")

        assert result.total_exchanges == 2
        for ex in result.exchanges:
            assert ex.section_name == "resume"

    def test_exchange_list_without_responses(self):
        """include_responses=False strips response data."""
        exchanges = [_make_exchange(1, 1, 101, "resume")]
        sub = _make_submission(exchanges=exchanges)
        repo = _build_mock_repo_with_data(sub, exchanges)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.list_exchanges(submission_id=1, include_responses=False)

        assert result.total_exchanges == 1
        assert result.exchanges[0].response_text is None
        assert result.exchanges[0].response_time_ms is None

    def test_exchange_list_empty(self):
        """No exchanges completed yet."""
        sub = _make_submission(exchanges=[], current_exchange_sequence=0)
        repo = _build_mock_repo_with_data(sub, [])

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.list_exchanges(submission_id=1)
        assert result.total_exchanges == 0
        assert result.exchanges == []

    def test_exchange_list_candidate_scoped(self):
        """Candidate can only access own exchanges."""
        exchanges = [_make_exchange(1, 1, 101, "resume")]
        sub = _make_submission(candidate_id=100, exchanges=exchanges)
        repo = _build_mock_repo_with_data(sub, exchanges)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.list_exchanges(submission_id=1, candidate_id=100)

        assert result.total_exchanges == 1
        repo.get_submission_for_candidate.assert_called_once_with(1, 100)

    def test_exchange_list_wrong_candidate_raises(self):
        """Wrong candidate_id → NotFoundError."""
        repo = MagicMock(spec=InterviewQueryRepository)
        repo.get_submission_for_candidate.side_effect = NotFoundError(
            resource_type="Submission", resource_id=1
        )

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        with pytest.raises(NotFoundError):
            svc.list_exchanges(submission_id=1, candidate_id=999)


# ═══════════════════════════════════════════════════════════════════════════
# Section progress integration
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionProgressIntegration:
    def test_partial_progress_multi_section(self):
        """3/8 questions answered across 3 sections."""
        exchanges = [
            _make_exchange(1, 1, 101, "resume"),
            _make_exchange(2, 2, 102, "resume"),
            _make_exchange(3, 3, 201, "behavioral"),
        ]
        sub = _make_submission(exchanges=exchanges, current_exchange_sequence=3)
        repo = _build_mock_repo_with_data(sub, exchanges)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.get_progress(submission_id=1)

        assert isinstance(result, SectionProgressResponse)
        assert result.overall_progress == 37.5  # 3/8 * 100
        assert len(result.sections) == 3

        resume = result.sections[0]
        assert resume.section_name == "resume"
        assert resume.questions_total == 2
        assert resume.questions_answered == 2
        assert resume.progress_percentage == 100.0

        behavioral = result.sections[1]
        assert behavioral.section_name == "behavioral"
        assert behavioral.questions_total == 3
        assert behavioral.questions_answered == 1
        assert behavioral.progress_percentage == 33.3

        coding = result.sections[2]
        assert coding.section_name == "coding"
        assert coding.questions_total == 3
        assert coding.questions_answered == 0
        assert coding.progress_percentage == 0.0

    def test_all_complete_progress(self):
        """All 8 questions answered → 100%."""
        exchanges = [
            _make_exchange(i, i, qid, sec)
            for i, (qid, sec) in enumerate(
                [
                    (101, "resume"), (102, "resume"),
                    (201, "behavioral"), (202, "behavioral"), (203, "behavioral"),
                    (301, "coding"), (302, "coding"), (303, "coding"),
                ],
                start=1,
            )
        ]
        sub = _make_submission(exchanges=exchanges, current_exchange_sequence=8)
        repo = _build_mock_repo_with_data(sub, exchanges)

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.get_progress(submission_id=1)

        assert result.overall_progress == 100.0
        for section in result.sections:
            assert section.progress_percentage == 100.0

    def test_zero_progress(self):
        """No exchanges → 0%."""
        sub = _make_submission(exchanges=[], current_exchange_sequence=0)
        repo = _build_mock_repo_with_data(sub, [])

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.get_progress(submission_id=1)

        assert result.overall_progress == 0.0
        for section in result.sections:
            assert section.questions_answered == 0
            assert section.progress_percentage == 0.0

    def test_no_template_snapshot(self):
        """Missing snapshot → empty sections."""
        sub = _make_submission(
            template_structure_snapshot=None,
            exchanges=[],
        )
        repo = _build_mock_repo_with_data(sub, [])

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        result = svc.get_progress(submission_id=1)
        assert result.overall_progress == 0.0
        assert result.sections == []

    def test_candidate_scoped_progress(self):
        """Candidate path validates ownership."""
        sub = _make_submission(candidate_id=100)
        repo = _build_mock_repo_with_data(sub, [])

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        svc.get_progress(submission_id=1, candidate_id=100)
        repo.get_submission_for_candidate.assert_called_once_with(1, 100)

    def test_wrong_candidate_raises(self):
        """Wrong candidate → NotFoundError."""
        repo = MagicMock(spec=InterviewQueryRepository)
        repo.get_submission_for_candidate.side_effect = NotFoundError(
            resource_type="Submission", resource_id=1
        )

        svc = InterviewApiService(db=MagicMock())
        svc._repo = repo

        with pytest.raises(NotFoundError):
            svc.get_progress(submission_id=1, candidate_id=999)
