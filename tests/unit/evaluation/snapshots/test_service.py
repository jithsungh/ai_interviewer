"""
Unit Tests — Snapshot Service

Tests stateless snapshot creation, retrieval, validation, and comparison
functions with mocked database sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.evaluation.snapshots.errors import (
    SnapshotError,
    SnapshotNotFoundError,
    SnapshotValidationError,
)
from app.evaluation.snapshots.service import (
    compare_rubric_snapshots,
    create_rubric_snapshot,
    create_template_weight_snapshot,
    retrieve_rubric_snapshot,
    retrieve_template_weight_snapshot,
    validate_rubric_snapshot,
    validate_template_weight_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════
# create_rubric_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateRubricSnapshot:
    def setup_method(self):
        self.db = MagicMock(spec=Session)

    def test_creates_snapshot_from_rubric(self):
        """Should build a rubric snapshot dict from DB data."""
        # Mock rubric row
        rubric_row = Mock()
        rubric_row.id = 1
        rubric_row.name = "Technical Assessment"
        rubric_row.description = "Tests technical skills"
        self.db.execute.return_value.first.return_value = rubric_row

        # Mock dimension rows
        dim_row = Mock()
        dim_row.id = 10
        dim_row.dimension_name = "Accuracy"
        dim_row.weight = 0.5
        dim_row.max_score = 5.0
        dim_row.criteria = {"description": "desc", "scoring_criteria": "0-5"}
        dim_row.sequence_order = 1

        # execute().first() for rubric, execute().fetchall() for dimensions
        self.db.execute.side_effect = [
            Mock(first=Mock(return_value=rubric_row)),
            Mock(fetchall=Mock(return_value=[dim_row])),
        ]

        result = create_rubric_snapshot(self.db, rubric_id=1)

        assert result["rubric_id"] == 1
        assert result["rubric_name"] == "Technical Assessment"
        assert len(result["dimensions"]) == 1
        assert result["dimensions"][0]["dimension_id"] == 10
        assert "snapshot_timestamp" in result

    def test_rubric_not_found_raises(self):
        """Should raise SnapshotError if rubric not found."""
        self.db.execute.return_value.first.return_value = None

        with pytest.raises(SnapshotError, match="not found"):
            create_rubric_snapshot(self.db, rubric_id=999)

    def test_no_dimensions_raises(self):
        """Should raise SnapshotError if rubric has no dimensions."""
        rubric_row = Mock(id=1, name="Empty", description=None)
        self.db.execute.side_effect = [
            Mock(first=Mock(return_value=rubric_row)),
            Mock(fetchall=Mock(return_value=[])),
        ]

        with pytest.raises(SnapshotError, match="no dimensions"):
            create_rubric_snapshot(self.db, rubric_id=1)


# ═══════════════════════════════════════════════════════════════════════════
# create_template_weight_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateTemplateWeightSnapshot:
    def setup_method(self):
        self.db = MagicMock(spec=Session)

    def test_creates_snapshot(self):
        """Should build a template weight snapshot dict."""
        template_row = Mock()
        template_row.id = 5
        template_row.name = "Graduate Interview"
        self.db.execute.return_value.first.return_value = template_row

        result = create_template_weight_snapshot(
            self.db,
            template_id=5,
            section_weights={"technical": 60, "behavioral": 40},
        )

        assert result["template_id"] == 5
        assert result["template_name"] == "Graduate Interview"
        assert result["section_weights"]["technical"] == 60
        assert "snapshot_timestamp" in result

    def test_template_not_found_raises(self):
        """Should raise SnapshotError if template not found."""
        self.db.execute.return_value.first.return_value = None

        with pytest.raises(SnapshotError, match="not found"):
            create_template_weight_snapshot(
                self.db, template_id=999, section_weights={"a": 1}
            )


# ═══════════════════════════════════════════════════════════════════════════
# retrieve_rubric_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRetrieveRubricSnapshot:
    def setup_method(self):
        self.db = MagicMock(spec=Session)

    def test_returns_parsed_snapshot(self):
        """Should return a RubricSnapshot from stored JSONB."""
        now = datetime.now(timezone.utc).isoformat()
        mock_result = Mock()
        mock_result.rubric_snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "dimensions": [
                {
                    "dimension_id": 10,
                    "dimension_name": "Accuracy",
                    "weight": 1.0,
                    "max_score": 5.0,
                }
            ],
            "snapshot_timestamp": now,
        }

        self.db.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        snapshot = retrieve_rubric_snapshot(self.db, result_id=1)
        assert snapshot.rubric_id == 1
        assert len(snapshot.dimensions) == 1

    def test_result_not_found_raises(self):
        """Should raise SnapshotNotFoundError if result missing."""
        self.db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(SnapshotNotFoundError):
            retrieve_rubric_snapshot(self.db, result_id=999)

    def test_empty_snapshot_raises(self):
        """Should raise SnapshotNotFoundError if snapshot is null."""
        mock_result = Mock()
        mock_result.rubric_snapshot = None
        self.db.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        with pytest.raises(SnapshotNotFoundError):
            retrieve_rubric_snapshot(self.db, result_id=1)

    def test_malformed_snapshot_raises_validation(self):
        """Should raise SnapshotValidationError on bad data."""
        mock_result = Mock()
        mock_result.rubric_snapshot = {"invalid": True}
        self.db.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        with pytest.raises(SnapshotValidationError):
            retrieve_rubric_snapshot(self.db, result_id=1)


# ═══════════════════════════════════════════════════════════════════════════
# retrieve_template_weight_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRetrieveTemplateWeightSnapshot:
    def setup_method(self):
        self.db = MagicMock(spec=Session)

    def test_returns_parsed_snapshot(self):
        """Should return a TemplateWeightSnapshot from stored JSONB."""
        now = datetime.now(timezone.utc).isoformat()
        mock_result = Mock()
        mock_result.template_weight_snapshot = {
            "template_id": 5,
            "template_name": "Senior",
            "section_weights": {"tech": 70, "soft": 30},
            "snapshot_timestamp": now,
        }
        self.db.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        snapshot = retrieve_template_weight_snapshot(self.db, result_id=1)
        assert snapshot.template_id == 5

    def test_result_not_found_raises(self):
        """Should raise SnapshotNotFoundError if result missing."""
        self.db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(SnapshotNotFoundError):
            retrieve_template_weight_snapshot(self.db, result_id=999)

    def test_empty_snapshot_raises(self):
        """Should raise SnapshotNotFoundError if snapshot is null."""
        mock_result = Mock()
        mock_result.template_weight_snapshot = None
        self.db.query.return_value.filter.return_value.first.return_value = (
            mock_result
        )

        with pytest.raises(SnapshotNotFoundError):
            retrieve_template_weight_snapshot(self.db, result_id=1)


# ═══════════════════════════════════════════════════════════════════════════
# validate_rubric_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateRubricSnapshot:
    def test_valid_snapshot_returns_none(self):
        """Valid snapshot should return None (no error)."""
        snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "dimensions": [
                {
                    "dimension_id": 1,
                    "dimension_name": "D1",
                    "weight": 1.0,
                    "max_score": 5.0,
                }
            ],
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        assert validate_rubric_snapshot(snapshot) is None

    def test_empty_snapshot(self):
        """Empty snapshot should return error."""
        result = validate_rubric_snapshot({})
        assert result is not None
        assert "empty" in result.lower()

    def test_none_snapshot(self):
        """None snapshot should return error."""
        result = validate_rubric_snapshot(None)
        assert result is not None

    def test_missing_rubric_id(self):
        """Missing rubric_id should return error."""
        snapshot = {
            "rubric_name": "Test",
            "dimensions": [
                {"dimension_id": 1, "dimension_name": "D", "weight": 1, "max_score": 5}
            ],
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None
        assert "rubric_id" in result

    def test_missing_dimensions(self):
        """Missing dimensions should return error."""
        snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None

    def test_empty_dimensions_list(self):
        """Empty dimensions list should return error."""
        snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "dimensions": [],
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None

    def test_dimension_missing_required_field(self):
        """Dimension missing required field should return error."""
        snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "dimensions": [{"dimension_id": 1}],
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None

    def test_missing_snapshot_timestamp(self):
        """Missing snapshot_timestamp should return error."""
        snapshot = {
            "rubric_id": 1,
            "rubric_name": "Test",
            "dimensions": [
                {"dimension_id": 1, "dimension_name": "D", "weight": 1, "max_score": 5}
            ],
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None

    def test_multi_rubric_container(self):
        """Multi-rubric container should validate each rubric."""
        snapshot = {
            "rubrics": [
                {
                    "rubric_id": 1,
                    "rubric_name": "R1",
                    "dimensions": [
                        {"dimension_id": 1, "dimension_name": "D", "weight": 1, "max_score": 5}
                    ],
                    "snapshot_timestamp": "2024-01-01T00:00:00Z",
                },
            ]
        }
        assert validate_rubric_snapshot(snapshot) is None

    def test_multi_rubric_invalid_entry(self):
        """Multi-rubric with invalid entry should return error."""
        snapshot = {
            "rubrics": [
                {"rubric_name": "Missing ID"},  # invalid
            ]
        }
        result = validate_rubric_snapshot(snapshot)
        assert result is not None
        assert "rubrics[0]" in result


# ═══════════════════════════════════════════════════════════════════════════
# validate_template_weight_snapshot Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateTemplateWeightSnapshot:
    def test_valid_snapshot_returns_none(self):
        """Valid snapshot should return None."""
        snapshot = {
            "template_id": 5,
            "section_weights": {"tech": 70, "soft": 30},
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        assert validate_template_weight_snapshot(snapshot) is None

    def test_empty_snapshot(self):
        """Empty snapshot should return error."""
        result = validate_template_weight_snapshot({})
        assert result is not None

    def test_missing_template_id(self):
        """Missing template_id should return error."""
        snapshot = {"section_weights": {"a": 1}, "snapshot_timestamp": "2024-01-01T00:00:00Z"}
        result = validate_template_weight_snapshot(snapshot)
        assert result is not None

    def test_missing_section_weights(self):
        """Missing section_weights should return error."""
        snapshot = {"template_id": 1, "snapshot_timestamp": "2024-01-01T00:00:00Z"}
        result = validate_template_weight_snapshot(snapshot)
        assert result is not None

    def test_negative_weight_returns_error(self):
        """Negative weight should return error."""
        snapshot = {
            "template_id": 1,
            "section_weights": {"tech": -10},
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }
        result = validate_template_weight_snapshot(snapshot)
        assert result is not None
        assert "tech" in result

    def test_missing_snapshot_timestamp(self):
        """Missing snapshot_timestamp should return error."""
        snapshot = {
            "template_id": 1,
            "section_weights": {"a": 1},
        }
        result = validate_template_weight_snapshot(snapshot)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════
# compare_rubric_snapshots Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCompareRubricSnapshots:
    def _make_snapshot(self, rubric_id=1, name="R1", dims=None):
        return {
            "rubric_id": rubric_id,
            "rubric_name": name,
            "dimensions": dims or [
                {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
            ],
            "snapshot_timestamp": "2024-01-01T00:00:00Z",
        }

    def test_identical_snapshots(self):
        """Identical snapshots should report identical=True."""
        a = self._make_snapshot()
        result = compare_rubric_snapshots(a, a)
        assert result["identical"] is True
        assert result["differences"] == []

    def test_different_rubric_name(self):
        """Changed rubric_name should be detected."""
        a = self._make_snapshot(name="R1")
        b = self._make_snapshot(name="R2")
        result = compare_rubric_snapshots(a, b)
        assert result["identical"] is False
        names = [d["field"] for d in result["differences"] if "field" in d]
        assert "rubric_name" in names

    def test_added_dimension(self):
        """New dimension in snapshot_b should be detected."""
        a = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
        ])
        b = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
            {"dimension_id": 2, "dimension_name": "D2", "weight": 0.5, "max_score": 5.0},
        ])
        result = compare_rubric_snapshots(a, b)
        assert result["identical"] is False
        types = [d["type"] for d in result["differences"] if "type" in d]
        assert "dimensions_added" in types

    def test_removed_dimension(self):
        """Removed dimension in snapshot_b should be detected."""
        a = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
            {"dimension_id": 2, "dimension_name": "D2", "weight": 0.5, "max_score": 5.0},
        ])
        b = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
        ])
        result = compare_rubric_snapshots(a, b)
        assert result["identical"] is False
        types = [d["type"] for d in result["differences"] if "type" in d]
        assert "dimensions_removed" in types

    def test_changed_dimension_weight(self):
        """Changed dimension weight should be detected."""
        a = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 1.0, "max_score": 5.0},
        ])
        b = self._make_snapshot(dims=[
            {"dimension_id": 1, "dimension_name": "D1", "weight": 2.0, "max_score": 5.0},
        ])
        result = compare_rubric_snapshots(a, b)
        assert result["identical"] is False
        changes = [
            d for d in result["differences"]
            if d.get("type") == "dimension_changed" and d.get("field") == "weight"
        ]
        assert len(changes) == 1
