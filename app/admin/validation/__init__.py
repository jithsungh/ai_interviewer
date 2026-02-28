"""
Admin Validation Layer

Provides structural and cross-entity validation for all admin content types.
This layer is READ-ONLY: it never mutates entities or triggers side effects.

Key distinction from domain service validation:
  - Services raise on first error (fail-fast for RBAC/invariants).
  - This module collects ALL errors and returns a ValidationResult
    for comprehensive pre-save / pre-activation feedback.

Public API:
  - ValidationResult, ValidationErrorDetail (result types)
  - TemplateStructureValidator (template_structure JSONB validation)
  - RubricValidator (dimension consistency checks)
  - OverrideValidator (override field + base content ownership validation)
  - CrossReferenceValidator (existence checks across entities)
  - PreActivationValidator (readiness check before template activation)
"""

from .result import ValidationResult, ValidationErrorDetail

from .template_validator import TemplateStructureValidator
from .rubric_validator import RubricValidator
from .override_validator import OverrideValidator
from .cross_reference_validator import CrossReferenceValidator
from .pre_activation_validator import PreActivationValidator

__all__ = [
    # Result types
    "ValidationResult",
    "ValidationErrorDetail",
    # Validators
    "TemplateStructureValidator",
    "RubricValidator",
    "OverrideValidator",
    "CrossReferenceValidator",
    "PreActivationValidator",
]
