"""
Evaluation API — FastAPI Routes

REST endpoints for:
    1. POST /evaluate          — Trigger exchange evaluation
    2. POST /override          — Human admin override
    3. POST /finalize          — Aggregate into interview result
    4. GET  /evaluations/{id}  — Fetch single evaluation
    5. GET  /exchanges/{id}/evaluations — Evaluations for exchange
    6. GET  /results/{id}      — Fetch interview result(s)
    7. GET  /results/{id}/reports — Supplementary reports

Authorization matrix:
    POST endpoints → admin only
    GET  endpoints → admin or own-candidate

Router is bare ``APIRouter()`` — prefix and tags set in
``app/bootstrap/router_registry.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session,
    get_db_session_with_commit,
    get_identity,
    require_admin,
)
from app.evaluation.api.contracts import (
    DimensionScoreOverride,
    DimensionScoreResponse,
    EvaluateExchangeRequest,
    EvaluationOverrideResponse,
    EvaluationResponse,
    ExchangeEvaluationsResponse,
    FinalizeInterviewRequest,
    GenerateReportRequest,
    HumanOverrideRequest,
    InterviewResultResponse,
    SubmissionReportsResponse,
    SubmissionResultsResponse,
    SupplementaryReportResponse,
)
from app.evaluation.api.dependencies import (
    build_dimension_score_repository,
    build_evaluation_repository,
    build_report_repository,
    build_result_repository,
)
from app.evaluation.persistence.errors import (
    EvaluationNotFoundError,
    InterviewResultNotFoundError,
)
from app.evaluation.persistence.models import (
    EvaluationDimensionScoreModel,
    EvaluationModel,
)
from app.shared.auth_context import IdentityContext
from app.shared.errors import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.shared.observability import get_context_logger

router = APIRouter()
logger = get_context_logger(__name__)


def _fallback_scoring_version() -> str:
    now = datetime.now(timezone.utc)
    return f"fallback-{now.strftime('%Y%m%d%H%M%S%f')}"


def _should_rescore_existing_evaluation(db: Session, evaluation_id: int) -> bool:
    """Detect stale/low-quality AI evaluations that should be regenerated."""
    row = db.execute(
        text(
            "SELECT "
            "  COUNT(*) AS total_dims, "
            "  COALESCE(SUM(CASE WHEN score > 0 THEN 1 ELSE 0 END), 0) AS non_zero_dims, "
            "  COALESCE(SUM(CASE WHEN justification ILIKE '%defaulting to 0%' THEN 1 ELSE 0 END), 0) AS defaulted_dims "
            "FROM evaluation_dimension_scores "
            "WHERE evaluation_id = :eid"
        ),
        {"eid": evaluation_id},
    ).first()

    if row is None:
        return True

    total_dims = int(row.total_dims or 0)
    non_zero_dims = int(row.non_zero_dims or 0)
    defaulted_dims = int(row.defaulted_dims or 0)

    if total_dims == 0:
        return True

    # All-zero with synthetic fallback justifications is considered stale.
    return non_zero_dims == 0 and defaulted_dims > 0


# ---------------------------------------------------------------------------
# 1. POST /evaluate
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=201,
    summary="Trigger exchange evaluation",
    responses={
        200: {"description": "Existing evaluation returned (idempotent)"},
        201: {"description": "New evaluation created"},
        409: {"description": "Evaluation already exists"},
    },
)
async def evaluate_exchange(
    request: EvaluateExchangeRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> EvaluationResponse:
    """
    Trigger evaluation for a specific exchange.

    Idempotent: if a final evaluation already exists and
    ``force_reevaluate`` is false, returns the existing evaluation (200).
    """
    eval_repo = build_evaluation_repository(db)
    dim_repo = build_dimension_score_repository(db)

    # Validate evaluator_type / human_evaluator_id consistency
    if request.evaluator_type in ("human", "hybrid"):
        if request.human_evaluator_id is None:
            raise ValidationError(
                message=(
                    "human_evaluator_id is required when "
                    f"evaluator_type={request.evaluator_type}"
                ),
            )

    # Check for existing final evaluation (idempotency)
    existing = eval_repo.get_final_by_exchange(request.interview_exchange_id)

    if existing and not request.force_reevaluate:
        # Return existing evaluation (200 OK via idempotency)
        dim_scores = _build_dimension_responses(db, existing.id)
        response = EvaluationResponse.from_model(existing, dim_scores)
        # FastAPI will still use 201 from decorator; caller sees the body
        return response

    if existing and request.force_reevaluate:
        eval_repo.mark_non_final(existing.id)

    # Run scoring pipeline
    from app.evaluation.scoring.service import EvaluatorType, ScoringService

    scoring_service = ScoringService(db=db)

    human_scores = None
    if request.evaluator_type in ("human", "hybrid"):
        # Human scores would come from a separate input — for API-triggered
        # evaluation we currently only support AI scoring or hybrid where
        # human scores are provided via the override endpoint post-evaluation.
        pass

    scoring_result = await scoring_service.score_exchange(
        interview_exchange_id=request.interview_exchange_id,
        evaluator_type=EvaluatorType(request.evaluator_type),
        human_scores=human_scores,
        evaluated_by=request.human_evaluator_id,
        force_rescore=False,  # Already handled above
    )

    # Fetch the persisted evaluation to return canonical response
    evaluation = eval_repo.get_by_id(scoring_result.evaluation_id)
    dim_scores = _build_dimension_responses(db, scoring_result.evaluation_id)

    return EvaluationResponse.from_model(evaluation, dim_scores)


# ---------------------------------------------------------------------------
# 2. POST /override
# ---------------------------------------------------------------------------


@router.post(
    "/override",
    response_model=EvaluationOverrideResponse,
    status_code=201,
    summary="Human admin override of dimension scores",
)
async def human_override(
    request: HumanOverrideRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> EvaluationOverrideResponse:
    """
    Apply human overrides to selected dimension scores.

    Creates a new evaluation version with ``evaluator_type=hybrid``,
    marks the original as non-final.
    """
    eval_repo = build_evaluation_repository(db)
    dim_repo = build_dimension_score_repository(db)

    # Fetch original evaluation
    original = eval_repo.get_by_id(request.evaluation_id)
    if original is None:
        raise EvaluationNotFoundError(evaluation_id=request.evaluation_id)

    # Validate overrides against rubric dimensions
    original_dims = dim_repo.get_by_evaluation(original.id)
    dim_lookup = {d.rubric_dimension_id: d for d in original_dims}

    # Validate all override dimension IDs exist and scores are in range
    for override in request.overrides:
        if override.rubric_dimension_id not in dim_lookup:
            raise ValidationError(
                message=(
                    f"Dimension {override.rubric_dimension_id} not found "
                    f"in evaluation {request.evaluation_id}"
                ),
            )
        original_dim = dim_lookup[override.rubric_dimension_id]
        if original_dim.max_score and override.new_score > float(
            original_dim.max_score
        ):
            raise ValidationError(
                message=(
                    f"Score {override.new_score} exceeds max_score "
                    f"{original_dim.max_score} for dimension "
                    f"{override.rubric_dimension_id}"
                ),
            )

    # Mark original as non-final
    eval_repo.mark_non_final(original.id)

    # Build new dimension scores (copy originals, apply overrides)
    override_lookup = {o.rubric_dimension_id: o for o in request.overrides}
    new_scores_data: List[Dict[str, Any]] = []

    for orig_dim in original_dims:
        override = override_lookup.get(orig_dim.rubric_dimension_id)
        if override:
            new_scores_data.append(
                {
                    "rubric_dimension_id": orig_dim.rubric_dimension_id,
                    "score": Decimal(str(override.new_score)),
                    "justification": override.justification,
                    "max_score": orig_dim.max_score,
                }
            )
        else:
            new_scores_data.append(
                {
                    "rubric_dimension_id": orig_dim.rubric_dimension_id,
                    "score": orig_dim.score,
                    "justification": orig_dim.justification,
                    "max_score": orig_dim.max_score,
                }
            )

    # Recalculate total score
    total_score = _recalculate_total(db, original.rubric_id, new_scores_data)

    # Create new evaluation
    new_eval = eval_repo.create(
        interview_exchange_id=original.interview_exchange_id,
        rubric_id=original.rubric_id,
        evaluator_type="hybrid",
        total_score=total_score,
        explanation={"override_reason": request.override_reason},
        is_final=True,
        evaluated_by=identity.user_id,
        model_id=original.model_id,
        scoring_version=original.scoring_version,
    )

    # Create dimension scores
    dim_repo.create_batch(new_eval.id, new_scores_data)

    # Build response
    dim_responses = _build_dimension_responses(db, new_eval.id)

    logger.info(
        "Human override applied",
        extra={
            "new_evaluation_id": new_eval.id,
            "original_evaluation_id": original.id,
            "admin_id": identity.user_id,
        },
    )

    return EvaluationOverrideResponse(
        evaluation_id=new_eval.id,
        previous_evaluation_id=original.id,
        interview_exchange_id=new_eval.interview_exchange_id,
        rubric_id=new_eval.rubric_id,
        evaluator_type=new_eval.evaluator_type,
        total_score=float(new_eval.total_score) if new_eval.total_score else None,
        dimension_scores=dim_responses,
        explanation=new_eval.explanation,
        is_final=new_eval.is_final,
        evaluated_at=new_eval.evaluated_at,
        evaluated_by=new_eval.evaluated_by,
    )


# ---------------------------------------------------------------------------
# 3. POST /finalize
# ---------------------------------------------------------------------------


@router.post(
    "/finalize",
    response_model=InterviewResultResponse,
    status_code=201,
    summary="Finalize interview result (aggregate evaluations)",
    responses={
        200: {"description": "Existing result returned (idempotent)"},
        201: {"description": "New result created"},
        409: {"description": "Result already exists"},
    },
)
async def finalize_interview(
    request: FinalizeInterviewRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> InterviewResultResponse:
    """
    Aggregate all exchange evaluations into a final interview result.

    Delegates to the AggregationService pipeline.
    """
    from app.evaluation.aggregation.service import AggregationService

    service = AggregationService(db=db)

    result_data = await service.aggregate_interview_result(
        submission_id=request.interview_submission_id,
        generated_by=request.generated_by,
        force_reaggregate=request.force_reaggregate,
    )

    # Fetch the persisted result to build canonical response
    result_repo = build_result_repository(db)
    result_model = result_repo.get_current_by_submission(
        request.interview_submission_id
    )

    if result_model is None:
        raise NotFoundError(
            resource_type="InterviewResult",
            resource_id=request.interview_submission_id,
        )

    return InterviewResultResponse.from_model(result_model)


# ---------------------------------------------------------------------------
# 3b. POST /generate-report (candidate accessible)
# ---------------------------------------------------------------------------


@router.post(
    "/generate-report",
    response_model=InterviewResultResponse,
    status_code=201,
    summary="Generate full interview report (evaluate + aggregate)",
    responses={
        200: {"description": "Existing result returned"},
        201: {"description": "New result created"},
    },
)
async def generate_report(
    request: GenerateReportRequest,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session_with_commit),
) -> InterviewResultResponse:
    """
    Generate a full interview report by evaluating all exchanges and
    aggregating the results.

    This endpoint is callable by candidates for their own submissions.
    It runs the complete pipeline:
      1. Score each exchange with AI
      2. Aggregate into an interview result
      3. Return the final result

    If a result already exists and force_regenerate is False,
    returns the existing result (200).
    """
    submission_id = request.interview_submission_id

    # Auth check: candidates can only generate reports for their own submissions
    _authorize_submission_access(db, identity, submission_id)

    # Check for existing result
    result_repo = build_result_repository(db)
    existing = result_repo.get_current_by_submission(submission_id)
    if existing and not request.force_regenerate:
        if existing.final_score is None or existing.normalized_score is None:
            logger.warning(
                "Existing result is incomplete; regenerating report",
                extra={
                    "submission_id": submission_id,
                    "result_id": existing.id,
                },
            )
        else:
            return InterviewResultResponse.from_model(existing)

    # Step 1: Evaluate all exchanges that don't have final evaluations
    exchange_rows = db.execute(
        text(
            "SELECT ie.id "
            "FROM interview_exchanges ie "
            "WHERE ie.interview_submission_id = :sid "
            "ORDER BY ie.sequence_order"
        ),
        {"sid": submission_id},
    ).fetchall()

    if not exchange_rows:
        # If no exchanges exist (e.g. user skipped all or ended early), gracefully return a generic result
        # rather than throwing a 404, so the frontend UI can display it without crashing.
        empty_result = result_repo.create(
            interview_submission_id=submission_id,
            final_score=0.0,
            normalized_score=0.0,
            result_status="completed",
            recommendation="none",
            scoring_version=_fallback_scoring_version(),
            rubric_snapshot=None,
            template_weight_snapshot=None,
            section_scores=None,
            strengths=None,
            weaknesses=None,
            summary_notes="Interview completed with no questions answered.",
            generated_by="system",
        )
        return InterviewResultResponse.from_model(empty_result)

    from app.evaluation.scoring.service import EvaluatorType, ScoringService

    scoring_service = ScoringService(db=db)
    evaluated_count = 0
    failed_exchange_ids: List[int] = []

    for row in exchange_rows:
        exchange_id = row.id
        force_rescore_for_exchange = request.force_regenerate

        # Check if already has a final evaluation
        eval_repo = build_evaluation_repository(db)
        existing_eval = eval_repo.get_final_by_exchange(exchange_id)
        if existing_eval and not request.force_regenerate:
            if _should_rescore_existing_evaluation(db, existing_eval.id):
                logger.warning(
                    "Existing evaluation appears stale/zeroed; rescoring",
                    extra={
                        "exchange_id": exchange_id,
                        "evaluation_id": existing_eval.id,
                    },
                )
                force_rescore_for_exchange = True
            else:
                evaluated_count += 1
                continue

        try:
            await scoring_service.score_exchange(
                interview_exchange_id=exchange_id,
                evaluator_type=EvaluatorType.AI,
                force_rescore=force_rescore_for_exchange,
            )
            evaluated_count += 1
            logger.info(
                "Exchange evaluated",
                extra={"exchange_id": exchange_id, "submission_id": submission_id},
            )
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            failed_exchange_ids.append(exchange_id)
            logger.warning(
                "Failed to evaluate exchange, skipping",
                extra={"exchange_id": exchange_id, "error": str(e)},
            )

    if evaluated_count == 0:
        raise ValidationError(
            message=(
                "Unable to generate report: all exchange evaluations failed. "
                f"submission_id={submission_id}, failed_exchanges={failed_exchange_ids}"
            )
        )

    # Step 2: Aggregate into interview result
    from app.evaluation.aggregation.service import AggregationService

    agg_service = AggregationService(db=db)
    try:
        await agg_service.aggregate_interview_result(
            submission_id=submission_id,
            generated_by="ai",
            force_reaggregate=request.force_regenerate,
        )
    except Exception as e:
        logger.error(
            "Aggregation failed during generate-report",
            extra={"submission_id": submission_id, "error": str(e)},
        )
        raise ValidationError(
            message=(
                "Unable to generate report: aggregation failed after evaluation. "
                f"submission_id={submission_id}, error={e}"
            )
        )

    # Fetch and return the result
    result_model = result_repo.get_current_by_submission(submission_id)
    if result_model is None:
        raise ValidationError(
            message=(
                "Unable to generate report: aggregation did not persist a current result. "
                f"submission_id={submission_id}"
            )
        )

    return InterviewResultResponse.from_model(result_model)


# ---------------------------------------------------------------------------
# 4. GET /evaluations/{evaluation_id}
# ---------------------------------------------------------------------------


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationResponse,
    summary="Fetch single evaluation",
)
async def get_evaluation(
    evaluation_id: int,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> EvaluationResponse:
    """Fetch evaluation by ID with dimension scores."""
    eval_repo = build_evaluation_repository(db)

    evaluation = eval_repo.get_by_id(evaluation_id)
    if evaluation is None:
        raise EvaluationNotFoundError(evaluation_id=evaluation_id)

    # Authorization: admin always allowed; candidate only for own interviews
    _authorize_evaluation_access(db, identity, evaluation)

    dim_scores = _build_dimension_responses(db, evaluation.id)
    return EvaluationResponse.from_model(evaluation, dim_scores)


# ---------------------------------------------------------------------------
# 5. GET /exchanges/{exchange_id}/evaluations
# ---------------------------------------------------------------------------


@router.get(
    "/exchanges/{exchange_id}/evaluations",
    response_model=ExchangeEvaluationsResponse,
    summary="Fetch evaluations for an exchange",
)
async def get_exchange_evaluations(
    exchange_id: int,
    include_history: bool = Query(
        False, description="Include non-final evaluations"
    ),
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> ExchangeEvaluationsResponse:
    """Fetch all evaluations for an exchange (optionally including history)."""
    # Verify exchange exists and check authorization
    _authorize_exchange_access(db, identity, exchange_id)

    eval_repo = build_evaluation_repository(db)

    evaluations = eval_repo.get_all_by_exchange(
        exchange_id, include_non_final=include_history
    )

    responses = []
    for ev in evaluations:
        dim_scores = _build_dimension_responses(db, ev.id)
        responses.append(EvaluationResponse.from_model(ev, dim_scores))

    current_eval_id = None
    for ev in evaluations:
        if ev.is_final:
            current_eval_id = ev.id
            break

    return ExchangeEvaluationsResponse(
        exchange_id=exchange_id,
        evaluations=responses,
        current_evaluation_id=current_eval_id,
    )


# ---------------------------------------------------------------------------
# 6. GET /results/{submission_id}
# ---------------------------------------------------------------------------


@router.get(
    "/results/{submission_id}",
    response_model=SubmissionResultsResponse,
    summary="Fetch interview results for a submission",
)
async def get_submission_results(
    submission_id: int,
    include_history: bool = Query(
        False, description="Include non-current results"
    ),
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> SubmissionResultsResponse:
    """Fetch interview results for a submission."""
    _authorize_submission_access(db, identity, submission_id)

    result_repo = build_result_repository(db)
    results = result_repo.list_by_submission(
        submission_id, include_non_current=include_history
    )

    responses = [InterviewResultResponse.from_model(r) for r in results]

    current_id = None
    for r in results:
        if r.is_current:
            current_id = r.id
            break

    return SubmissionResultsResponse(
        interview_submission_id=submission_id,
        results=responses,
        current_result_id=current_id,
    )


# ---------------------------------------------------------------------------
# 7. GET /results/{submission_id}/reports
# ---------------------------------------------------------------------------


@router.get(
    "/results/{submission_id}/reports",
    response_model=SubmissionReportsResponse,
    summary="Fetch supplementary reports for a submission",
)
async def get_submission_reports(
    submission_id: int,
    report_type: Optional[str] = Query(
        None, description="Filter by report type"
    ),
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> SubmissionReportsResponse:
    """Fetch supplementary reports attached to a submission."""
    _authorize_submission_access(db, identity, submission_id)

    report_repo = build_report_repository(db)
    reports = report_repo.get_by_submission(
        submission_id, report_type=report_type
    )

    return SubmissionReportsResponse(
        interview_submission_id=submission_id,
        reports=[SupplementaryReportResponse.from_model(r) for r in reports],
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _build_dimension_responses(
    db: Session,
    evaluation_id: int,
) -> List[DimensionScoreResponse]:
    """
    Build DimensionScoreResponse list for an evaluation.

    Joins dimension_scores with rubric_dimensions for names and weights.
    """
    rows = db.execute(
        text(
            "SELECT eds.rubric_dimension_id, eds.score, eds.max_score, "
            "       eds.justification, rd.dimension_name, rd.weight "
            "FROM evaluation_dimension_scores eds "
            "JOIN rubric_dimensions rd ON rd.id = eds.rubric_dimension_id "
            "WHERE eds.evaluation_id = :eid "
            "ORDER BY rd.sequence_order"
        ),
        {"eid": evaluation_id},
    ).fetchall()

    return [
        DimensionScoreResponse(
            rubric_dimension_id=row.rubric_dimension_id,
            dimension_name=row.dimension_name,
            score=float(row.score) if row.score else 0.0,
            max_score=float(row.max_score) if row.max_score else None,
            weight=float(row.weight) if row.weight else None,
            justification=row.justification,
        )
        for row in rows
    ]


def _recalculate_total(
    db: Session,
    rubric_id: Optional[int],
    scores_data: List[Dict[str, Any]],
) -> Decimal:
    """
    Recalculate total score from dimension scores using rubric weights.

    Falls back to simple average if rubric/weights not available.
    """
    if not scores_data:
        return Decimal("0")

    # Fetch rubric dimension weights
    weights: Dict[int, Decimal] = {}
    if rubric_id:
        rows = db.execute(
            text(
                "SELECT id, weight FROM rubric_dimensions "
                "WHERE rubric_id = :rid"
            ),
            {"rid": rubric_id},
        ).fetchall()
        weights = {
            row.id: Decimal(str(row.weight)) if row.weight else Decimal("1")
            for row in rows
        }

    total_weighted = Decimal("0")
    total_weight = Decimal("0")

    for sd in scores_data:
        dim_id = sd["rubric_dimension_id"]
        score = Decimal(str(sd["score"]))
        max_score = Decimal(str(sd.get("max_score") or 5))
        weight = weights.get(dim_id, Decimal("1"))

        # Normalized dimension contribution
        normalized = (score / max_score) * 100 if max_score > 0 else Decimal("0")
        total_weighted += normalized * weight
        total_weight += weight

    if total_weight == 0:
        return Decimal("0")

    return (total_weighted / total_weight).quantize(Decimal("0.01"))


def _authorize_evaluation_access(
    db: Session,
    identity: IdentityContext,
    evaluation: EvaluationModel,
) -> None:
    """
    Verify the requester can access an evaluation.

    Admins: always allowed.
    Candidates: only if the evaluation belongs to their interview.
    """
    if identity.user_type.value == "admin":
        return

    # Candidate: check that the exchange belongs to their submission
    row = db.execute(
        text(
            "SELECT is2.candidate_id "
            "FROM interview_exchanges ie "
            "JOIN interview_submissions is2 "
            "  ON is2.id = ie.interview_submission_id "
            "WHERE ie.id = :eid"
        ),
        {"eid": evaluation.interview_exchange_id},
    ).first()

    if not row:
        raise NotFoundError(
            resource_type="Evaluation", resource_id=evaluation.id
        )
    if row.candidate_id != identity.candidate_id:
        # Return 404 instead of 403 to avoid leaking evaluation existence
        raise NotFoundError(
            resource_type="Evaluation", resource_id=evaluation.id
        )


def _authorize_exchange_access(
    db: Session,
    identity: IdentityContext,
    exchange_id: int,
) -> None:
    """Verify the requester can access an exchange's evaluations."""
    if identity.user_type.value == "admin":
        return

    row = db.execute(
        text(
            "SELECT is2.candidate_id "
            "FROM interview_exchanges ie "
            "JOIN interview_submissions is2 "
            "  ON is2.id = ie.interview_submission_id "
            "WHERE ie.id = :eid"
        ),
        {"eid": exchange_id},
    ).first()

    if not row:
        raise NotFoundError(
            resource_type="Exchange", resource_id=exchange_id
        )
    if row.candidate_id != identity.candidate_id:
        # Return 404 instead of 403 to avoid leaking exchange existence
        raise NotFoundError(
            resource_type="Exchange", resource_id=exchange_id
        )


def _authorize_submission_access(
    db: Session,
    identity: IdentityContext,
    submission_id: int,
) -> None:
    """Verify the requester can access a submission's results."""
    if identity.user_type.value == "admin":
        return

    row = db.execute(
        text(
            "SELECT candidate_id FROM interview_submissions WHERE id = :sid"
        ),
        {"sid": submission_id},
    ).first()

    if not row:
        raise NotFoundError(
            resource_type="Submission", resource_id=submission_id
        )
    if row.candidate_id != identity.candidate_id:
        # Return 404 instead of 403 to avoid leaking submission existence
        raise NotFoundError(
            resource_type="Submission", resource_id=submission_id
        )
