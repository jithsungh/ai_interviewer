"""
Cross-Reference Validator

Validates that references between entities actually exist:
  • Template → rubric IDs exist
  • Template → role IDs exist
  • Topic → parent_topic_id exists and has no cycle
  • Window → role + template mappings exist
  • Question → topic references exist

Requires repository access (via protocol interfaces) for DB lookups.
Only read-only operations — no mutations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.admin.domain.entities import Template, Window, WindowRoleTemplate
from app.admin.domain.protocols import (
    RoleRepository,
    RubricRepository,
    TemplateRepository,
    TopicRepository,
)

from .result import ValidationErrorDetail, ValidationResult


class CrossReferenceValidator:
    """
    Validates cross-entity references via repository lookups.

    Accepts repository protocols as constructor args (dependency injection).
    All operations are read-only.
    """

    def __init__(
        self,
        *,
        template_repo: Optional[TemplateRepository] = None,
        rubric_repo: Optional[RubricRepository] = None,
        role_repo: Optional[RoleRepository] = None,
        topic_repo: Optional[TopicRepository] = None,
    ) -> None:
        self._templates = template_repo
        self._rubrics = rubric_repo
        self._roles = role_repo
        self._topics = topic_repo

    # ------------------------------------------------------------------
    # Template cross-references
    # ------------------------------------------------------------------

    def validate_template_role_refs(
        self,
        role_ids: List[int],
    ) -> ValidationResult:
        """
        Validate all role IDs referenced by a template exist.

        Args:
            role_ids: Role IDs from template-role mapping.
        """
        if self._roles is None:
            return ValidationResult.success()

        errors: List[ValidationErrorDetail] = []
        for rid in role_ids:
            role = self._roles.get_by_id(rid)
            if role is None:
                errors.append(ValidationErrorDetail(
                    field=f"role_ids",
                    message=f"Referenced role ID {rid} not found",
                    code="INVALID_REFERENCE",
                ))
        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    def validate_template_rubric_refs(
        self,
        rubric_ids: List[int],
    ) -> ValidationResult:
        """
        Validate all rubric IDs referenced by a template exist and are active.

        Args:
            rubric_ids: Rubric IDs from template-rubric mapping.
        """
        if self._rubrics is None:
            return ValidationResult.success()

        errors: List[ValidationErrorDetail] = []
        for rid in rubric_ids:
            rubric = self._rubrics.get_by_id(rid)
            if rubric is None:
                errors.append(ValidationErrorDetail(
                    field=f"rubric_ids",
                    message=f"Referenced rubric ID {rid} not found",
                    code="INVALID_REFERENCE",
                ))
            elif not rubric.is_active:
                errors.append(ValidationErrorDetail(
                    field=f"rubric_ids",
                    message=f"Referenced rubric ID {rid} is inactive",
                    code="INACTIVE_REFERENCE",
                ))
        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    # ------------------------------------------------------------------
    # Window cross-references
    # ------------------------------------------------------------------

    def validate_window_mappings(
        self,
        mappings: List[WindowRoleTemplate],
    ) -> ValidationResult:
        """
        Validate all role/template references in window mappings exist.

        Args:
            mappings: WindowRoleTemplate entries to validate.
        """
        errors: List[ValidationErrorDetail] = []

        for idx, m in enumerate(mappings):
            # Role exists
            if self._roles is not None:
                role = self._roles.get_by_id(m.role_id)
                if role is None:
                    errors.append(ValidationErrorDetail(
                        field=f"mappings[{idx}].role_id",
                        message=f"Referenced role ID {m.role_id} not found",
                        code="INVALID_REFERENCE",
                    ))

            # Template exists and is active
            if self._templates is not None:
                template = self._templates.get_by_id(m.template_id)
                if template is None:
                    errors.append(ValidationErrorDetail(
                        field=f"mappings[{idx}].template_id",
                        message=f"Referenced template ID {m.template_id} not found",
                        code="INVALID_REFERENCE",
                    ))
                elif not template.is_active:
                    errors.append(ValidationErrorDetail(
                        field=f"mappings[{idx}].template_id",
                        message=f"Referenced template ID {m.template_id} is inactive",
                        code="INACTIVE_REFERENCE",
                    ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    # ------------------------------------------------------------------
    # Topic hierarchy
    # ------------------------------------------------------------------

    def validate_topic_parent(
        self,
        topic_id: Optional[int],
        parent_topic_id: int,
    ) -> ValidationResult:
        """
        Validate parent_topic_id exists and does not create a cycle.

        Args:
            topic_id: ID of the topic being created/updated (None for new).
            parent_topic_id: Proposed parent topic ID.
        """
        if self._topics is None:
            return ValidationResult.success()

        errors: List[ValidationErrorDetail] = []

        # Self-reference check
        if topic_id is not None and parent_topic_id == topic_id:
            errors.append(ValidationErrorDetail(
                field="parent_topic_id",
                message="Topic cannot be its own parent",
                code="SELF_REFERENCE",
            ))
            return ValidationResult.failure(errors)

        # Parent must exist
        parent = self._topics.get_topic_by_id(parent_topic_id)
        if parent is None:
            errors.append(ValidationErrorDetail(
                field="parent_topic_id",
                message=f"Parent topic ID {parent_topic_id} not found",
                code="INVALID_REFERENCE",
            ))
            return ValidationResult.failure(errors)

        # Cycle detection
        if topic_id is not None:
            ancestors = self._topics.get_topic_ancestors(parent_topic_id)
            if topic_id in ancestors:
                errors.append(ValidationErrorDetail(
                    field="parent_topic_id",
                    message="Circular reference detected in topic hierarchy",
                    code="CIRCULAR_REFERENCE",
                ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    def validate_coding_topic_parent(
        self,
        topic_id: Optional[int],
        parent_topic_id: int,
    ) -> ValidationResult:
        """
        Validate coding topic parent reference.

        Same logic as validate_topic_parent but for coding_topics table.
        """
        if self._topics is None:
            return ValidationResult.success()

        errors: List[ValidationErrorDetail] = []

        if topic_id is not None and parent_topic_id == topic_id:
            errors.append(ValidationErrorDetail(
                field="parent_topic_id",
                message="Coding topic cannot be its own parent",
                code="SELF_REFERENCE",
            ))
            return ValidationResult.failure(errors)

        parent = self._topics.get_coding_topic_by_id(parent_topic_id)
        if parent is None:
            errors.append(ValidationErrorDetail(
                field="parent_topic_id",
                message=f"Parent coding topic ID {parent_topic_id} not found",
                code="INVALID_REFERENCE",
            ))
            return ValidationResult.failure(errors)

        if topic_id is not None:
            ancestors = self._topics.get_coding_topic_ancestors(parent_topic_id)
            if topic_id in ancestors:
                errors.append(ValidationErrorDetail(
                    field="parent_topic_id",
                    message="Circular reference detected in coding topic hierarchy",
                    code="CIRCULAR_REFERENCE",
                ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()
