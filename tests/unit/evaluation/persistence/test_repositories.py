"""
Unit Tests — Evaluation Persistence Repositories

Tests repository CRUD operations with a mocked SQLAlchemy session.
Follows the same pattern used in tests/unit/auth/persistence/.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.evaluation.persistence.errors import (
    DuplicateEvaluationError,
    DuplicateResultError,
    EvaluationNotFoundError,
    InterviewResultNotFoundError,
    PersistenceError,
)
from app.evaluation.persistence.models import (
    EvaluationDimensionScoreModel,
    EvaluationModel,
    InterviewResultModel,
    SupplementaryReportModel,
)
from app.evaluation.persistence.repositories import (
    DimensionScoreRepository,
    EvaluationRepository,
    InterviewResultRepository,
    SupplementaryReportRepository,
)


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationRepository — Create
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationRepositoryCreate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = EvaluationRepository(self.session)

    def test_create_adds_and_flushes(self):
        """Verify evaluation is added to session and flushed."""
        result = self.repo.create(
            interview_exchange_id=1,
            rubric_id=2,
            evaluator_type="ai",
            total_score=Decimal("85.00"),
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert isinstance(added, EvaluationModel)
        assert added.interview_exchange_id == 1
        assert added.evaluator_type == "ai"
        assert added.total_score == Decimal("85.00")

    def test_create_sets_defaults(self):
        """Verify default values for is_final and evaluated_at."""
        self.repo.create(
            interview_exchange_id=1,
            rubric_id=None,
            evaluator_type="ai",
            total_score=Decimal("90"),
        )
        added = self.session.add.call_args[0][0]
        assert added.is_final is True
        assert added.evaluated_at is not None

    def test_create_with_all_optional_fields(self):
        """Verify all optional fields are stored."""
        self.repo.create(
            interview_exchange_id=1,
            rubric_id=2,
            evaluator_type="hybrid",
            total_score=Decimal("80"),
            explanation={"comment": "Good"},
            is_final=False,
            evaluated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            evaluated_by=42,
            model_id=99,
            scoring_version="v2.0",
        )
        added = self.session.add.call_args[0][0]
        assert added.evaluated_by == 42
        assert added.model_id == 99
        assert added.scoring_version == "v2.0"
        assert added.explanation == {"comment": "Good"}
        assert added.is_final is False

    def test_create_duplicate_raises_duplicate_error(self):
        """DuplicateEvaluationError on partial unique constraint."""
        orig = Exception("uq_evaluations_exchange_final")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DuplicateEvaluationError) as exc_info:
            self.repo.create(
                interview_exchange_id=1,
                rubric_id=None,
                evaluator_type="ai",
                total_score=Decimal("85"),
            )
        assert exc_info.value.interview_exchange_id == 1

    def test_create_other_integrity_raises_persistence_error(self):
        """PersistenceError on other IntegrityError."""
        orig = Exception("some_other_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(PersistenceError):
            self.repo.create(
                interview_exchange_id=1,
                rubric_id=None,
                evaluator_type="ai",
                total_score=Decimal("85"),
            )


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationRepository — Read
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationRepositoryRead:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = EvaluationRepository(self.session)

    def test_get_by_id_returns_model(self):
        """get_by_id should return the model when found."""
        mock_eval = Mock(spec=EvaluationModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_eval
        )
        result = self.repo.get_by_id(1)
        assert result is mock_eval

    def test_get_by_id_returns_none(self):
        """get_by_id should return None when not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.get_by_id(999) is None

    def test_get_by_id_or_raise_returns_model(self):
        """get_by_id_or_raise should return the model when found."""
        mock_eval = Mock(spec=EvaluationModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_eval
        )
        result = self.repo.get_by_id_or_raise(1)
        assert result is mock_eval

    def test_get_by_id_or_raise_raises_not_found(self):
        """get_by_id_or_raise should raise EvaluationNotFoundError."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(EvaluationNotFoundError) as exc_info:
            self.repo.get_by_id_or_raise(999)
        assert exc_info.value.evaluation_id == 999

    def test_get_final_by_exchange_returns_model(self):
        """get_final_by_exchange should find the final evaluation."""
        mock_eval = Mock(spec=EvaluationModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_eval
        )
        result = self.repo.get_final_by_exchange(10)
        assert result is mock_eval

    def test_get_all_by_exchange_returns_list(self):
        """get_all_by_exchange should return ordered list."""
        mock_evals = [Mock(spec=EvaluationModel), Mock(spec=EvaluationModel)]
        (
            self.session.query.return_value
            .filter.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = mock_evals
        result = self.repo.get_all_by_exchange(10, include_non_final=False)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationRepository — Update
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationRepositoryUpdate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = EvaluationRepository(self.session)

    def test_mark_non_final(self):
        """mark_non_final should set is_final=False and flush."""
        mock_eval = Mock(spec=EvaluationModel)
        mock_eval.is_final = True
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_eval
        )

        result = self.repo.mark_non_final(1)
        assert result.is_final is False
        self.session.flush.assert_called_once()

    def test_mark_non_final_raises_when_not_found(self):
        """mark_non_final should raise EvaluationNotFoundError."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(EvaluationNotFoundError):
            self.repo.mark_non_final(999)


