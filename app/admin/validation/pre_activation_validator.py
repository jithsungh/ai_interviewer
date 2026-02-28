"""
Pre-Activation Validator

Composite validator that runs ALL checks required before a template
can be activated.  Acts as the single entry point for the
"validate before activate" workflow described in admin/REQUIREMENTS.md.

Orchestrates:
  1. Template structure validation (TemplateStructureValidator)
  2. Template → rubric cross-reference checks
  3. Template → role cross-reference checks
  4. Rubric dimension consistency for every linked rubric

Requires repository access (via protocol interfaces) for lookups.
All operations are read-only.
"""

from __future__ import annotations

from typing import List, Optional

from app.admin.domain.entities import Template, TemplateRubric
from app.admin.domain.protocols import (
    RoleRepository,
    RubricRepository,
    TemplateRepository,
)

from .cross_reference_validator import CrossReferenceValidator
from .result import ValidationErrorDetail, ValidationResult
from .rubric_validator import RubricValidator
from .template_validator import TemplateStructureValidator


class PreActivationValidator:
    """
    Composite validator for template pre-activation readiness.

    Accepts repository protocols via the constructor (DI).
    """

    def __init__(
        self,
        *,
        template_repo: TemplateRepository,
        rubric_repo: RubricRepository,
        role_repo: RoleRepository,
    ) -> None:
        self._templates = template_repo
        self._rubrics = rubric_repo
        self._roles = role_repo
        self._xref = CrossReferenceValidator(
            template_repo=template_repo,
            rubric_repo=rubric_repo,
            role_repo=role_repo,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def validate(
        self,
        template: Template,
        role_ids: List[int],
        rubric_mappings: List[TemplateRubric],
    ) -> ValidationResult:
        """
        Run all pre-activation checks for a template.

        Args:
            template: The template entity to validate.
            role_ids: Role IDs currently assigned to the template.
            rubric_mappings: TemplateRubric mappings for the template.

        Returns:
            Merged ValidationResult with all discovered errors.
        """
        results: List[ValidationResult] = []

        # 1. Template must have a name
        if not template.name or not template.name.strip():
            results.append(ValidationResult.from_single(
                field="name",
                message="Template name is required",
                code="MISSING_NAME",
            ))

        # 2. Template structure validation
        results.append(
            TemplateStructureValidator.validate(template.template_structure)
        )

        # 3. Must have at least one role assignment
        if not role_ids:
            results.append(ValidationResult.from_single(
                field="role_ids",
                message="Template must have at least one role assigned before activation",
                code="NO_ROLES",
            ))
        else:
            results.append(self._xref.validate_template_role_refs(role_ids))

        # 4. Rubric cross-references
        rubric_ids = [rm.rubric_id for rm in rubric_mappings]
        if rubric_ids:
            results.append(self._xref.validate_template_rubric_refs(rubric_ids))

            # 5. Validate dimension consistency for each linked rubric
            results.append(self._validate_linked_rubric_dimensions(rubric_ids))

        return ValidationResult.merge_all(*results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_linked_rubric_dimensions(
        self,
        rubric_ids: List[int],
    ) -> ValidationResult:
        """
        For each linked rubric, load its dimensions and validate
        weight sum & uniqueness.
        """
        errors: List[ValidationErrorDetail] = []

        seen: set = set()
        for rid in rubric_ids:
            if rid in seen:
                continue
            seen.add(rid)

            dimensions = self._rubrics.get_dimensions(rid)
            if not dimensions:
                # No dimensions — that may or may not be an error
                # depending on business rules. For activation, warn.
                errors.append(ValidationErrorDetail(
                    field=f"rubric_id_{rid}.dimensions",
                    message=f"Rubric ID {rid} has no dimensions defined",
                    code="EMPTY_DIMENSIONS",
                ))
                continue

            dim_result = RubricValidator.validate_dimensions(dimensions)
            if not dim_result.is_valid:
                # Prefix errors with rubric context
                for err in dim_result.errors:
                    errors.append(ValidationErrorDetail(
                        field=f"rubric_id_{rid}.{err.field}",
                        message=f"[Rubric {rid}] {err.message}",
                        code=err.code,
                    ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()
