"""
Evaluation Persistence — Repository Layer

Provides repository classes for all evaluation-owned tables.
Follows the repository patterns established in the codebase:
    - Constructor takes ``Session``
    - Mutations call ``session.flush()`` (never ``commit()``)
    - Commit managed by caller (``get_db_session_with_commit``)
    - Raises ``NotFoundError`` for missing resources
    - Returns ORM model instances directly

Repositories:
    - EvaluationRepository
    - DimensionScoreRepository
    - InterviewResultRepository
    - SupplementaryReportRepository
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, text
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
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


# ---------------------------------------------------------------------------
# Evaluation Repository
# ---------------------------------------------------------------------------


class EvaluationRepository:
    """
    Repository for the ``evaluations`` table.

    Enforces:
        - One final evaluation per exchange (via partial unique index)
        - Versioning via is_final flag
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        interview_exchange_id: int,
        rubric_id: Optional[int],
        evaluator_type: str,
        total_score: Decimal,
        explanation: Any = None,
        is_final: bool = True,
        evaluated_at: Optional[datetime] = None,
        evaluated_by: Optional[int] = None,
        model_id: Optional[int] = None,
        scoring_version: Optional[str] = None,
    ) -> EvaluationModel:
        """
        Create a new evaluation record.

        Args:
            interview_exchange_id: FK to interview_exchanges.
            rubric_id: FK to rubrics (nullable).
            evaluator_type: One of 'ai', 'human', 'hybrid'.
            total_score: Computed total score.
            explanation: JSONB explanation/comment.
            is_final: Whether this is the final (current) evaluation.
            evaluated_at: Timestamp of evaluation.
            evaluated_by: FK to users (human evaluator).
            model_id: FK to models (AI model used).
            scoring_version: Algorithm version string.

        Returns:
            Created EvaluationModel.

        Raises:
            DuplicateEvaluationError: Partial unique constraint violated.
            PersistenceError: Other database error.
        """
        evaluation = EvaluationModel(
            interview_exchange_id=interview_exchange_id,
            rubric_id=rubric_id,
            evaluator_type=evaluator_type,
            total_score=total_score,
            explanation=explanation,
            is_final=is_final,
            evaluated_at=evaluated_at or datetime.now(timezone.utc),
            evaluated_by=evaluated_by,
            model_id=model_id,
            scoring_version=scoring_version,
        )

        self._session.add(evaluation)

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if "uq_evaluations_exchange_final" in str(exc):
                raise DuplicateEvaluationError(
                    interview_exchange_id=interview_exchange_id,
                ) from exc
            raise PersistenceError(
                message=f"Failed to create evaluation: {exc}",
                error_code="EVAL_CREATE_FAILED",
            ) from exc

        logger.info(
            "Evaluation created",
            extra={
                "evaluation_id": evaluation.id,
                "exchange_id": interview_exchange_id,
                "evaluator_type": evaluator_type,
            },
        )
        return evaluation

    def get_by_id(self, evaluation_id: int) -> Optional[EvaluationModel]:
        """Fetch evaluation by primary key."""
        return (
            self._session.query(EvaluationModel)
            .filter(EvaluationModel.id == evaluation_id)
            .first()
        )

    def get_by_id_or_raise(self, evaluation_id: int) -> EvaluationModel:
        """Fetch evaluation by primary key or raise NotFound."""
        evaluation = self.get_by_id(evaluation_id)
        if evaluation is None:
            raise EvaluationNotFoundError(evaluation_id=evaluation_id)
        return evaluation

    def get_final_by_exchange(
        self,
        interview_exchange_id: int,
    ) -> Optional[EvaluationModel]:
        """Fetch the final (current) evaluation for an exchange."""
        return (
            self._session.query(EvaluationModel)
            .filter(
                and_(
                    EvaluationModel.interview_exchange_id == interview_exchange_id,
                    EvaluationModel.is_final.is_(True),
                )
            )
            .first()
        )

    def get_all_by_exchange(
        self,
        interview_exchange_id: int,
        *,
        include_non_final: bool = False,
    ) -> List[EvaluationModel]:
        """
        Fetch evaluations for an exchange (optionally including historical).

        Results ordered by created_at descending (newest first).
        """
        query = self._session.query(EvaluationModel).filter(
            EvaluationModel.interview_exchange_id == interview_exchange_id,
        )
        if not include_non_final:
            query = query.filter(EvaluationModel.is_final.is_(True))
        return query.order_by(EvaluationModel.created_at.desc()).all()

    def list_by_submission(
        self,
        submission_id: int,
        *,
        is_final: Optional[bool] = True,
    ) -> List[EvaluationModel]:
        """
        Fetch all evaluations for exchanges belonging to a submission.

        Uses a join through interview_exchanges to filter by submission.
        """
        query_text = text(
            "SELECT e.* FROM evaluations e "
            "JOIN interview_exchanges ie ON ie.id = e.interview_exchange_id "
            "WHERE ie.interview_submission_id = :submission_id"
            + (" AND e.is_final = :is_final" if is_final is not None else "")
            + " ORDER BY e.created_at DESC"
        )
        params: Dict[str, Any] = {"submission_id": submission_id}
        if is_final is not None:
            params["is_final"] = is_final

        rows = self._session.execute(query_text, params).fetchall()

        # Map raw rows back to ORM models
        if not rows:
            return []

        evaluation_ids = [row.id for row in rows]
        return (
            self._session.query(EvaluationModel)
            .filter(EvaluationModel.id.in_(evaluation_ids))
            .order_by(EvaluationModel.created_at.desc())
            .all()
        )

    def mark_non_final(self, evaluation_id: int) -> EvaluationModel:
        """
        Mark an evaluation as non-final (for re-evaluation flow).

        Returns the updated model.

        Raises:
            EvaluationNotFoundError: Evaluation does not exist.
        """
        evaluation = self.get_by_id_or_raise(evaluation_id)
        evaluation.is_final = False
        self._session.flush()

        logger.info(
            "Evaluation marked non-final",
            extra={"evaluation_id": evaluation_id},
        )
        return evaluation

    def count_final_by_submission(self, submission_id: int) -> int:
        """Count final evaluations for all exchanges in a submission."""
        result = self._session.execute(
            text(
                "SELECT COUNT(*) FROM evaluations e "
                "JOIN interview_exchanges ie ON ie.id = e.interview_exchange_id "
                "WHERE ie.interview_submission_id = :sid AND e.is_final = true"
            ),
            {"sid": submission_id},
        ).scalar()
        return result or 0


