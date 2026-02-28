"""
Validation Result Types

Immutable result containers for the validation layer.
ValidationResult collects all errors rather than failing fast,
enabling comprehensive feedback for admin UI workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ValidationErrorDetail:
    """
    Single validation error.

    Attributes:
        field:   Dot-delimited path to the offending field,
                 e.g. ``"template_structure.sections[0].rubric_id"``.
        message: Human-readable error description.
        code:    Machine-readable error identifier for programmatic handling.
    """

    field: str
    message: str
    code: str


@dataclass(frozen=True)
class ValidationResult:
    """
    Aggregated validation outcome.

    ``is_valid`` is True IFF ``errors`` is empty.
    This invariant is enforced by the factory methods; prefer using
    ``success()``, ``failure()``, or ``merge()`` over direct construction.
    """

    is_valid: bool
    errors: tuple[ValidationErrorDetail, ...] = ()  # tuple for immutability

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def success() -> ValidationResult:
        """Return a passing validation result with no errors."""
        return ValidationResult(is_valid=True, errors=())

    @staticmethod
    def failure(errors: List[ValidationErrorDetail]) -> ValidationResult:
        """
        Return a failing validation result.

        Args:
            errors: Non-empty list of error details.
        """
        if not errors:
            return ValidationResult.success()
        return ValidationResult(is_valid=False, errors=tuple(errors))

    @staticmethod
    def from_single(field: str, message: str, code: str) -> ValidationResult:
        """Convenience: construct a single-error failure."""
        return ValidationResult.failure([
            ValidationErrorDetail(field=field, message=message, code=code)
        ])

    # ------------------------------------------------------------------
    # Combinators
    # ------------------------------------------------------------------

    def merge(self, other: ValidationResult) -> ValidationResult:
        """
        Combine two results, accumulating errors from both.

        If either result has errors the merged result is invalid.
        """
        all_errors = self.errors + other.errors
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
        )

    @staticmethod
    def merge_all(*results: ValidationResult) -> ValidationResult:
        """Merge an arbitrary number of results."""
        combined_errors: List[ValidationErrorDetail] = []
        for r in results:
            combined_errors.extend(r.errors)
        return ValidationResult(
            is_valid=len(combined_errors) == 0,
            errors=tuple(combined_errors),
        )
