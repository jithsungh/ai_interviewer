"""
Unit tests for RubricValidator.

Tests dimension weight sums, sequence order uniqueness, and per-dimension checks.
Pure domain logic — no mocks, no DB.
"""

import pytest
from decimal import Decimal

from app.admin.domain.entities import RubricDimension
from app.admin.validation.rubric_validator import RubricValidator


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


def _dim(
    name: str = "D",
    weight: str = "0.5",
    max_score: str = "10",
    seq: int = 0,
    rubric_id: int = 1,
) -> RubricDimension:
    """Shortcut to build a RubricDimension."""
    return RubricDimension(
        id=None,
        rubric_id=rubric_id,
        dimension_name=name,
        description=f"Description for {name}",
        max_score=Decimal(max_score),
        weight=Decimal(weight),
        sequence_order=seq,
    )


# ─────────────────────────────────────────────────────────────────
# Valid dimensions
# ─────────────────────────────────────────────────────────────────


class TestValidDimensions:
    def test_two_dimensions_summing_to_one(self):
        dims = [_dim("A", "0.6", seq=1), _dim("B", "0.4", seq=2)]
        result = RubricValidator.validate_dimensions(dims)
        assert result.is_valid, [e.message for e in result.errors]

    def test_single_dimension_weight_one(self):
        result = RubricValidator.validate_dimensions([_dim("Only", "1.0", seq=1)])
        assert result.is_valid

    def test_three_dimensions_summing_to_one(self):
        dims = [
            _dim("A", "0.333", seq=1),
            _dim("B", "0.333", seq=2),
            _dim("C", "0.334", seq=3),
        ]
        result = RubricValidator.validate_dimensions(dims)
        assert result.is_valid

    def test_weights_within_tolerance(self):
        """Allow tiny floating point drift within RUBRIC_WEIGHT_TOLERANCE."""
        dims = [_dim("A", "0.6005", seq=1), _dim("B", "0.4", seq=2)]
        result = RubricValidator.validate_dimensions(dims)
        # 0.6005 + 0.4 = 1.0005 — within 0.001 tolerance
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Weight sum violations
# ─────────────────────────────────────────────────────────────────


