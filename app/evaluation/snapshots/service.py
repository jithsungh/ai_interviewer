"""
Evaluation Snapshots — Service

Functions for creating, retrieving, validating, and comparing audit-safe
snapshots of rubric and template configuration at evaluation time.

Design:
    - Pure functions (no class state) — stateless snapshot operations
    - Database reads via raw SQL (no cross-module model imports)
    - Returns Pydantic schema instances or serialized dicts for JSONB storage
    - Validation at both creation and retrieval time
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.evaluation.snapshots.errors import (
    SnapshotError,
    SnapshotNotFoundError,
    SnapshotValidationError,
)
from app.evaluation.snapshots.schemas import (
    DimensionSnapshot,
    RubricSnapshot,
    TemplateWeightSnapshot,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def create_rubric_snapshot(
    db: Session,
    rubric_id: int,
) -> Dict[str, Any]:
    """
    Create a rubric snapshot by reading the current rubric and its dimensions.

    Args:
        db: Database session.
        rubric_id: ID of the rubric to snapshot.

    Returns:
        Serialized dict suitable for JSONB storage.

    Raises:
        SnapshotError: Rubric or dimensions not found.
    """
    # Fetch rubric metadata
    rubric_row = db.execute(
        text("SELECT id, name, description FROM rubrics WHERE id = :rid"),
        {"rid": rubric_id},
    ).first()

    if not rubric_row:
        raise SnapshotError(
            message=f"Rubric {rubric_id} not found for snapshot",
            error_code="RUBRIC_NOT_FOUND",
        )

    # Fetch dimensions
    dim_rows = db.execute(
        text(
            "SELECT id, dimension_name, weight, max_score, "
            "       criteria, sequence_order "
            "FROM rubric_dimensions "
            "WHERE rubric_id = :rid "
            "ORDER BY sequence_order"
        ),
        {"rid": rubric_id},
    ).fetchall()

    if not dim_rows:
        raise SnapshotError(
            message=f"Rubric {rubric_id} has no dimensions",
            error_code="NO_DIMENSIONS",
        )

    now = datetime.now(timezone.utc)

    snapshot = RubricSnapshot(
        rubric_id=rubric_row.id,
        rubric_name=rubric_row.name,
        rubric_description=rubric_row.description,
        dimensions=[
            DimensionSnapshot(
                dimension_id=d.id,
                dimension_name=d.dimension_name,
                weight=float(d.weight) if d.weight else 0,
                max_score=float(d.max_score) if d.max_score else 0,
                description=_extract_criteria_description(d.criteria),
                scoring_criteria=_extract_criteria_text(d.criteria),
            )
            for d in dim_rows
        ],
        snapshot_timestamp=now,
    )

    logger.info(
        "Rubric snapshot created",
        extra={
            "rubric_id": rubric_id,
            "dimension_count": len(dim_rows),
        },
    )

    return snapshot.model_dump(mode="json")


def create_template_weight_snapshot(
    db: Session,
    template_id: int,
    section_weights: Dict[str, int],
) -> Dict[str, Any]:
    """
    Create a template weight snapshot.

    Args:
        db: Database session.
        template_id: ID of the interview template.
        section_weights: Pre-resolved section → weight mapping.

    Returns:
        Serialized dict suitable for JSONB storage.

    Raises:
        SnapshotError: Template not found.
    """
    # Fetch template name
    template_row = db.execute(
        text("SELECT id, name FROM interview_templates WHERE id = :tid"),
        {"tid": template_id},
    ).first()

    if not template_row:
        raise SnapshotError(
            message=f"Template {template_id} not found for snapshot",
            error_code="TEMPLATE_NOT_FOUND",
        )

    now = datetime.now(timezone.utc)

    snapshot = TemplateWeightSnapshot(
        template_id=template_row.id,
        template_name=template_row.name,
        section_weights=section_weights,
        snapshot_timestamp=now,
    )

    logger.info(
        "Template weight snapshot created",
        extra={
            "template_id": template_id,
            "sections": list(section_weights.keys()),
        },
    )

    return snapshot.model_dump(mode="json")


def create_rubric_snapshot_for_template(
    db: Session,
    template_id: int,
) -> Dict[str, Any]:
    """
    Create a rubric snapshot from template → rubric linkage.

    Reads ``interview_template_rubrics`` to find associated rubrics,
    then creates a snapshot covering all rubrics and their dimensions.

    Args:
        db: Database session.
        template_id: Interview template ID.

    Returns:
        Serialized dict — either a single RubricSnapshot or a dict
        with a ``rubrics`` key containing multiple snapshots.
    """
    rows = db.execute(
        text(
            "SELECT r.id AS rubric_id, r.name AS rubric_name, "
            "       r.description AS rubric_description, "
            "       rd.id AS dimension_id, rd.dimension_name, "
            "       rd.weight, rd.max_score, rd.criteria, rd.sequence_order "
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

    now = datetime.now(timezone.utc)

    # Group by rubric
    rubrics: Dict[int, Dict] = {}
    for row in rows:
        rid = row.rubric_id
        if rid not in rubrics:
            rubrics[rid] = {
                "rubric_id": rid,
                "rubric_name": row.rubric_name,
                "rubric_description": row.rubric_description,
                "dimensions": [],
                "snapshot_timestamp": now.isoformat(),
            }
        rubrics[rid]["dimensions"].append(
            {
                "dimension_id": row.dimension_id,
                "dimension_name": row.dimension_name,
                "weight": float(row.weight) if row.weight else 0,
                "max_score": float(row.max_score) if row.max_score else 0,
                "description": _extract_criteria_description(row.criteria),
                "scoring_criteria": _extract_criteria_text(row.criteria),
            }
        )

    rubric_list = list(rubrics.values())
    if len(rubric_list) == 1:
        return rubric_list[0]
    return {"rubrics": rubric_list}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve_rubric_snapshot(
    db: Session,
    result_id: int,
) -> RubricSnapshot:
    """
    Retrieve the rubric snapshot from an interview result.

    Args:
        db: Database session.
        result_id: Interview result ID.

    Returns:
        Parsed RubricSnapshot.

    Raises:
        SnapshotNotFoundError: Result or snapshot data missing.
        SnapshotValidationError: Snapshot data is malformed.
    """
    from app.evaluation.persistence.models import InterviewResultModel

    result = (
        db.query(InterviewResultModel)
        .filter(InterviewResultModel.id == result_id)
        .first()
    )

    if not result:
        raise SnapshotNotFoundError(
            result_id=result_id, snapshot_type="rubric"
        )

    if not result.rubric_snapshot:
        raise SnapshotNotFoundError(
            result_id=result_id, snapshot_type="rubric"
        )

    try:
        return RubricSnapshot.model_validate(result.rubric_snapshot)
    except Exception as exc:
        raise SnapshotValidationError(
            reason=str(exc), snapshot_type="rubric"
        ) from exc


def retrieve_template_weight_snapshot(
    db: Session,
    result_id: int,
) -> TemplateWeightSnapshot:
    """
    Retrieve the template weight snapshot from an interview result.

    Args:
        db: Database session.
        result_id: Interview result ID.

    Returns:
        Parsed TemplateWeightSnapshot.

    Raises:
        SnapshotNotFoundError: Result or snapshot data missing.
        SnapshotValidationError: Snapshot data is malformed.
    """
    from app.evaluation.persistence.models import InterviewResultModel

    result = (
        db.query(InterviewResultModel)
        .filter(InterviewResultModel.id == result_id)
        .first()
    )

    if not result:
        raise SnapshotNotFoundError(
            result_id=result_id, snapshot_type="template_weight"
        )

    if not result.template_weight_snapshot:
        raise SnapshotNotFoundError(
            result_id=result_id, snapshot_type="template_weight"
        )

    try:
        return TemplateWeightSnapshot.model_validate(
            result.template_weight_snapshot
        )
    except Exception as exc:
        raise SnapshotValidationError(
            reason=str(exc), snapshot_type="template_weight"
        ) from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_rubric_snapshot(snapshot: Dict[str, Any]) -> Optional[str]:
    """
    Validate rubric snapshot structure.

    Returns:
        None if valid, error message string if invalid.
    """
    if not snapshot:
        return "Snapshot is empty"

    # Handle multi-rubric container
    if "rubrics" in snapshot:
        for i, rubric in enumerate(snapshot["rubrics"]):
            error = _validate_single_rubric(rubric)
            if error:
                return f"rubrics[{i}]: {error}"
        return None

    return _validate_single_rubric(snapshot)


def validate_template_weight_snapshot(
    snapshot: Dict[str, Any],
) -> Optional[str]:
    """
    Validate template weight snapshot structure.

    Returns:
        None if valid, error message string if invalid.
    """
    if not snapshot:
        return "Snapshot is empty"

    if "template_id" not in snapshot or not snapshot["template_id"]:
        return "Missing or invalid template_id"

    weights = snapshot.get("section_weights")
    if not weights or not isinstance(weights, dict):
        return "Missing or empty section_weights"

    for section, weight in weights.items():
        if not isinstance(weight, (int, float)) or weight < 0:
            return f"Invalid weight for section '{section}': {weight}"

    if "snapshot_timestamp" not in snapshot:
        return "Missing snapshot_timestamp"

    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_rubric_snapshots(
    snapshot_a: Dict[str, Any],
    snapshot_b: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare two rubric snapshots and report differences.

    Useful for auditing whether rubric configuration changed between
    two evaluations/results.

    Returns:
        Dict with keys: ``identical`` (bool), ``differences`` (list of diffs).
    """
    if snapshot_a == snapshot_b:
        return {"identical": True, "differences": []}

    differences: List[Dict] = []

    # Compare top-level fields
    for field in ("rubric_id", "rubric_name", "rubric_description"):
        if snapshot_a.get(field) != snapshot_b.get(field):
            differences.append(
                {
                    "field": field,
                    "snapshot_a": snapshot_a.get(field),
                    "snapshot_b": snapshot_b.get(field),
                }
            )

    # Compare dimensions
    dims_a = {
        d["dimension_id"]: d
        for d in snapshot_a.get("dimensions", [])
    }
    dims_b = {
        d["dimension_id"]: d
        for d in snapshot_b.get("dimensions", [])
    }

    added = set(dims_b.keys()) - set(dims_a.keys())
    removed = set(dims_a.keys()) - set(dims_b.keys())
    common = set(dims_a.keys()) & set(dims_b.keys())

    if added:
        differences.append({"type": "dimensions_added", "ids": sorted(added)})
    if removed:
        differences.append(
            {"type": "dimensions_removed", "ids": sorted(removed)}
        )

    for dim_id in sorted(common):
        da, db = dims_a[dim_id], dims_b[dim_id]
        for field in ("weight", "max_score", "dimension_name"):
            if da.get(field) != db.get(field):
                differences.append(
                    {
                        "type": "dimension_changed",
                        "dimension_id": dim_id,
                        "field": field,
                        "snapshot_a": da.get(field),
                        "snapshot_b": db.get(field),
                    }
                )

    return {"identical": False, "differences": differences}


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _validate_single_rubric(rubric: Dict[str, Any]) -> Optional[str]:
    """Validate a single rubric snapshot dict."""
    if "rubric_id" not in rubric or not rubric["rubric_id"]:
        return "Missing or invalid rubric_id"

    dims = rubric.get("dimensions")
    if not dims or not isinstance(dims, list) or len(dims) == 0:
        return "Missing or empty dimensions"

    required_fields = ("dimension_id", "dimension_name", "weight", "max_score")
    for i, dim in enumerate(dims):
        for field in required_fields:
            if field not in dim:
                return f"dimensions[{i}] missing field: {field}"

    if "snapshot_timestamp" not in rubric:
        return "Missing snapshot_timestamp"

    return None


def _extract_criteria_description(criteria: Any) -> Optional[str]:
    """Extract a text description from rubric_dimensions.criteria JSONB."""
    if criteria is None:
        return None
    if isinstance(criteria, str):
        return criteria
    if isinstance(criteria, dict):
        return criteria.get("description")
    return None


def _extract_criteria_text(criteria: Any) -> Optional[str]:
    """Extract scoring criteria text from rubric_dimensions.criteria JSONB."""
    if criteria is None:
        return None
    if isinstance(criteria, str):
        return criteria
    if isinstance(criteria, dict):
        return criteria.get("scoring_criteria") or criteria.get("criteria")
    return None