# ---------------------------------------------------------------------------
# Dimension Score Repository
# ---------------------------------------------------------------------------


class DimensionScoreRepository:
    """Repository for the ``evaluation_dimension_scores`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(
        self,
        evaluation_id: int,
        scores: List[Dict[str, Any]],
    ) -> List[EvaluationDimensionScoreModel]:
        """
        Create dimension scores in batch for an evaluation.

        Args:
            evaluation_id: Parent evaluation ID.
            scores: List of dicts with keys:
                rubric_dimension_id, score, justification, max_score (optional).

        Returns:
            List of created models.

        Raises:
            PersistenceError: Database error.
        """
        models = []
        for score_data in scores:
            model = EvaluationDimensionScoreModel(
                evaluation_id=evaluation_id,
                rubric_dimension_id=score_data["rubric_dimension_id"],
                score=score_data["score"],
                justification=score_data.get("justification"),
                max_score=score_data.get("max_score"),
            )
            self._session.add(model)
            models.append(model)

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise PersistenceError(
                message=f"Failed to create dimension scores: {exc}",
                error_code="DIM_SCORE_CREATE_FAILED",
            ) from exc

        return models

    def get_by_evaluation(
        self,
        evaluation_id: int,
    ) -> List[EvaluationDimensionScoreModel]:
        """Fetch all dimension scores for an evaluation."""
        return (
            self._session.query(EvaluationDimensionScoreModel)
            .filter(
                EvaluationDimensionScoreModel.evaluation_id == evaluation_id,
            )
            .all()
        )

    def update_score(
        self,
        dimension_score_id: int,
        *,
        new_score: Decimal,
        justification: Optional[str] = None,
    ) -> EvaluationDimensionScoreModel:
        """
        Update a specific dimension score (for human override flow).

        Returns the updated model.

        Raises:
            PersistenceError: Record not found or DB error.
        """
        model = (
            self._session.query(EvaluationDimensionScoreModel)
            .filter(EvaluationDimensionScoreModel.id == dimension_score_id)
            .first()
        )
        if model is None:
            raise PersistenceError(
                message=f"Dimension score {dimension_score_id} not found",
                error_code="DIM_SCORE_NOT_FOUND",
            )

        model.score = new_score
        if justification is not None:
            model.justification = justification
        self._session.flush()
        return model


# ---------------------------------------------------------------------------
# Interview Result Repository
# ---------------------------------------------------------------------------


class InterviewResultRepository:
    """
    Repository for the ``interview_results`` table.

    Enforces:
        - One current result per submission (via partial unique index)
        - Versioning via is_current flag
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        interview_submission_id: int,
        final_score: Optional[Decimal],
        normalized_score: Optional[Decimal],
        result_status: str,
        recommendation: str,
        scoring_version: str,
        rubric_snapshot: Optional[Dict],
        template_weight_snapshot: Optional[Dict],
        section_scores: Optional[Dict],
        strengths: Optional[str],
        weaknesses: Optional[str],
        summary_notes: Optional[str],
        generated_by: str,
        model_id: Optional[int] = None,
        is_current: bool = True,
        computed_at: Optional[datetime] = None,
    ) -> InterviewResultModel:
        """
        Create an interview result record.

        Raises:
            DuplicateResultError: Partial unique constraint violated.
            PersistenceError: Other database error.
        """
        result = InterviewResultModel(
            interview_submission_id=interview_submission_id,
            final_score=final_score,
            normalized_score=normalized_score,
            result_status=result_status,
            recommendation=recommendation,
            scoring_version=scoring_version,
            rubric_snapshot=rubric_snapshot,
            template_weight_snapshot=template_weight_snapshot,
            section_scores=section_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            summary_notes=summary_notes,
            generated_by=generated_by,
            model_id=model_id,
            is_current=is_current,
            computed_at=computed_at or datetime.now(timezone.utc),
        )

        self._session.add(result)

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if "uq_interview_results_submission_current" in str(exc):
                raise DuplicateResultError(
                    submission_id=interview_submission_id,
                ) from exc
            raise PersistenceError(
                message=f"Failed to create interview result: {exc}",
                error_code="RESULT_CREATE_FAILED",
            ) from exc

        logger.info(
            "Interview result created",
            extra={
                "result_id": result.id,
                "submission_id": interview_submission_id,
            },
        )
        return result

    def get_by_id(self, result_id: int) -> Optional[InterviewResultModel]:
        """Fetch result by primary key."""
        return (
            self._session.query(InterviewResultModel)
            .filter(InterviewResultModel.id == result_id)
            .first()
        )

    def get_by_id_or_raise(self, result_id: int) -> InterviewResultModel:
        """Fetch result by primary key or raise NotFound."""
        result = self.get_by_id(result_id)
        if result is None:
            raise InterviewResultNotFoundError(result_id=result_id)
        return result

    def get_current_by_submission(
        self,
        submission_id: int,
    ) -> Optional[InterviewResultModel]:
        """Fetch the current (active) result for a submission."""
        return (
            self._session.query(InterviewResultModel)
            .filter(
                and_(
                    InterviewResultModel.interview_submission_id == submission_id,
                    InterviewResultModel.is_current.is_(True),
                )
            )
            .first()
        )

    def list_by_submission(
        self,
        submission_id: int,
        *,
        include_non_current: bool = False,
    ) -> List[InterviewResultModel]:
        """
        Fetch results for a submission (optionally including historical).

        Results ordered by created_at descending (newest first).
        """
        query = self._session.query(InterviewResultModel).filter(
            InterviewResultModel.interview_submission_id == submission_id,
        )
        if not include_non_current:
            query = query.filter(InterviewResultModel.is_current.is_(True))
        return query.order_by(InterviewResultModel.created_at.desc()).all()

    def mark_non_current(self, result_id: int) -> InterviewResultModel:
        """
        Mark a result as non-current (for re-aggregation versioning).

        Raises:
            InterviewResultNotFoundError: Result does not exist.
        """
        result = self.get_by_id_or_raise(result_id)
        result.is_current = False
        self._session.flush()

        logger.info(
            "Interview result marked non-current",
            extra={"result_id": result_id},
        )
        return result

    def mark_all_non_current(self, submission_id: int) -> int:
        """
        Mark ALL current results for a submission as non-current.

        Returns the number of rows updated.
        """
        count = (
            self._session.query(InterviewResultModel)
            .filter(
                and_(
                    InterviewResultModel.interview_submission_id == submission_id,
                    InterviewResultModel.is_current.is_(True),
                )
            )
            .update({"is_current": False})
        )
        self._session.flush()
        return count