class TestWeightSumViolation:
    def test_weights_under_one(self):
        dims = [_dim("A", "0.5", seq=1), _dim("B", "0.3", seq=2)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "WEIGHT_SUM_MISMATCH" for e in result.errors)

    def test_weights_over_one(self):
        dims = [_dim("A", "0.6", seq=1), _dim("B", "0.6", seq=2)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "WEIGHT_SUM_MISMATCH" for e in result.errors)

    def test_weights_far_from_one(self):
        dims = [_dim("A", "0.1", seq=1)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "WEIGHT_SUM_MISMATCH" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Empty dimensions
# ─────────────────────────────────────────────────────────────────


class TestEmptyDimensions:
    def test_empty_list(self):
        result = RubricValidator.validate_dimensions([])
        assert not result.is_valid
        assert any(e.code == "EMPTY_DIMENSIONS" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Duplicate sequence order
# ─────────────────────────────────────────────────────────────────


class TestDuplicateSequenceOrder:
    def test_duplicate_order(self):
        dims = [_dim("A", "0.5", seq=1), _dim("B", "0.5", seq=1)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "DUPLICATE_SEQUENCE_ORDER" for e in result.errors)

    def test_unique_orders_pass(self):
        dims = [_dim("A", "0.5", seq=1), _dim("B", "0.5", seq=2)]
        result = RubricValidator.validate_dimensions(dims)
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Individual dimension validation
# ─────────────────────────────────────────────────────────────────


class TestIndividualDimensions:
    def test_empty_name(self):
        dims = [_dim("", "1.0", seq=1)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "EMPTY_DIMENSION_NAME" for e in result.errors)

    def test_whitespace_only_name(self):
        dims = [_dim("   ", "1.0", seq=1)]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        assert any(e.code == "EMPTY_DIMENSION_NAME" for e in result.errors)

    def test_non_positive_max_score(self):
        dim = _dim("A", "1.0", max_score="0", seq=1)
        result = RubricValidator.validate_dimensions([dim])
        assert not result.is_valid
        assert any(e.code == "NON_POSITIVE_MAX_SCORE" for e in result.errors)

    def test_negative_max_score(self):
        dim = _dim("A", "1.0", max_score="-5", seq=1)
        result = RubricValidator.validate_dimensions([dim])
        assert not result.is_valid
        assert any(e.code == "NON_POSITIVE_MAX_SCORE" for e in result.errors)

    def test_non_positive_weight(self):
        dim = RubricDimension(
            id=None,
            rubric_id=1,
            dimension_name="A",
            description=None,
            max_score=Decimal("10"),
            weight=Decimal("0"),
            sequence_order=1,
        )
        result = RubricValidator.validate_dimensions([dim])
        assert not result.is_valid
        assert any(e.code == "NON_POSITIVE_WEIGHT" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# validate_dimension_weights_from_dicts
# ─────────────────────────────────────────────────────────────────


class TestValidateDimensionWeightsFromDicts:
    def test_valid_dicts(self):
        dicts = [{"weight": 0.6}, {"weight": 0.4}]
        result = RubricValidator.validate_dimension_weights_from_dicts(dicts)
        assert result.is_valid

    def test_empty_dicts(self):
        result = RubricValidator.validate_dimension_weights_from_dicts([])
        assert not result.is_valid
        assert any(e.code == "EMPTY_DIMENSIONS" for e in result.errors)

    def test_missing_weight(self):
        dicts = [{"name": "A"}, {"weight": 1.0}]
        result = RubricValidator.validate_dimension_weights_from_dicts(dicts)
        assert not result.is_valid
        assert any(e.code == "MISSING_WEIGHT" for e in result.errors)

    def test_invalid_weight_type(self):
        dicts = [{"weight": "abc"}, {"weight": 0.5}]
        result = RubricValidator.validate_dimension_weights_from_dicts(dicts)
        assert not result.is_valid
        assert any(e.code == "INVALID_WEIGHT" for e in result.errors)

    def test_non_positive_weight(self):
        dicts = [{"weight": -0.5}, {"weight": 1.5}]
        result = RubricValidator.validate_dimension_weights_from_dicts(dicts)
        assert not result.is_valid
        assert any(e.code == "NON_POSITIVE_WEIGHT" for e in result.errors)

    def test_sum_mismatch(self):
        dicts = [{"weight": 0.3}, {"weight": 0.3}]
        result = RubricValidator.validate_dimension_weights_from_dicts(dicts)
        assert not result.is_valid
        assert any(e.code == "WEIGHT_SUM_MISMATCH" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# validate_criteria_schema
# ─────────────────────────────────────────────────────────────────


class TestValidateCriteriaSchema:
    def test_none_is_valid(self):
        result = RubricValidator.validate_criteria_schema(None)
        assert result.is_valid

    def test_dict_is_valid(self):
        result = RubricValidator.validate_criteria_schema({"key": "value"})
        assert result.is_valid

    def test_non_dict_fails(self):
        result = RubricValidator.validate_criteria_schema("not a dict")  # type: ignore[arg-type]
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_CRITERIA_TYPE"


# ─────────────────────────────────────────────────────────────────
# Multiple errors accumulated
# ─────────────────────────────────────────────────────────────────


class TestMultipleErrors:
    def test_multiple_problems_collected(self):
        """Validator collects all errors — not fail-fast."""
        dims = [
            RubricDimension(
                id=None,
                rubric_id=1,
                dimension_name="",
                description=None,
                max_score=Decimal("-1"),
                weight=Decimal("0"),
                sequence_order=1,
            ),
            RubricDimension(
                id=None,
                rubric_id=1,
                dimension_name="  ",
                description=None,
                max_score=Decimal("-5"),
                weight=Decimal("0"),
                sequence_order=1,
            ),
        ]
        result = RubricValidator.validate_dimensions(dims)
        assert not result.is_valid
        # Should have errors for: empty names (2), negative max_scores (2),
        # non-positive weights (2), duplicate sequence_order, weight sum mismatch
        assert len(result.errors) >= 5
