"""
Unit Tests — Snapshot Schemas

Tests Pydantic snapshot models for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.evaluation.snapshots.schemas import (
    DimensionSnapshot,
    MultiRubricSnapshot,
    RubricSnapshot,
    TemplateWeightSnapshot,
)


NOW = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# DimensionSnapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionSnapshot:
    def test_valid_snapshot(self):
        """Valid dimension snapshot should be created."""
        snap = DimensionSnapshot(
            dimension_id=1,
            dimension_name="Technical Accuracy",
            weight=0.4,
            max_score=5.0,
        )
        assert snap.dimension_id == 1
        assert snap.dimension_name == "Technical Accuracy"
        assert snap.weight == 0.4
        assert snap.max_score == 5.0

    def test_optional_fields(self):
        """Optional fields should default to None."""
        snap = DimensionSnapshot(
            dimension_id=1,
            dimension_name="Accuracy",
            weight=1.0,
            max_score=5.0,
        )
        assert snap.description is None
        assert snap.scoring_criteria is None

    def test_with_all_fields(self):
        """All fields including optional should be populated."""
        snap = DimensionSnapshot(
            dimension_id=2,
            dimension_name="Communication",
            weight=0.3,
            max_score=10.0,
            description="Clarity of communication",
            scoring_criteria="0-3: poor, 4-7: average, 8-10: excellent",
        )
        assert snap.description == "Clarity of communication"
        assert snap.scoring_criteria is not None

    def test_frozen(self):
        """DimensionSnapshot should be immutable (frozen)."""
        snap = DimensionSnapshot(
            dimension_id=1,
            dimension_name="Test",
            weight=1.0,
            max_score=5.0,
        )
        with pytest.raises(ValidationError):
            snap.weight = 2.0

    def test_dimension_id_gt_zero(self):
        """dimension_id must be > 0."""
        with pytest.raises(ValidationError):
            DimensionSnapshot(
                dimension_id=0,
                dimension_name="Test",
                weight=1.0,
                max_score=5.0,
            )

    def test_max_score_gt_zero(self):
        """max_score must be > 0."""
        with pytest.raises(ValidationError):
            DimensionSnapshot(
                dimension_id=1,
                dimension_name="Test",
                weight=1.0,
                max_score=0,
            )

    def test_weight_ge_zero(self):
        """weight must be >= 0."""
        with pytest.raises(ValidationError):
            DimensionSnapshot(
                dimension_id=1,
                dimension_name="Test",
                weight=-0.1,
                max_score=5.0,
            )

    def test_empty_name_rejected(self):
        """Empty dimension_name should be rejected."""
        with pytest.raises(ValidationError):
            DimensionSnapshot(
                dimension_id=1,
                dimension_name="",
                weight=1.0,
                max_score=5.0,
            )


# ═══════════════════════════════════════════════════════════════════════════
# RubricSnapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRubricSnapshot:
    def _make_dimension(self, dim_id: int = 1) -> DimensionSnapshot:
        return DimensionSnapshot(
            dimension_id=dim_id,
            dimension_name=f"Dimension {dim_id}",
            weight=1.0,
            max_score=5.0,
        )

    def test_valid_snapshot(self):
        """Valid rubric snapshot should be created."""
        snap = RubricSnapshot(
            rubric_id=1,
            rubric_name="Technical Assessment",
            dimensions=[self._make_dimension(1), self._make_dimension(2)],
            snapshot_timestamp=NOW,
        )
        assert snap.rubric_id == 1
        assert len(snap.dimensions) == 2

    def test_optional_description(self):
        """rubric_description should be optional."""
        snap = RubricSnapshot(
            rubric_id=1,
            rubric_name="Test",
            dimensions=[self._make_dimension()],
            snapshot_timestamp=NOW,
        )
        assert snap.rubric_description is None

    def test_frozen(self):
        """RubricSnapshot should be immutable."""
        snap = RubricSnapshot(
            rubric_id=1,
            rubric_name="Test",
            dimensions=[self._make_dimension()],
            snapshot_timestamp=NOW,
        )
        with pytest.raises(ValidationError):
            snap.rubric_name = "Changed"

    def test_empty_dimensions_rejected(self):
        """At least one dimension is required."""
        with pytest.raises(ValidationError):
            RubricSnapshot(
                rubric_id=1,
                rubric_name="Test",
                dimensions=[],
                snapshot_timestamp=NOW,
            )

    def test_duplicate_dimension_ids_rejected(self):
        """Duplicate dimension_ids should be rejected."""
        d1 = self._make_dimension(1)
        d2 = DimensionSnapshot(
            dimension_id=1,  # Duplicate
            dimension_name="Another",
            weight=0.5,
            max_score=5.0,
        )
        with pytest.raises(ValidationError, match="Duplicate"):
            RubricSnapshot(
                rubric_id=1,
                rubric_name="Test",
                dimensions=[d1, d2],
                snapshot_timestamp=NOW,
            )

    def test_rubric_id_gt_zero(self):
        """rubric_id must be > 0."""
        with pytest.raises(ValidationError):
            RubricSnapshot(
                rubric_id=0,
                rubric_name="Test",
                dimensions=[self._make_dimension()],
                snapshot_timestamp=NOW,
            )

    def test_serialization_roundtrip(self):
        """Snapshot should serialize and deserialize consistently."""
        snap = RubricSnapshot(
            rubric_id=1,
            rubric_name="Test Rubric",
            rubric_description="Description",
            dimensions=[self._make_dimension(1)],
            snapshot_timestamp=NOW,
        )
        data = snap.model_dump(mode="json")
        restored = RubricSnapshot.model_validate(data)
        assert restored.rubric_id == snap.rubric_id
        assert len(restored.dimensions) == 1


# ═══════════════════════════════════════════════════════════════════════════
# TemplateWeightSnapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateWeightSnapshot:
    def test_valid_snapshot(self):
        """Valid template weight snapshot should be created."""
        snap = TemplateWeightSnapshot(
            template_id=5,
            template_name="Graduate Interview",
            section_weights={"technical": 60, "behavioral": 40},
            snapshot_timestamp=NOW,
        )
        assert snap.template_id == 5
        assert snap.section_weights["technical"] == 60

    def test_frozen(self):
        """TemplateWeightSnapshot should be immutable."""
        snap = TemplateWeightSnapshot(
            template_id=1,
            template_name="Test",
            section_weights={"a": 100},
            snapshot_timestamp=NOW,
        )
        with pytest.raises(ValidationError):
            snap.template_name = "Changed"

    def test_empty_section_weights_rejected(self):
        """At least one section weight is required."""
        with pytest.raises(ValidationError):
            TemplateWeightSnapshot(
                template_id=1,
                template_name="Test",
                section_weights={},
                snapshot_timestamp=NOW,
            )

    def test_negative_weight_rejected(self):
        """Negative weight should be rejected."""
        with pytest.raises(ValidationError, match=">="):
            TemplateWeightSnapshot(
                template_id=1,
                template_name="Test",
                section_weights={"technical": -10},
                snapshot_timestamp=NOW,
            )

    def test_zero_weight_allowed(self):
        """Zero weight should be valid (section has no impact)."""
        snap = TemplateWeightSnapshot(
            template_id=1,
            template_name="Test",
            section_weights={"optional": 0, "required": 100},
            snapshot_timestamp=NOW,
        )
        assert snap.section_weights["optional"] == 0

    def test_serialization_roundtrip(self):
        """Snapshot should serialize and deserialize consistently."""
        snap = TemplateWeightSnapshot(
            template_id=3,
            template_name="Senior",
            section_weights={"tech": 70, "soft": 30},
            snapshot_timestamp=NOW,
        )
        data = snap.model_dump(mode="json")
        restored = TemplateWeightSnapshot.model_validate(data)
        assert restored.section_weights == snap.section_weights


# ═══════════════════════════════════════════════════════════════════════════
# MultiRubricSnapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiRubricSnapshot:
    def _make_rubric_snapshot(self, rid: int = 1) -> RubricSnapshot:
        return RubricSnapshot(
            rubric_id=rid,
            rubric_name=f"Rubric {rid}",
            dimensions=[
                DimensionSnapshot(
                    dimension_id=rid * 10 + 1,
                    dimension_name=f"Dim {rid}.1",
                    weight=1.0,
                    max_score=5.0,
                ),
            ],
            snapshot_timestamp=NOW,
        )

    def test_valid_multi_snapshot(self):
        """MultiRubricSnapshot should accept multiple rubrics."""
        snap = MultiRubricSnapshot(
            rubrics=[self._make_rubric_snapshot(1), self._make_rubric_snapshot(2)],
            snapshot_timestamp=NOW,
        )
        assert len(snap.rubrics) == 2

    def test_empty_rubrics_rejected(self):
        """At least one rubric is required."""
        with pytest.raises(ValidationError):
            MultiRubricSnapshot(rubrics=[], snapshot_timestamp=NOW)

    def test_frozen(self):
        """MultiRubricSnapshot should be immutable."""
        snap = MultiRubricSnapshot(
            rubrics=[self._make_rubric_snapshot(1)],
            snapshot_timestamp=NOW,
        )
        with pytest.raises(ValidationError):
            snap.snapshot_timestamp = NOW