# ═══════════════════════════════════════════════════════════════════════════
# DimensionScoreRepository — Create
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionScoreRepositoryCreate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = DimensionScoreRepository(self.session)

    def test_create_batch_adds_all_and_flushes(self):
        """create_batch should add each model and flush once."""
        scores = [
            {"rubric_dimension_id": 1, "score": Decimal("4.0"), "justification": "Good"},
            {"rubric_dimension_id": 2, "score": Decimal("3.5"), "justification": "OK"},
        ]
        result = self.repo.create_batch(evaluation_id=10, scores=scores)

        assert self.session.add.call_count == 2
        self.session.flush.assert_called_once()
        assert len(result) == 2

    def test_create_batch_with_max_score(self):
        """create_batch should store max_score (DEV-49)."""
        scores = [
            {
                "rubric_dimension_id": 1,
                "score": Decimal("4.0"),
                "justification": "Good",
                "max_score": Decimal("5.0"),
            },
        ]
        result = self.repo.create_batch(evaluation_id=10, scores=scores)
        added = self.session.add.call_args_list[0][0][0]
        assert added.max_score == Decimal("5.0")

    def test_create_batch_empty_list(self):
        """create_batch with empty list should flush but return empty."""
        result = self.repo.create_batch(evaluation_id=10, scores=[])
        assert result == []
        self.session.flush.assert_called_once()

    def test_create_batch_integrity_error(self):
        """create_batch should raise PersistenceError on IntegrityError."""
        orig = Exception("some_fk_violation")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(PersistenceError):
            self.repo.create_batch(
                evaluation_id=10,
                scores=[{"rubric_dimension_id": 1, "score": Decimal("4")}],
            )


# ═══════════════════════════════════════════════════════════════════════════
# DimensionScoreRepository — Read
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionScoreRepositoryRead:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = DimensionScoreRepository(self.session)

    def test_get_by_evaluation_returns_list(self):
        """get_by_evaluation should return all scores for evaluation."""
        mock_scores = [Mock(spec=EvaluationDimensionScoreModel)]
        self.session.query.return_value.filter.return_value.all.return_value = (
            mock_scores
        )
        result = self.repo.get_by_evaluation(10)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# DimensionScoreRepository — Update
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionScoreRepositoryUpdate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = DimensionScoreRepository(self.session)

    def test_update_score_succeeds(self):
        """update_score should update the score and flush."""
        mock_dim = Mock(spec=EvaluationDimensionScoreModel)
        mock_dim.score = Decimal("3.0")
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_dim
        )

        result = self.repo.update_score(1, new_score=Decimal("4.5"))
        assert result.score == Decimal("4.5")
        self.session.flush.assert_called_once()

    def test_update_score_with_justification(self):
        """update_score should update justification when provided."""
        mock_dim = Mock(spec=EvaluationDimensionScoreModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_dim
        )

        self.repo.update_score(
            1, new_score=Decimal("4.5"), justification="Updated"
        )
        assert mock_dim.justification == "Updated"

    def test_update_score_not_found(self):
        """update_score should raise PersistenceError when not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(PersistenceError) as exc_info:
            self.repo.update_score(999, new_score=Decimal("4.0"))
        assert "not found" in exc_info.value.message


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultRepository — Create
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultRepositoryCreate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = InterviewResultRepository(self.session)

    def _make_result_kwargs(self, **overrides):
        """Helper to build minimal valid kwargs."""
        defaults = dict(
            interview_submission_id=1,
            final_score=Decimal("85"),
            normalized_score=Decimal("0.85"),
            result_status="pass",
            recommendation="hire",
            scoring_version="v1.0",
            rubric_snapshot=None,
            template_weight_snapshot=None,
            section_scores=None,
            strengths="Good technical skills",
            weaknesses="Could improve communication",
            summary_notes="Solid candidate",
            generated_by="ai",
        )
        defaults.update(overrides)
        return defaults

    def test_create_adds_and_flushes(self):
        """Verify result is added to session and flushed."""
        self.repo.create(**self._make_result_kwargs())
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert isinstance(added, InterviewResultModel)
        assert added.interview_submission_id == 1

    def test_create_duplicate_raises_duplicate_result_error(self):
        """DuplicateResultError on partial unique constraint."""
        orig = Exception("uq_interview_results_submission_current")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(DuplicateResultError) as exc_info:
            self.repo.create(**self._make_result_kwargs())
        assert exc_info.value.submission_id == 1

    def test_create_other_integrity_raises_persistence_error(self):
        """PersistenceError on other IntegrityError."""
        orig = Exception("some_other_constraint")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(PersistenceError):
            self.repo.create(**self._make_result_kwargs())


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultRepository — Read
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultRepositoryRead:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = InterviewResultRepository(self.session)

    def test_get_by_id_returns_model(self):
        """get_by_id should return the model when found."""
        mock_result = Mock(spec=InterviewResultModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )
        assert self.repo.get_by_id(1) is mock_result

    def test_get_by_id_returns_none(self):
        """get_by_id should return None when not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.get_by_id(999) is None

    def test_get_by_id_or_raise_raises(self):
        """get_by_id_or_raise should raise InterviewResultNotFoundError."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(InterviewResultNotFoundError):
            self.repo.get_by_id_or_raise(999)

    def test_get_current_by_submission(self):
        """get_current_by_submission should filter by is_current."""
        mock_result = Mock(spec=InterviewResultModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )
        result = self.repo.get_current_by_submission(10)
        assert result is mock_result


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultRepository — Update
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultRepositoryUpdate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = InterviewResultRepository(self.session)

    def test_mark_non_current(self):
        """mark_non_current should set is_current=False and flush."""
        mock_result = Mock(spec=InterviewResultModel)
        mock_result.is_current = True
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        result = self.repo.mark_non_current(1)
        assert result.is_current is False
        self.session.flush.assert_called_once()

    def test_mark_non_current_raises_when_not_found(self):
        """mark_non_current should raise InterviewResultNotFoundError."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(InterviewResultNotFoundError):
            self.repo.mark_non_current(999)

    def test_mark_all_non_current(self):
        """mark_all_non_current should update and flush."""
        (
            self.session.query.return_value
            .filter.return_value
            .update.return_value
        ) = 3

        count = self.repo.mark_all_non_current(submission_id=10)
        assert count == 3
        self.session.flush.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# SupplementaryReportRepository — Create
