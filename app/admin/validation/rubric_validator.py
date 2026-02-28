"""
Rubric Validator

Validates rubric dimension consistency:
  • Dimension weights sum to 1.0 (±tolerance)
  • Sequence orders are unique
  • Each dimension has required fields populated
  • Criteria schema is valid (if present)

Pure domain logic — no DB calls, no FastAPI imports.
Reuses RUBRIC_WEIGHT_TOLERANCE constant from admin/domain/entities.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app.admin.domain.entities import RUBRIC_WEIGHT_TOLERANCE, RubricDimension

from .result import ValidationErrorDetail, ValidationResult


class RubricValidator:
    """
    Stateless validator for rubric dimension consistency.

    Designed for pre-save feedback — collects all errors.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @staticmethod
    def validate_dimensions(dimensions: List[RubricDimension]) -> ValidationResult:
        """
        Validate a list of rubric dimensions.

        Checks:
          1. At least one dimension is present.
          2. All weights are positive.
          3. Weights sum to 1.0 (±tolerance).
          4. Sequence orders are unique.
          5. Each dimension_name is non-empty.
          6. max_score is positive.
        """
        if not dimensions:
            return ValidationResult.from_single(
                field="dimensions",
                message="Rubric must have at least one dimension",
                code="EMPTY_DIMENSIONS",
            )

        results: List[ValidationResult] = [
            RubricValidator._validate_weight_sum(dimensions),
            RubricValidator._validate_unique_sequence_order(dimensions),
            RubricValidator._validate_individual_dimensions(dimensions),
        ]
        return ValidationResult.merge_all(*results)

    @staticmethod
    def validate_dimension_weights_from_dicts(
        dimension_dicts: List[Dict[str, Any]],
    ) -> ValidationResult:
        """
        Validate dimension weights from raw dicts (pre-entity construction).

        Useful when validating incoming API payloads before building
        RubricDimension entities.
        """
        if not dimension_dicts:
            return ValidationResult.from_single(
                field="dimensions",
                message="Rubric must have at least one dimension",
                code="EMPTY_DIMENSIONS",
            )

        errors: List[ValidationErrorDetail] = []
        total_weight = Decimal("0")

        for idx, d in enumerate(dimension_dicts):
            raw_weight = d.get("weight")
            if raw_weight is None:
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].weight",
                    message="weight is required",
                    code="MISSING_WEIGHT",
                ))
                continue
            try:
                w = Decimal(str(raw_weight))
            except (InvalidOperation, ValueError, TypeError):
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].weight",
                    message=f"Invalid weight value: {raw_weight}",
                    code="INVALID_WEIGHT",
                ))
                continue

            if w <= 0:
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].weight",
                    message="Weight must be positive",
                    code="NON_POSITIVE_WEIGHT",
                ))
            total_weight += w

        # Weight sum check
        if not errors:
            if abs(total_weight - Decimal("1.0")) > Decimal(str(RUBRIC_WEIGHT_TOLERANCE)):
                errors.append(ValidationErrorDetail(
                    field="dimensions.weight",
                    message=f"Dimension weights must sum to 1.0 (got {total_weight})",
                    code="WEIGHT_SUM_MISMATCH",
                ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    # ------------------------------------------------------------------
    # Internal rules
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_weight_sum(dimensions: List[RubricDimension]) -> ValidationResult:
        """Weights must sum to 1.0 ± tolerance."""
        total = sum(d.weight for d in dimensions)
        # Ensure comparison uses Decimal
        tolerance = Decimal(str(RUBRIC_WEIGHT_TOLERANCE))
        if abs(total - Decimal("1.0")) > tolerance:
            return ValidationResult.from_single(
                field="dimensions.weight",
                message=f"Dimension weights must sum to 1.0 (got {total})",
                code="WEIGHT_SUM_MISMATCH",
            )
        return ValidationResult.success()

    @staticmethod
    def _validate_unique_sequence_order(
        dimensions: List[RubricDimension],
    ) -> ValidationResult:
        """Sequence orders must be unique within the rubric."""
        orders = [d.sequence_order for d in dimensions]
        seen: set = set()
        duplicates: List[int] = []
        for o in orders:
            if o in seen:
                duplicates.append(o)
            seen.add(o)

        if duplicates:
            return ValidationResult.from_single(
                field="dimensions.sequence_order",
                message=f"Duplicate sequence_order values: {sorted(set(duplicates))}",
                code="DUPLICATE_SEQUENCE_ORDER",
            )
        return ValidationResult.success()

    @staticmethod
    def _validate_individual_dimensions(
        dimensions: List[RubricDimension],
    ) -> ValidationResult:
        """Per-dimension field validation."""
        errors: List[ValidationErrorDetail] = []

        for idx, d in enumerate(dimensions):
            # dimension_name must be non-empty
            if not d.dimension_name or not d.dimension_name.strip():
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].dimension_name",
                    message="Dimension name must be non-empty",
                    code="EMPTY_DIMENSION_NAME",
                ))

            # max_score must be positive
            if d.max_score is not None and d.max_score <= 0:
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].max_score",
                    message=f"max_score must be positive (got {d.max_score})",
                    code="NON_POSITIVE_MAX_SCORE",
                ))

            # weight must be positive
            if d.weight is not None and d.weight <= 0:
                errors.append(ValidationErrorDetail(
                    field=f"dimensions[{idx}].weight",
                    message=f"Weight must be positive (got {d.weight})",
                    code="NON_POSITIVE_WEIGHT",
                ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    @staticmethod
    def validate_criteria_schema(criteria: Optional[Dict[str, Any]]) -> ValidationResult:
        """
        Validate a dimension's criteria JSONB.

        Criteria is optional. If present, must be a dict.
        """
        if criteria is None:
            return ValidationResult.success()

        if not isinstance(criteria, dict):
            return ValidationResult.from_single(
                field="criteria",
                message="Criteria must be a JSON object",
                code="INVALID_CRITERIA_TYPE",
            )
        return ValidationResult.success()
