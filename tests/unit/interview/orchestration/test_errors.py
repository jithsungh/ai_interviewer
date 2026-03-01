"""
Unit Tests — Orchestration Errors

Tests error construction, error codes, HTTP status codes, and metadata.
"""

import pytest

from app.interview.orchestration.errors import (
    AudioNotReadyError,
    CodeNotReadyError,
    InterviewCompleteError,
    SequenceMismatchError,
    TemplateSnapshotInvalidError,
    TemplateSnapshotMissingError,
)
from app.shared.errors import BaseError


class TestTemplateSnapshotMissingError:
    def test_inherits_base_error(self):
        err = TemplateSnapshotMissingError(submission_id=42)
        assert isinstance(err, BaseError)

    def test_error_code(self):
        err = TemplateSnapshotMissingError(submission_id=42)
        assert err.error_code == "TEMPLATE_SNAPSHOT_MISSING"

    def test_http_status(self):
        err = TemplateSnapshotMissingError(submission_id=42)
        assert err.http_status_code == 500

    def test_metadata(self):
        err = TemplateSnapshotMissingError(submission_id=42)
        assert err.metadata["submission_id"] == 42

    def test_message_contains_submission_id(self):
        err = TemplateSnapshotMissingError(submission_id=42)
        assert "42" in err.message


class TestTemplateSnapshotInvalidError:
    def test_error_code(self):
        err = TemplateSnapshotInvalidError(submission_id=1, reason="bad structure")
        assert err.error_code == "TEMPLATE_SNAPSHOT_INVALID"

    def test_reason_in_metadata(self):
        err = TemplateSnapshotInvalidError(submission_id=1, reason="bad structure")
        assert err.metadata["reason"] == "bad structure"


class TestInterviewCompleteError:
    def test_error_code(self):
        err = InterviewCompleteError(submission_id=1, total_questions=10)
        assert err.error_code == "INTERVIEW_COMPLETE"

    def test_http_status(self):
        err = InterviewCompleteError(submission_id=1, total_questions=10)
        assert err.http_status_code == 400

    def test_metadata(self):
        err = InterviewCompleteError(submission_id=1, total_questions=10)
        assert err.metadata["total_questions"] == 10


class TestSequenceMismatchError:
    def test_error_code(self):
        err = SequenceMismatchError(
            submission_id=1, expected_sequence=3, received_sequence=5
        )
        assert err.error_code == "SEQUENCE_MISMATCH"

    def test_http_status(self):
        err = SequenceMismatchError(
            submission_id=1, expected_sequence=3, received_sequence=5
        )
        assert err.http_status_code == 409

    def test_metadata(self):
        err = SequenceMismatchError(
            submission_id=1, expected_sequence=3, received_sequence=5
        )
        assert err.metadata["expected_sequence"] == 3
        assert err.metadata["received_sequence"] == 5

    def test_message(self):
        err = SequenceMismatchError(
            submission_id=1, expected_sequence=3, received_sequence=5
        )
        assert "expected 3" in err.message
        assert "received 5" in err.message


class TestAudioNotReadyError:
    def test_error_code(self):
        err = AudioNotReadyError(recording_id=456)
        assert err.error_code == "AUDIO_NOT_READY"

    def test_http_status(self):
        err = AudioNotReadyError(recording_id=456)
        assert err.http_status_code == 409

    def test_custom_reason(self):
        err = AudioNotReadyError(recording_id=456, reason="Still processing")
        assert "Still processing" in err.message
        assert err.metadata["reason"] == "Still processing"


class TestCodeNotReadyError:
    def test_error_code(self):
        err = CodeNotReadyError(code_submission_id=789)
        assert err.error_code == "CODE_NOT_READY"

    def test_http_status(self):
        err = CodeNotReadyError(code_submission_id=789)
        assert err.http_status_code == 409

    def test_metadata(self):
        err = CodeNotReadyError(code_submission_id=789)
        assert err.metadata["code_submission_id"] == 789
