"""
Aggregation Service

Orchestrates the complete interview-level aggregation pipeline:
1. Verify all exchanges evaluated
2. Fetch template section weights
3. Aggregate by section
4. Calculate weighted final score
5. Normalize to 0–100
6. Determine recommendation
7. Adjust for proctoring risk (feature-flagged)
8. Generate AI summary
9. Create snapshots
10. Persist interview result

Design:
- Single entry point for all aggregation operations
- Coordinates section_aggregator, normalizer, recommendation, proctoring_adjuster, summary_generator
- Handles persistence transactions and versioning
- Enforces "one current result per submission" invariant
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.evaluation.aggregation.config import AggregationConfig, get_aggregation_config
from app.evaluation.aggregation.errors import (
    AggregationAlreadyExistsError,
    AggregationError,
    IncompleteEvaluationError,
    InterviewNotFoundError,
    NoExchangesError,
    TemplateWeightsNotFoundError,
)
from app.evaluation.aggregation.normalizer import ScoreNormalizer, calculate_final_score
from app.evaluation.aggregation.proctoring_adjuster import ProctoringAdjuster
from app.evaluation.aggregation.recommendation import RecommendationEngine
from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    ExchangeSummaryDTO,
    InterviewResultData,
    ProctoringRiskDTO,
    SectionScore,
    SummaryData,
)
from app.evaluation.aggregation.section_aggregator import SectionAggregator
from app.evaluation.aggregation.summary_generator import ExchangeDetail, SummaryGenerator
from app.evaluation.persistence.models import (
    InterviewResultModel as InterviewResult,
    SupplementaryReportModel as SupplementaryReport,
)
from app.shared.observability import get_context_logger

if TYPE_CHECKING:
    from app.ai.llm import BaseLLMProvider

logger = get_context_logger(__name__)


SECTION_NAME_ALIASES: Dict[str, str] = {
    "resume": "resume_analysis",
    "resume_experience": "resume_analysis",
    "resume_and_experience_analysis": "resume_analysis",
    "self_intro": "self_introduction",
    "selfintroduction": "self_introduction",
    "behavioral": "behavioral_assessment",
    "behavioral_round": "behavioral_assessment",
    "coding": "live_coding",
    "coding_round": "live_coding",
    "technical": "technical_concepts",
    "technical_depth": "technical_concepts",
    "complexity": "complexity_analysis",
}


# -----------------------------------------------------------------------------
# SQLAlchemy ORM Models
#
# Inline models migrated to app.evaluation.persistence.models (DEV-49).
# Imported above as InterviewResult / SupplementaryReport for compatibility.
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Aggregation Service
# -----------------------------------------------------------------------------


class AggregationService:
    """
    Main orchestrator for interview-level aggregation.

    Handles the complete pipeline from fetching evaluations through
    persisting the final interview result.
    """

    def __init__(
        self,
        db: Session,
        config: Optional[AggregationConfig] = None,
        llm_provider: Optional["BaseLLMProvider"] = None,
    ) -> None:
        """
        Initialize aggregation service.

        Args:
            db: Database session for persistence.
            config: Aggregation configuration (uses defaults if None).
            llm_provider: LLM provider for summary generation.
        """
        self._db = db
        self._config = config or get_aggregation_config()

        # Initialize pipeline components
        self._aggregator = SectionAggregator()
        self._normalizer = ScoreNormalizer(config=self._config)
        self._recommendation_engine = RecommendationEngine(config=self._config)
        self._proctoring_adjuster = ProctoringAdjuster(config=self._config)
        self._summary_generator = SummaryGenerator(
            llm_provider=llm_provider, config=self._config, db=db
        )

    # ── Public API ─────────────────────────────────────────────────────

    async def aggregate_interview_result(
        self,
        submission_id: int,
        generated_by: str = "ai",
        force_reaggregate: bool = False,
    ) -> InterviewResultData:
        """
        Complete aggregation pipeline for an interview.

        Steps:
            1.  Verify submission exists
            2.  Check for existing current result
            3.  Fetch all exchanges and final evaluations
            4.  Verify completeness (all exchanges evaluated)
            5.  Fetch template section weights
            6.  Aggregate by section
            7.  Calculate weighted final score
            8.  Normalize to 0–100
            9.  Determine recommendation
            10. Adjust for proctoring risk (feature-flagged)
            11. Generate AI summary
            12. Build snapshots
            13. Persist interview result
            14. Return result data

        Args:
            submission_id: Interview submission to aggregate.
            generated_by: Who triggered aggregation ("ai" | "human" | "system").
            force_reaggregate: If True, mark existing result as non-current
                               and create a new version.

        Returns:
            InterviewResultData with all computed aggregation fields.

        Raises:
            InterviewNotFoundError: Submission does not exist.
            AggregationAlreadyExistsError: Current result exists (without force).
            IncompleteEvaluationError: Not all exchanges have final evaluations.
            NoExchangesError: Interview has zero exchanges.
            TemplateWeightsNotFoundError: Template section weights unavailable.
        """
        logger.info(
            "Starting aggregation pipeline",
            extra={
                "submission_id": submission_id,
                "generated_by": generated_by,
                "force_reaggregate": force_reaggregate,
            },
        )

        # Step 1: Verify submission exists
        submission_row = self._fetch_submission(submission_id)

        # Step 2: Check existing result
        existing_current_result = self._check_existing_result(
            submission_id,
            force_reaggregate,
        )

        # Step 3: Fetch exchanges and evaluations
        exchanges = self._fetch_exchanges(submission_id)
        if not exchanges:
            raise NoExchangesError(submission_id=submission_id)

        evaluations = self._fetch_final_evaluations(submission_id)

        # Step 4: Verify completeness
        self._verify_completeness(submission_id, exchanges, evaluations)

        # Step 5: Fetch template weights
        template_id = submission_row["template_id"]
        template_weights = self._fetch_template_weights(template_id)
        template_weights = self._apply_conditional_section_rules(
            template_weights=template_weights,
            exchanges=exchanges,
        )

        # Step 6: Aggregate by section
        section_scores = self._aggregator.aggregate(
            exchanges=exchanges,
            evaluations=evaluations,
            template_weights=template_weights,
        )

        # Step 7: Calculate final score
        final_score = calculate_final_score(
            section_scores, decimal_places=self._config.score_decimal_places
        )

        # Step 8: Normalize
        normalized_score = self._normalizer.normalize(final_score, section_scores)

        # Step 9: Determine recommendation
        recommendation = self._recommendation_engine.determine(normalized_score)

        # Step 10: Proctoring adjustment
        proctoring_risk = self._fetch_proctoring_risk(submission_id)
        recommendation = self._proctoring_adjuster.adjust(
            recommendation, proctoring_risk
        )

        # Step 11: Fetch exchange details for evidence-based summary
        exchange_detail_list = self._fetch_exchange_details(
            submission_id, exchanges, evaluations
        )

        # Step 12: Generate summary
        summary = await self._summary_generator.generate(
            section_scores=section_scores,
            normalized_score=normalized_score,
            recommendation=recommendation,
            exchange_details=exchange_detail_list,
        )

        # Step 13: Build snapshots
        rubric_snapshot = self._build_rubric_snapshot(template_id)
        template_weight_snapshot = {
            name: {"weight": weight} for name, weight in template_weights.items()
        }

        # Step 14: Persist
        result_data = InterviewResultData(
            interview_submission_id=submission_id,
            final_score=final_score,
            normalized_score=normalized_score,
            result_status="completed",
            recommendation=recommendation,
            section_scores=section_scores,
            strengths=summary.strengths,
            weaknesses=summary.weaknesses,
            summary_notes=summary.summary_notes,
            rubric_snapshot=rubric_snapshot,
            template_weight_snapshot=template_weight_snapshot,
            scoring_version=self._config.scoring_version,
            generated_by=generated_by,
            model_id=None,
        )

        self._persist_result(
            result_data,
            proctoring_risk,
            replace_existing_result_id=(existing_current_result.id if existing_current_result else None),
        )

        logger.info(
            "Aggregation complete",
            extra={
                "submission_id": submission_id,
                "final_score": str(final_score),
                "normalized_score": str(normalized_score),
                "recommendation": recommendation,
            },
        )

        return result_data

    def get_current_result(
        self, submission_id: int
    ) -> Optional[InterviewResultData]:
        """
        Fetch the current interview result for a submission.

        Args:
            submission_id: Interview submission ID.

        Returns:
            InterviewResultData or None if no current result exists.
        """
        row = (
            self._db.query(InterviewResult)
            .filter(
                and_(
                    InterviewResult.interview_submission_id == submission_id,
                    InterviewResult.is_current == True,  # noqa: E712
                )
            )
            .first()
        )

        if not row:
            return None

        return self._row_to_result_data(row)

    def _apply_conditional_section_rules(
        self,
        template_weights: Dict[str, int],
        exchanges: List[ExchangeSummaryDTO],
    ) -> Dict[str, int]:
        """
        Remove conditional sections that are not applicable for this submission.

        Business rule:
        - `complexity_analysis` is only applicable when a coding round is present.
        """
        adjusted_weights = dict(template_weights)

        has_coding_round = any(ex.section_name == "live_coding" for ex in exchanges)
        if not has_coding_round and "complexity_analysis" in adjusted_weights:
            adjusted_weights.pop("complexity_analysis", None)
            logger.info(
                "Excluded complexity_analysis from aggregation (no coding round present)",
                extra={
                    "exchange_sections": sorted({ex.section_name for ex in exchanges}),
                },
            )

        return adjusted_weights

    @staticmethod
    def _normalize_section_name(section_name: Optional[str]) -> str:
        raw = (section_name or "unknown").strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
        if not normalized:
            return "unknown"
        compact = normalized.replace("_", "")
        return (
            SECTION_NAME_ALIASES.get(normalized)
            or SECTION_NAME_ALIASES.get(compact)
            or normalized
        )

    def _extract_enabled_sections_from_structure(self, structure: Dict[str, Any]) -> Set[str]:
        enabled: Set[str] = set()

        sections = structure.get("sections")
        if isinstance(sections, dict):
            for key, section in sections.items():
                normalized_key = self._normalize_section_name(str(key))
                if not isinstance(section, dict) or section.get("enabled", True):
                    enabled.add(normalized_key)
            if enabled:
                return enabled

        if isinstance(sections, list):
            for idx, section in enumerate(sections):
                if isinstance(section, dict):
                    if section.get("enabled", True) is False:
                        continue
                    section_name = (
                        section.get("section_key")
                        or section.get("section_name")
                        or section.get("name")
                        or section.get("id")
                        or f"section_{idx}"
                    )
                else:
                    section_name = str(section)
                enabled.add(self._normalize_section_name(str(section_name)))
            if enabled:
                return enabled

        scoring_config = structure.get("scoring_configuration")
        if isinstance(scoring_config, dict):
            evaluation_dimensions = scoring_config.get("evaluation_dimensions")
            if isinstance(evaluation_dimensions, dict):
                for key, value in evaluation_dimensions.items():
                    if bool(value):
                        enabled.add(self._normalize_section_name(str(key)))

        return enabled

    # ── Internal: Data Fetching ────────────────────────────────────────

    def _fetch_submission(self, submission_id: int) -> Dict[str, Any]:
        """Fetch interview submission row."""
        result = self._db.execute(
            text(
                "SELECT id, template_id, status "
                "FROM interview_submissions "
                "WHERE id = :sid"
            ),
            {"sid": submission_id},
        ).first()

        if not result:
            raise InterviewNotFoundError(submission_id=submission_id)

        return {"id": result.id, "template_id": result.template_id, "status": result.status}

    def _fetch_exchanges(self, submission_id: int) -> List[ExchangeSummaryDTO]:
        """Fetch all exchanges for a submission with section assignment."""
        rows = self._db.execute(
            text(
                "SELECT id, sequence_order, content_metadata "
                "FROM interview_exchanges "
                "WHERE interview_submission_id = :sid "
                "ORDER BY sequence_order"
            ),
            {"sid": submission_id},
        ).fetchall()

        exchanges: List[ExchangeSummaryDTO] = []
        for row in rows:
            # Extract section_name from content_metadata JSONB
            metadata = row.content_metadata or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            raw_section_name = (
                metadata.get("section_name")
                or metadata.get("section")
                or metadata.get("section_key")
                or metadata.get("question_type")
                or "unknown"
            )
            section_name = self._normalize_section_name(str(raw_section_name))

            exchanges.append(
                ExchangeSummaryDTO(
                    exchange_id=row.id,
                    sequence_order=row.sequence_order,
                    section_name=section_name,
                )
            )

        return exchanges

    def _fetch_final_evaluations(
        self, submission_id: int
    ) -> List[EvaluationSummaryDTO]:
        """Fetch all final evaluations for exchanges in a submission."""
        rows = self._db.execute(
            text(
                "SELECT e.id AS evaluation_id, "
                "       e.interview_exchange_id, "
                "       e.total_score, "
                "       e.evaluator_type "
                "FROM evaluations e "
                "JOIN interview_exchanges ie "
                "  ON ie.id = e.interview_exchange_id "
                "WHERE ie.interview_submission_id = :sid "
                "  AND e.is_final = true"
            ),
            {"sid": submission_id},
        ).fetchall()

        return [
            EvaluationSummaryDTO(
                evaluation_id=row.evaluation_id,
                interview_exchange_id=row.interview_exchange_id,
                total_score=Decimal(str(row.total_score)),
                evaluator_type=row.evaluator_type,
            )
            for row in rows
        ]

    def _fetch_exchange_details(
        self,
        submission_id: int,
        exchanges: List[ExchangeSummaryDTO],
        evaluations: List[EvaluationSummaryDTO],
    ) -> List[ExchangeDetail]:
        """
        Fetch rich exchange data for evidence-based summary generation.

        Joins question text, response, difficulty, and per-dimension scores
        for each exchange.
        """
        eval_lookup = {e.interview_exchange_id: e for e in evaluations}

        # Fetch question text, response, difficulty for all exchanges
        rows = self._db.execute(
            text(
                "SELECT id, sequence_order, question_text, "
                "       response_text, response_code, "
                "       difficulty_at_time, content_metadata "
                "FROM interview_exchanges "
                "WHERE interview_submission_id = :sid "
                "ORDER BY sequence_order"
            ),
            {"sid": submission_id},
        ).fetchall()

        details: List[ExchangeDetail] = []

        for row in rows:
            metadata = row.content_metadata or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            section_name = metadata.get("section_name", "unknown")

            # Fetch dimension scores if evaluation exists
            eval_data = eval_lookup.get(row.id)
            dim_scores: List[Dict[str, Any]] = []
            total_score = None

            if eval_data:
                total_score = float(eval_data.total_score)
                dim_rows = self._db.execute(
                    text(
                        "SELECT eds.score, eds.max_score, eds.justification, "
                        "       rd.dimension_name "
                        "FROM evaluation_dimension_scores eds "
                        "JOIN rubric_dimensions rd ON rd.id = eds.rubric_dimension_id "
                        "WHERE eds.evaluation_id = :eid"
                    ),
                    {"eid": eval_data.evaluation_id},
                ).fetchall()

                dim_scores = [
                    {
                        "dimension_name": dr.dimension_name,
                        "score": float(dr.score),
                        "max_score": float(dr.max_score) if dr.max_score else 10,
                        "justification": dr.justification,
                    }
                    for dr in dim_rows
                ]

            response = row.response_text or row.response_code or ""

            details.append(
                ExchangeDetail(
                    sequence_order=row.sequence_order,
                    section_name=section_name,
                    question_text=row.question_text or "",
                    response_text=response,
                    difficulty=row.difficulty_at_time,
                    total_score=total_score,
                    dimension_scores=dim_scores,
                )
            )

        return details

    def _fetch_template_weights(self, template_id: int) -> Dict[str, int]:
        """
        Fetch section weights from interview template.

        Reads scoring_configuration.section_weights from template_structure JSONB.
        Falls back to equal weights (1) per section when not found.
        """
        result = self._db.execute(
            text(
                "SELECT template_structure "
                "FROM interview_templates "
                "WHERE id = :tid"
            ),
            {"tid": template_id},
        ).first()

        if not result or not result.template_structure:
            raise TemplateWeightsNotFoundError(
                template_id=template_id,
                reason="Template not found or template_structure is null",
            )

        structure = result.template_structure
        if isinstance(structure, str):
            structure = json.loads(structure)

        enabled_sections = self._extract_enabled_sections_from_structure(structure)

        # Try scoring_configuration.section_weights
        scoring_config = structure.get("scoring_configuration", {})
        section_weights = scoring_config.get("section_weights")

        if section_weights and isinstance(section_weights, dict):
            normalized_weights: Dict[str, int] = {}
            for section_name, weight in section_weights.items():
                normalized_name = self._normalize_section_name(str(section_name))
                if enabled_sections and normalized_name not in enabled_sections:
                    continue
                normalized_weights[normalized_name] = int(weight)

            if not normalized_weights:
                raise TemplateWeightsNotFoundError(
                    template_id=template_id,
                    reason="No enabled section_weights in scoring_configuration",
                )

            logger.info(
                "Template section weights resolved",
                extra={
                    "template_id": template_id,
                    "sections": list(normalized_weights.keys()),
                },
            )
            return normalized_weights

        # Fallback: derive sections from template_structure sections
        sections = structure.get("sections", [])
        if sections:
            logger.warning(
                "No section_weights in scoring_configuration — using equal weights",
                extra={
                    "template_id": template_id,
                    "sections_count": len(sections),
                    "scoring_configuration_present": isinstance(scoring_config, dict),
                },
            )

            derived_weights: Dict[str, int] = {}
            if isinstance(sections, dict):
                for key, section in sections.items():
                    if isinstance(section, dict) and section.get("enabled", True) is False:
                        continue
                    normalized = self._normalize_section_name(str(key))
                    if enabled_sections and normalized not in enabled_sections:
                        continue
                    section_weight = section.get("weight", 1) if isinstance(section, dict) else 1
                    if normalized not in derived_weights:
                        derived_weights[normalized] = int(section_weight)
            else:
                for i, section in enumerate(sections):
                    section_name: Optional[str] = None
                    if isinstance(section, dict):
                        if section.get("enabled", True) is False:
                            continue
                        section_name = (
                            section.get("section_key")
                            or section.get("section_name")
                            or section.get("name")
                            or section.get("id")
                        )
                        section_weight = int(section.get("weight", 1))
                    elif isinstance(section, str):
                        section_name = section.strip()
                        section_weight = 1
                    else:
                        section_name = None
                        section_weight = 1

                    if not section_name:
                        section_name = f"section_{i}"

                    normalized = self._normalize_section_name(section_name)
                    if enabled_sections and normalized not in enabled_sections:
                        continue

                    if normalized not in derived_weights:
                        derived_weights[normalized] = section_weight

            if derived_weights:
                # Self-heal: persist derived equal weights so this warning doesn't repeat
                try:
                    structure.setdefault("scoring_configuration", {})
                    structure["scoring_configuration"]["section_weights"] = derived_weights
                    self._db.execute(
                        text(
                            "UPDATE interview_templates "
                            "SET template_structure = CAST(:template_structure AS jsonb), "
                            "    updated_at = now() "
                            "WHERE id = :template_id"
                        ),
                        {
                            "template_id": template_id,
                            "template_structure": json.dumps(structure),
                        },
                    )
                    self._db.flush()
                    logger.info(
                        "Persisted derived section_weights into template_structure",
                        extra={
                            "template_id": template_id,
                            "derived_sections": list(derived_weights.keys()),
                        },
                    )
                except Exception as persist_error:
                    logger.warning(
                        "Failed to persist derived section_weights; continuing with in-memory weights",
                        extra={
                            "template_id": template_id,
                            "error": str(persist_error),
                        },
                    )
                return derived_weights

        if enabled_sections:
            logger.warning(
                "No section_weights found; deriving equal weights from enabled sections",
                extra={
                    "template_id": template_id,
                    "enabled_sections": sorted(enabled_sections),
                },
            )
            return {section_name: 1 for section_name in sorted(enabled_sections)}

        logger.error(
            "Unable to resolve section weights from template_structure",
            extra={
                "template_id": template_id,
                "template_structure_keys": list(structure.keys()) if isinstance(structure, dict) else None,
            },
        )

        raise TemplateWeightsNotFoundError(
            template_id=template_id,
            reason="No sections or section_weights in template_structure",
        )

    def _fetch_proctoring_risk(
        self, submission_id: int
    ) -> Optional[ProctoringRiskDTO]:
        """
        Fetch aggregated proctoring risk for an interview.

        Returns None if proctoring is disabled, no events exist,
        or the proctoring_events table is not available.
        """
        if not self._config.enable_proctoring_influence:
            return None

        try:
            rows = self._db.execute(
                text(
                    "SELECT severity, event_type "
                    "FROM proctoring_events "
                    "WHERE interview_submission_id = :sid"
                ),
                {"sid": submission_id},
            ).fetchall()
        except Exception:
            # Table may not exist yet (proctoring module not deployed)
            logger.debug(
                "Could not query proctoring_events — skipping proctoring adjustment",
                extra={"submission_id": submission_id},
            )
            return None

        if not rows:
            return None

        total_events = len(rows)
        high_count = sum(
            1 for r in rows if r.severity in ("high", "critical")
        )
        flagged_behaviors = list({r.event_type for r in rows})

        # Determine overall risk
        if any(r.severity == "critical" for r in rows):
            overall_risk = "critical"
        elif high_count > 0:
            overall_risk = "high"
        elif any(r.severity == "medium" for r in rows):
            overall_risk = "medium"
        else:
            overall_risk = "low"

        return ProctoringRiskDTO(
            overall_risk=overall_risk,
            total_events=total_events,
            high_severity_count=high_count,
            flagged_behaviors=flagged_behaviors,
        )

    def _build_rubric_snapshot(self, template_id: int) -> Dict[str, Any]:
        """
        Build minimal rubric snapshot for audit trail.

        Captures rubric ID, name, and dimension weights/max_scores.
        """
        rows = self._db.execute(
            text(
                "SELECT r.id AS rubric_id, r.name AS rubric_name, "
                "       rd.id AS dimension_id, rd.dimension_name, "
                "       rd.weight, rd.max_score "
                "FROM interview_template_rubrics itr "
                "JOIN rubrics r ON r.id = itr.rubric_id "
                "JOIN rubric_dimensions rd ON rd.rubric_id = r.id "
                "WHERE itr.interview_template_id = :tid "
                "ORDER BY r.id, rd.sequence_order"
            ),
            {"tid": template_id},
        ).fetchall()

        if not rows:
            return {}

        rubrics: Dict[int, Dict] = {}
        for row in rows:
            rid = row.rubric_id
            if rid not in rubrics:
                rubrics[rid] = {
                    "rubric_id": rid,
                    "rubric_name": row.rubric_name,
                    "dimensions": [],
                }
            rubrics[rid]["dimensions"].append(
                {
                    "dimension_id": row.dimension_id,
                    "name": row.dimension_name,
                    "weight": float(row.weight),
                    "max_score": float(row.max_score),
                }
            )

        # Return single rubric or list if multiple
        rubric_list = list(rubrics.values())
        if len(rubric_list) == 1:
            return rubric_list[0]
        return {"rubrics": rubric_list}

    # ── Internal: Validation ───────────────────────────────────────────

    def _check_existing_result(
        self,
        submission_id: int,
        force_reaggregate: bool,
    ) -> Optional[InterviewResult]:
        """Check for existing current result and return it when re-aggregation is allowed."""
        existing = (
            self._db.query(InterviewResult)
            .filter(
                and_(
                    InterviewResult.interview_submission_id == submission_id,
                    InterviewResult.is_current == True,  # noqa: E712
                )
            )
            .first()
        )

        if existing:
            if force_reaggregate:
                logger.info(
                    "Existing current result will be replaced after successful aggregation",
                    extra={
                        "existing_result_id": existing.id,
                        "submission_id": submission_id,
                    },
                )
                return existing
            else:
                raise AggregationAlreadyExistsError(
                    submission_id=submission_id,
                    existing_result_id=existing.id,
                )

        return None

    def _verify_completeness(
        self,
        submission_id: int,
        exchanges: List[ExchangeSummaryDTO],
        evaluations: List[EvaluationSummaryDTO],
    ) -> None:
        """Verify all exchanges have final evaluations."""
        evaluated_exchange_ids = {ev.interview_exchange_id for ev in evaluations}
        all_exchange_ids = {ex.exchange_id for ex in exchanges}

        pending = all_exchange_ids - evaluated_exchange_ids
        if pending:
            raise IncompleteEvaluationError(
                pending_exchange_ids=sorted(pending),
                submission_id=submission_id,
            )

    # ── Internal: Persistence ──────────────────────────────────────────

    def _persist_result(
        self,
        data: InterviewResultData,
        proctoring_risk: Optional[ProctoringRiskDTO],
        replace_existing_result_id: Optional[int] = None,
    ) -> InterviewResult:
        """Persist interview result and optional proctoring report."""
        # Serialize section_scores for JSONB storage as per-section averages (0-100)
        # so API/UI don't surface accumulated totals that can exceed 100 when a
        # section has multiple exchanges.
        section_scores_json: Dict[str, float] = {}
        for section in data.section_scores:
            if section.exchanges_evaluated > 0:
                avg_score = section.score / Decimal(section.exchanges_evaluated)
            else:
                avg_score = Decimal("0")
            section_scores_json[section.section_name] = float(
                max(Decimal("0"), min(Decimal("100"), avg_score)).quantize(Decimal("0.01"))
            )

        # strengths / weaknesses stored as text (JSON-encoded list) per actual schema
        strengths_text = json.dumps(data.strengths) if data.strengths else None
        weaknesses_text = json.dumps(data.weaknesses) if data.weaknesses else None

        if replace_existing_result_id is not None:
            existing = self._db.get(InterviewResult, replace_existing_result_id)
            if existing is not None and existing.is_current:
                existing.is_current = False
                self._db.flush()

        def build_result(scoring_version: str) -> InterviewResult:
            return InterviewResult(
                interview_submission_id=data.interview_submission_id,
                final_score=data.final_score,
                normalized_score=data.normalized_score,
                result_status=data.result_status,
                recommendation=data.recommendation,
                scoring_version=scoring_version,
                rubric_snapshot=data.rubric_snapshot,
                template_weight_snapshot=data.template_weight_snapshot,
                section_scores=section_scores_json,
                strengths=strengths_text,
                weaknesses=weaknesses_text,
                summary_notes=data.summary_notes or None,
                generated_by=data.generated_by,
                model_id=data.model_id,
                is_current=True,
                computed_at=datetime.now(timezone.utc),
            )

        result = build_result(data.scoring_version)
        self._db.add(result)

        try:
            self._db.flush()
        except IntegrityError as e:
            self._db.rollback()
            err_text = str(e).lower()
            is_duplicate_scoring_version = (
                "interview_results_interview_submission_id_scoring_version_key" in err_text
                or "duplicate key value violates unique constraint" in err_text
            )

            if not is_duplicate_scoring_version:
                raise AggregationError(
                    message=f"Failed to persist interview result: {e}",
                    error_code="RESULT_PERSIST_ERROR",
                ) from e

            fallback_version = f"{data.scoring_version}-fallback-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            logger.warning(
                "Duplicate scoring_version detected, retrying with fallback version",
                extra={
                    "submission_id": data.interview_submission_id,
                    "old_scoring_version": data.scoring_version,
                    "new_scoring_version": fallback_version,
                },
            )

            data.scoring_version = fallback_version

            if replace_existing_result_id is not None:
                existing = self._db.get(InterviewResult, replace_existing_result_id)
                if existing is not None and existing.is_current:
                    existing.is_current = False
                    self._db.flush()

            result = build_result(data.scoring_version)
            self._db.add(result)

            try:
                self._db.flush()
            except IntegrityError as e2:
                self._db.rollback()
                raise AggregationError(
                    message=f"Failed to persist interview result after scoring_version fallback: {e2}",
                    error_code="RESULT_PERSIST_ERROR",
                ) from e2

        # Optional: Persist proctoring supplementary report
        if proctoring_risk and proctoring_risk.overall_risk in ("high", "critical"):
            self._persist_proctoring_report(data, proctoring_risk)

        self._db.commit()
        self._db.refresh(result)

        logger.info(
            "Interview result persisted",
            extra={
                "result_id": result.id,
                "submission_id": data.interview_submission_id,
            },
        )

        return result

    def _persist_proctoring_report(
        self,
        data: InterviewResultData,
        proctoring_risk: ProctoringRiskDTO,
    ) -> None:
        """Persist proctoring risk supplementary report."""
        report_content = {
            "overall_risk": proctoring_risk.overall_risk,
            "total_events": proctoring_risk.total_events,
            "high_severity_count": proctoring_risk.high_severity_count,
            "flagged_behaviors": proctoring_risk.flagged_behaviors,
            "recommendation_impact": (
                f"Recommendation may have been adjusted due to "
                f"{proctoring_risk.overall_risk} proctoring risk"
            ),
        }

        report = SupplementaryReport(
            interview_submission_id=data.interview_submission_id,
            report_type="proctoring_risk",
            content=report_content,
            generated_by=data.generated_by,
            model_id=None,
        )

        self._db.add(report)

    # ── Internal: Mapping ──────────────────────────────────────────────

    def _row_to_result_data(self, row: InterviewResult) -> InterviewResultData:
        """Convert ORM row to InterviewResultData DTO."""
        # Parse stored section_scores JSONB back to SectionScore list
        section_scores_raw = row.section_scores or {}
        template_weights = row.template_weight_snapshot or {}
        section_scores = [
            SectionScore(
                section_name=name,
                score=Decimal(str(score)),
                weight=template_weights.get(name, {}).get("weight", 1),
                exchanges_evaluated=0,  # Not stored; 0 as placeholder
            )
            for name, score in section_scores_raw.items()
        ]

        # Parse strengths / weaknesses from text (JSON-encoded lists)
        strengths = json.loads(row.strengths) if row.strengths else []
        weaknesses = json.loads(row.weaknesses) if row.weaknesses else []

        return InterviewResultData(
            interview_submission_id=row.interview_submission_id,
            final_score=Decimal(str(row.final_score)) if row.final_score else Decimal("0"),
            normalized_score=Decimal(str(row.normalized_score)) if row.normalized_score else Decimal("0"),
            result_status=row.result_status or "completed",
            recommendation=row.recommendation or "no_hire",
            section_scores=section_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            summary_notes=row.summary_notes or "",
            rubric_snapshot=row.rubric_snapshot or {},
            template_weight_snapshot=template_weights,
            scoring_version=row.scoring_version or "",
            generated_by=row.generated_by or "unknown",
            model_id=row.model_id,
        )


# -----------------------------------------------------------------------------
# Convenience Function
# -----------------------------------------------------------------------------


async def aggregate_interview_result(
    db: Session,
    submission_id: int,
    generated_by: str = "ai",
    force_reaggregate: bool = False,
    llm_provider: Optional["BaseLLMProvider"] = None,
) -> InterviewResultData:
    """
    Aggregate an interview result.

    Convenience function wrapping AggregationService.

    Args:
        db: Database session.
        submission_id: Interview submission to aggregate.
        generated_by: Who triggered aggregation.
        force_reaggregate: Create new version if result exists.
        llm_provider: LLM provider for summary generation.

    Returns:
        InterviewResultData with all computed fields.
    """
    service = AggregationService(db=db, llm_provider=llm_provider)
    return await service.aggregate_interview_result(
        submission_id=submission_id,
        generated_by=generated_by,
        force_reaggregate=force_reaggregate,
    )
