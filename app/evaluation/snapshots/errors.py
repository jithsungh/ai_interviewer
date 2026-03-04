"""
Evaluation Snapshots — Error Classes

Snapshot-specific errors for validation and retrieval operations.
"""

from __future__ import annotations

from app.shared.errors import BaseError


class SnapshotError(BaseError):
    """Base error for snapshot operations."""

    def __init__(
        self,
        message: str = "Snapshot error",
        error_code: str = "SNAPSHOT_ERROR",
        **kwargs,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            http_status_code=500,
            metadata=kwargs,
        )


class SnapshotValidationError(BaseError):
    """Snapshot structure failed validation."""

    def __init__(self, reason: str, snapshot_type: str = "unknown") -> None:
        self.reason = reason
        self.snapshot_type = snapshot_type
        super().__init__(
            error_code="SNAPSHOT_VALIDATION_FAILED",
            message=f"Invalid {snapshot_type} snapshot: {reason}",
            http_status_code=422,
            metadata={"reason": reason, "snapshot_type": snapshot_type},
        )


class SnapshotNotFoundError(BaseError):
    """Snapshot data not found on interview result."""

    def __init__(
        self,
        result_id: int,
        snapshot_type: str,
    ) -> None:
        self.result_id = result_id
        self.snapshot_type = snapshot_type
        super().__init__(
            error_code="SNAPSHOT_NOT_FOUND",
            message=(
                f"{snapshot_type} snapshot not found on result {result_id}"
            ),
            http_status_code=404,
            metadata={
                "result_id": result_id,
                "snapshot_type": snapshot_type,
            },
        )
