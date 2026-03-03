"""
Unit Tests — Ingestion Contracts (Pydantic validation)
and IngestionService dedup fingerprint logic.

Tests schema validation, boundary conditions, and deterministic
fingerprint generation. No database infrastructure needed.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

os.environ["TESTING"] = "1"

from pydantic import ValidationError as PydanticValidationError

from app.proctoring.ingestion.contracts.schemas import (
    BatchEventRequest,
    BatchIngestionResult,
    EventIngestionResult,
    ProctoringEventInput,
)
from app.proctoring.ingestion.domain.ingestion_service import IngestionService
from app.proctoring.rules.domain.rule_definitions import ALLOWED_EVENT_TYPES


# ════════════════════════════════════════════════════════════════════════
# ProctoringEventInput validation
# ════════════════════════════════════════════════════════════════════════


class TestProctoringEventInput:
    """Test Pydantic schema validation for single event input."""

    VALID_TIMESTAMP = "2026-02-14T10:30:15.234Z"

    def test_valid_event_type_accepted(self):
        for event_type in sorted(ALLOWED_EVENT_TYPES):
            event = ProctoringEventInput(
                submission_id=1,
                event_type=event_type,
                timestamp=self.VALID_TIMESTAMP,
            )
            assert event.event_type == event_type

    def test_all_allowed_types_are_valid(self):
        assert len(ALLOWED_EVENT_TYPES) == 12

    def test_unknown_event_type_rejected(self):
        with pytest.raises(PydanticValidationError) as exc_info:
            ProctoringEventInput(
                submission_id=1,
                event_type="invisible_cloak_activated",
                timestamp=self.VALID_TIMESTAMP,
            )
        assert "Unknown event type" in str(exc_info.value)

    def test_empty_event_type_rejected(self):
        with pytest.raises(PydanticValidationError):
            ProctoringEventInput(
                submission_id=1,
                event_type="",
                timestamp=self.VALID_TIMESTAMP,
            )

    def test_submission_id_positive_only(self):
        with pytest.raises(PydanticValidationError):
            ProctoringEventInput(
                submission_id=0,
                event_type="tab_switch",
                timestamp=self.VALID_TIMESTAMP,
            )
        with pytest.raises(PydanticValidationError):
            ProctoringEventInput(
                submission_id=-1,
                event_type="tab_switch",
                timestamp=self.VALID_TIMESTAMP,
            )

    def test_metadata_optional(self):
        event = ProctoringEventInput(
            submission_id=1,
            event_type="tab_switch",
            timestamp=self.VALID_TIMESTAMP,
        )
        assert event.metadata is None

    def test_metadata_accepted(self):
        event = ProctoringEventInput(
            submission_id=1,
            event_type="tab_switch",
            timestamp=self.VALID_TIMESTAMP,
            metadata={"tab_title": "[REDACTED]", "confidence": 0.89},
        )
        assert event.metadata["confidence"] == 0.89

    def test_timestamp_iso_format(self):
        event = ProctoringEventInput(
            submission_id=1,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234+00:00",
        )
        assert event.timestamp.year == 2026


# ════════════════════════════════════════════════════════════════════════
# BatchEventRequest validation
# ════════════════════════════════════════════════════════════════════════


class TestBatchEventRequest:
    """Test batch event request validation."""

    def _make_event(self, submission_id=42, event_type="tab_switch"):
        return ProctoringEventInput(
            submission_id=submission_id,
            event_type=event_type,
            timestamp="2026-02-14T10:30:15.234Z",
        )

    def test_valid_batch(self):
        batch = BatchEventRequest(
            submission_id=42,
            events=[self._make_event()],
        )
        assert len(batch.events) == 1

    def test_empty_events_rejected(self):
        with pytest.raises(PydanticValidationError):
            BatchEventRequest(
                submission_id=42,
                events=[],
            )

    def test_max_50_events(self):
        # 50 events → OK
        events_50 = [self._make_event() for _ in range(50)]
        batch = BatchEventRequest(submission_id=42, events=events_50)
        assert len(batch.events) == 50

    def test_over_50_events_rejected(self):
        events_51 = [self._make_event() for _ in range(51)]
        with pytest.raises(PydanticValidationError):
            BatchEventRequest(submission_id=42, events=events_51)

    def test_submission_id_positive(self):
        with pytest.raises(PydanticValidationError):
            BatchEventRequest(
                submission_id=0,
                events=[self._make_event(submission_id=0)],
            )


# ════════════════════════════════════════════════════════════════════════
# EventIngestionResult / BatchIngestionResult
# ════════════════════════════════════════════════════════════════════════


class TestResponseSchemas:
    """Test response schema construction."""

    def test_event_ingestion_result_accepted(self):
        result = EventIngestionResult(
            event_id=1,
            status="accepted",
            message="Event accepted and processed",
        )
        assert result.status == "accepted"
        assert result.event_id == 1

    def test_event_ingestion_result_duplicate(self):
        result = EventIngestionResult(
            event_id=None,
            status="duplicate",
            message="Duplicate",
        )
        assert result.event_id is None

    def test_batch_ingestion_result(self):
        result = BatchIngestionResult(
            accepted=8,
            rejected=2,
            event_ids=[1, 2, 3, 4, 5, 6, 7, 8],
            errors=[{"index": 4, "reason": "bad"}],
        )
        assert result.accepted == 8
        assert result.rejected == 2
        assert len(result.event_ids) == 8

    def test_batch_result_no_errors(self):
        result = BatchIngestionResult(
            accepted=5,
            rejected=0,
            event_ids=[1, 2, 3, 4, 5],
        )
        assert result.errors is None


# ════════════════════════════════════════════════════════════════════════
# IngestionService fingerprint + dedup (deterministic helpers)
# ════════════════════════════════════════════════════════════════════════


class TestIngestionServiceFingerprint:
    """Test the deterministic fingerprint used for deduplication."""

    def test_fingerprint_deterministic(self):
        event = ProctoringEventInput(
            submission_id=42,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        fp1 = IngestionService._fingerprint(event)
        fp2 = IngestionService._fingerprint(event)
        assert fp1 == fp2
        assert len(fp1) == 32  # SHA256 truncated to 32 hex chars

    def test_fingerprint_differs_for_different_events(self):
        event_a = ProctoringEventInput(
            submission_id=42,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        event_b = ProctoringEventInput(
            submission_id=42,
            event_type="face_absent",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        assert IngestionService._fingerprint(event_a) != IngestionService._fingerprint(event_b)

    def test_fingerprint_differs_for_different_timestamps(self):
        event_a = ProctoringEventInput(
            submission_id=42,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        event_b = ProctoringEventInput(
            submission_id=42,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:16.000Z",
        )
        assert IngestionService._fingerprint(event_a) != IngestionService._fingerprint(event_b)

    def test_fingerprint_differs_for_different_submissions(self):
        event_a = ProctoringEventInput(
            submission_id=42,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        event_b = ProctoringEventInput(
            submission_id=99,
            event_type="tab_switch",
            timestamp="2026-02-14T10:30:15.234Z",
        )
        assert IngestionService._fingerprint(event_a) != IngestionService._fingerprint(event_b)
