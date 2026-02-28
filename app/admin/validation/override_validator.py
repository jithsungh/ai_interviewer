"""
Override Validator

Validates tenant override payloads:
  • Override fields do not include immutable fields (id, org_id, scope, …)
  • Base content is owned by super org (org_id=1)
  • Override fields are a valid subset of the content's field set
  • No structural integrity violations

Pure domain logic — repository protocol for lookup is accepted as an arg.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.admin.domain.entities import (
    IMMUTABLE_OVERRIDE_FIELDS,
    SUPER_ORG_ID,
    ContentType,
)

from .result import ValidationErrorDetail, ValidationResult


# --------------------------------------------------------------------------
# Known mutable fields per content type
# --------------------------------------------------------------------------

# These are the fields that CAN be overridden per content type.
# Derived from entity dataclass fields minus immutable fields.

_TEMPLATE_MUTABLE_FIELDS: Set[str] = {
    "name", "description", "template_structure", "rules",
    "total_estimated_time_minutes", "is_active",
}

_RUBRIC_MUTABLE_FIELDS: Set[str] = {
    "name", "description", "schema", "is_active",
}

_ROLE_MUTABLE_FIELDS: Set[str] = {
    "name", "description",
}

_TOPIC_MUTABLE_FIELDS: Set[str] = {
    "name", "description", "parent_topic_id", "estimated_time_minutes",
}

_QUESTION_MUTABLE_FIELDS: Set[str] = {
    "question_text", "answer_text", "question_type", "difficulty",
    "source_type", "estimated_time_minutes", "is_active",
}

_CODING_PROBLEM_MUTABLE_FIELDS: Set[str] = {
    "title", "body", "difficulty", "description", "constraints",
    "estimated_time_minutes", "is_active", "examples",
    "constraints_structured", "hints", "code_snippets",
}

_MUTABLE_FIELDS_BY_TYPE: Dict[str, Set[str]] = {
    ContentType.TEMPLATE.value: _TEMPLATE_MUTABLE_FIELDS,
    ContentType.RUBRIC.value: _RUBRIC_MUTABLE_FIELDS,
    ContentType.ROLE.value: _ROLE_MUTABLE_FIELDS,
    ContentType.TOPIC.value: _TOPIC_MUTABLE_FIELDS,
    ContentType.QUESTION.value: _QUESTION_MUTABLE_FIELDS,
    ContentType.CODING_PROBLEM.value: _CODING_PROBLEM_MUTABLE_FIELDS,
}


class OverrideValidator:
    """
    Stateless validator for tenant override payloads.

    All methods are static — no internal state.
    """

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    @staticmethod
    def validate_fields(
        override_fields: Dict[str, Any],
        content_type: str | ContentType,
    ) -> ValidationResult:
        """
        Validate override fields against content type schema.

        Checks:
          1. override_fields is non-empty.
          2. No immutable fields are present.
          3. All fields are recognised for the content type.

        Args:
            override_fields: Sparse dict of fields to override.
            content_type: ContentType value or its string equivalent.
        """
        ct_value = content_type.value if isinstance(content_type, ContentType) else content_type

        results: List[ValidationResult] = [
            OverrideValidator._validate_non_empty(override_fields),
            OverrideValidator._validate_no_immutable_fields(override_fields),
            OverrideValidator._validate_known_fields(override_fields, ct_value),
        ]
        return ValidationResult.merge_all(*results)

    @staticmethod
    def validate_base_content_ownership(
        base_content_org_id: Optional[int],
    ) -> ValidationResult:
        """
        Ensure base content is owned by the super org.

        Per REQUIREMENTS.md:
          "Base content must exist and be owned by super org (org_id=1)"

        Args:
            base_content_org_id: organization_id of the base content entity.
        """
        if base_content_org_id is None:
            # Global content (org_id=NULL) — also managed by super org
            return ValidationResult.success()

        if base_content_org_id != SUPER_ORG_ID:
            return ValidationResult.from_single(
                field="base_content_id",
                message=f"Base content must be owned by super org (org_id={SUPER_ORG_ID}), "
                        f"but found org_id={base_content_org_id}",
                code="INVALID_BASE_CONTENT",
            )
        return ValidationResult.success()

    @staticmethod
    def validate_full(
        override_fields: Dict[str, Any],
        content_type: str | ContentType,
        base_content_org_id: Optional[int],
    ) -> ValidationResult:
        """
        Full override validation combining field checks and base ownership.

        Convenience method that merges validate_fields + validate_base_content_ownership.
        """
        return ValidationResult.merge_all(
            OverrideValidator.validate_fields(override_fields, content_type),
            OverrideValidator.validate_base_content_ownership(base_content_org_id),
        )

    # ------------------------------------------------------------------
    # Internal rules
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_non_empty(override_fields: Dict[str, Any]) -> ValidationResult:
        """Override must contain at least one field."""
        if not override_fields:
            return ValidationResult.from_single(
                field="override_fields",
                message="Override must contain at least one field to override",
                code="EMPTY_OVERRIDE",
            )
        return ValidationResult.success()

    @staticmethod
    def _validate_no_immutable_fields(
        override_fields: Dict[str, Any],
    ) -> ValidationResult:
        """Reject immutable fields in override payload."""
        forbidden = set(override_fields.keys()) & IMMUTABLE_OVERRIDE_FIELDS
        if forbidden:
            errors = [
                ValidationErrorDetail(
                    field=f"override_fields.{f}",
                    message=f"Cannot override immutable field '{f}'",
                    code="IMMUTABLE_FIELD_OVERRIDE",
                )
                for f in sorted(forbidden)
            ]
            return ValidationResult.failure(errors)
        return ValidationResult.success()

    @staticmethod
    def _validate_known_fields(
        override_fields: Dict[str, Any],
        content_type_value: str,
    ) -> ValidationResult:
        """Ensure all override fields are valid for the content type."""
        known = _MUTABLE_FIELDS_BY_TYPE.get(content_type_value)
        if known is None:
            return ValidationResult.from_single(
                field="content_type",
                message=f"Unknown content type '{content_type_value}'",
                code="UNKNOWN_CONTENT_TYPE",
            )

        unknown = set(override_fields.keys()) - known - IMMUTABLE_OVERRIDE_FIELDS
        if unknown:
            errors = [
                ValidationErrorDetail(
                    field=f"override_fields.{f}",
                    message=f"Field '{f}' is not a valid override field for {content_type_value}",
                    code="UNKNOWN_OVERRIDE_FIELD",
                )
                for f in sorted(unknown)
            ]
            return ValidationResult.failure(errors)
        return ValidationResult.success()