# ═══════════════════════════════════════════════════════════════════════════


class TestSupplementaryReportRepositoryCreate:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = SupplementaryReportRepository(self.session)

    def test_create_adds_and_flushes(self):
        """Verify report is added to session and flushed."""
        result = self.repo.create(
            interview_submission_id=1,
            report_type="technical_breakdown",
            content={"sections": []},
            generated_by="ai",
        )
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        added = self.session.add.call_args[0][0]
        assert isinstance(added, SupplementaryReportModel)
        assert added.report_type == "technical_breakdown"

    def test_create_integrity_error(self):
        """PersistenceError on IntegrityError."""
        orig = Exception("some_fk_violation")
        exc = IntegrityError("INSERT", {}, orig)
        self.session.flush.side_effect = exc

        with pytest.raises(PersistenceError):
            self.repo.create(
                interview_submission_id=1,
                report_type="candidate_summary",
                content={},
                generated_by="ai",
            )


# ═══════════════════════════════════════════════════════════════════════════
# SupplementaryReportRepository — Read
# ═══════════════════════════════════════════════════════════════════════════


class TestSupplementaryReportRepositoryRead:
    def setup_method(self):
        self.session = MagicMock(spec=Session)
        self.repo = SupplementaryReportRepository(self.session)

    def test_get_by_submission_returns_list(self):
        """get_by_submission should return reports list."""
        mock_reports = [Mock(spec=SupplementaryReportModel)]
        (
            self.session.query.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = mock_reports
        result = self.repo.get_by_submission(10)
        assert len(result) == 1

    def test_get_by_submission_with_filter(self):
        """get_by_submission with report_type filter should add filter."""
        mock_reports = []
        (
            self.session.query.return_value
            .filter.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = mock_reports
        result = self.repo.get_by_submission(10, report_type="technical_breakdown")
        assert result == []

    def test_get_by_id_returns_model(self):
        """get_by_id should return the model when found."""
        mock_report = Mock(spec=SupplementaryReportModel)
        self.session.query.return_value.filter.return_value.first.return_value = (
            mock_report
        )
        assert self.repo.get_by_id(1) is mock_report

    def test_get_by_id_returns_none(self):
        """get_by_id should return None when not found."""
        self.session.query.return_value.filter.return_value.first.return_value = None
        assert self.repo.get_by_id(999) is None