# ---------------------------------------------------------------------------
# Supplementary Report Repository
# ---------------------------------------------------------------------------


class SupplementaryReportRepository:
    """Repository for the ``supplementary_reports`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        interview_submission_id: int,
        report_type: str,
        content: Dict[str, Any],
        generated_by: str,
        model_id: Optional[int] = None,
    ) -> SupplementaryReportModel:
        """
        Create a supplementary report.

        Args:
            interview_submission_id: FK to interview_submissions.
            report_type: One of report_type enum values.
            content: JSONB report data.
            generated_by: Who generated the report.
            model_id: FK to models (if AI-generated).

        Returns:
            Created SupplementaryReportModel.
        """
        report = SupplementaryReportModel(
            interview_submission_id=interview_submission_id,
            report_type=report_type,
            content=content,
            generated_by=generated_by,
            model_id=model_id,
        )
        self._session.add(report)

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise PersistenceError(
                message=f"Failed to create supplementary report: {exc}",
                error_code="REPORT_CREATE_FAILED",
            ) from exc

        return report

    def get_by_submission(
        self,
        submission_id: int,
        *,
        report_type: Optional[str] = None,
    ) -> List[SupplementaryReportModel]:
        """
        Fetch reports for a submission, optionally filtered by type.
        """
        query = self._session.query(SupplementaryReportModel).filter(
            SupplementaryReportModel.interview_submission_id == submission_id,
        )
        if report_type:
            query = query.filter(
                SupplementaryReportModel.report_type == report_type,
            )
        return query.order_by(SupplementaryReportModel.created_at.desc()).all()

    def get_by_id(
        self,
        report_id: int,
    ) -> Optional[SupplementaryReportModel]:
        """Fetch a single report by primary key."""
        return (
            self._session.query(SupplementaryReportModel)
            .filter(SupplementaryReportModel.id == report_id)
            .first()
        )
