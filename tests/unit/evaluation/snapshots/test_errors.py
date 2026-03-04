"""
Unit Tests — Snapshot Errors

Tests snapshot-specific error classes.
"""

from __future__ import annotations

import pytest

from app.evaluation.snapshots.errors import (
    SnapshotError,
    SnapshotNotFoundError,
    SnapshotValidationError,
)


# ═══════════════════════════════════════════════════════════════════════════
# SnapshotError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotError:
    def test_is_exception(self):
        """SnapshotError should be an Exception."""
        error = SnapshotError()
        assert isinstance(error, Exception)

    def test_default_message(self):
        """Default message should be descriptive."""
        error = SnapshotError()
        assert "snapshot" in error.message.lower()

    def test_custom_message(self):
        """Custom message should be stored."""
        error = SnapshotError(message="Custom snapshot error")
        assert error.message == "Custom snapshot error"

    def test_http_status_500(self):
        """HTTP status should be 500."""
        error = SnapshotError()
        assert error.http_status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# SnapshotValidationError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotValidationError:
    def test_stores_reason(self):
        """Error should store validation reason."""
        error = SnapshotValidationError(
            reason="Missing dimension_id", snapshot_type="rubric"
        )
        assert error.reason == "Missing dimension_id"
        assert error.snapshot_type == "rubric"

    def test_message_includes_type_and_reason(self):
        """Error message should include snapshot type and reason."""
        error = SnapshotValidationError(
            reason="Empty dimensions", snapshot_type="rubric"
        )
        assert "rubric" in error.message
        assert "Empty dimensions" in error.message

    def test_http_status_422(self):
        """HTTP status should be 422."""
        error = SnapshotValidationError(reason="bad", snapshot_type="rubric")
        assert error.http_status_code == 422

    def test_error_code(self):
        """Error code should be SNAPSHOT_VALIDATION_FAILED."""
        error = SnapshotValidationError(reason="bad", snapshot_type="rubric")
        assert error.error_code == "SNAPSHOT_VALIDATION_FAILED"

    def test_metadata(self):
        """Metadata should include reason and snapshot_type."""
        error = SnapshotValidationError(
            reason="invalid", snapshot_type="template_weight"
        )
        assert error.metadata["reason"] == "invalid"
        assert error.metadata["snapshot_type"] == "template_weight"


# ═══════════════════════════════════════════════════════════════════════════
# SnapshotNotFoundError Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotNotFoundError:
    def test_stores_result_id_and_type(self):
        """Error should store result_id and snapshot_type."""
        error = SnapshotNotFoundError(result_id=5, snapshot_type="rubric")
        assert error.result_id == 5
        assert error.snapshot_type == "rubric"

    def test_message(self):
        """Error message should include type and result ID."""
        error = SnapshotNotFoundError(result_id=10, snapshot_type="template_weight")
        assert "template_weight" in error.message
        assert "10" in error.message

    def test_http_status_404(self):
        """HTTP status should be 404."""
        error = SnapshotNotFoundError(result_id=1, snapshot_type="rubric")
        assert error.http_status_code == 404

    def test_error_code(self):
        """Error code should be SNAPSHOT_NOT_FOUND."""
        error = SnapshotNotFoundError(result_id=1, snapshot_type="rubric")
        assert error.error_code == "SNAPSHOT_NOT_FOUND"

    def test_metadata(self):
        """Metadata should include result_id and snapshot_type."""
        error = SnapshotNotFoundError(result_id=7, snapshot_type="rubric")
        assert error.metadata["result_id"] == 7
        assert error.metadata["snapshot_type"] == "rubric"
