"""
Evaluation Snapshots — Public API

Exports schemas, service functions, and errors for audit-safe context freezing.
"""

from app.evaluation.snapshots.errors import (
    SnapshotError,
    SnapshotNotFoundError,
    SnapshotValidationError,
)
from app.evaluation.snapshots.schemas import (
    DimensionSnapshot,
    MultiRubricSnapshot,
    RubricSnapshot,
    TemplateWeightSnapshot,
)
from app.evaluation.snapshots.service import (
    compare_rubric_snapshots,
    create_rubric_snapshot,
    create_rubric_snapshot_for_template,
    create_template_weight_snapshot,
    retrieve_rubric_snapshot,
    retrieve_template_weight_snapshot,
    validate_rubric_snapshot,
    validate_template_weight_snapshot,
)

__all__ = [
    # Schemas
    "DimensionSnapshot",
    "RubricSnapshot",
    "TemplateWeightSnapshot",
    "MultiRubricSnapshot",
    # Service functions
    "create_rubric_snapshot",
    "create_template_weight_snapshot",
    "create_rubric_snapshot_for_template",
    "retrieve_rubric_snapshot",
    "retrieve_template_weight_snapshot",
    "validate_rubric_snapshot",
    "validate_template_weight_snapshot",
    "compare_rubric_snapshots",
    # Errors
    "SnapshotError",
    "SnapshotNotFoundError",
    "SnapshotValidationError",
]
