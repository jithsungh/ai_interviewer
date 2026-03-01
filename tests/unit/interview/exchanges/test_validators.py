"""
Unit Tests — Exchange Validators

Tests validate_sequence_order() and validate_response_completeness()
with pure domain logic (no DB, no mocks for validators themselves).
"""

from __future__ import annotations

import pytest

from app.interview.exchanges.contracts import ContentMetadata, ExchangeQuestionType
from app.interview.exchanges.errors import (
    DuplicateSequenceError,
    IncompleteResponseError,
    SequenceGapError,
)
from app.interview.exchanges.validators import (
    validate_response_completeness,
    validate_sequence_order,
)


# ═══════════════════════════════════════════════════════════════════════════
# validate_sequence_order
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateSequenceOrder:
    def test_first_exchange(self):
        """First exchange: proposed=1, count=0 → valid."""
        validate_sequence_order(
            submission_id=1,
            proposed_sequence=1,
            current_exchange_count=0,
        )

    def test_second_exchange(self):
        """Second exchange: proposed=2, count=1 → valid."""
        validate_sequence_order(
            submission_id=1,
            proposed_sequence=2,
            current_exchange_count=1,
        )

    def test_gap_detected(self):
        """Gap: proposed=3, count=1 (expected 2) → SequenceGapError."""
        with pytest.raises(SequenceGapError) as exc_info:
            validate_sequence_order(
                submission_id=1,
                proposed_sequence=3,
                current_exchange_count=1,
            )
        assert exc_info.value.metadata["expected_sequence"] == 2
        assert exc_info.value.metadata["proposed_sequence"] == 3

    def test_backward_gap(self):
        """Backward: proposed=1, count=3 (expected 4) → SequenceGapError."""
        with pytest.raises(SequenceGapError):
            validate_sequence_order(
                submission_id=1,
                proposed_sequence=1,
                current_exchange_count=3,
            )

    def test_duplicate_detected(self):
        """Duplicate: proposed=2 already in existing set → DuplicateSequenceError."""
        with pytest.raises(DuplicateSequenceError) as exc_info:
            validate_sequence_order(
                submission_id=1,
                proposed_sequence=2,
                current_exchange_count=1,
                existing_sequence_orders={1, 2},
            )
        assert exc_info.value.metadata["sequence_order"] == 2

    def test_no_existing_orders_skips_duplicate_check(self):
        """Without explicit set, only gap check runs."""
        validate_sequence_order(
            submission_id=1,
            proposed_sequence=1,
            current_exchange_count=0,
            existing_sequence_orders=None,
        )


# ═══════════════════════════════════════════════════════════════════════════
# validate_response_completeness — text questions
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateResponseCompletenessText:
    def test_valid_text_response(self):
        """Valid text: response_text present, response_time > 0."""
        validate_response_completeness({
            "response_text": "My answer is...",
            "response_time_ms": 10000,
            "content_metadata": {"question_type": "text"},
        })

    def test_missing_response_text(self):
        """Text question without response_text → IncompleteResponseError."""
        with pytest.raises(IncompleteResponseError, match="response_text required"):
            validate_response_completeness({
                "response_text": None,
                "response_time_ms": 10000,
                "content_metadata": {"question_type": "text"},
            })

    def test_empty_response_text(self):
        with pytest.raises(IncompleteResponseError, match="response_text required"):
            validate_response_completeness({
                "response_text": "",
                "response_time_ms": 10000,
                "content_metadata": {"question_type": "text"},
            })

    def test_zero_response_time(self):
        with pytest.raises(IncompleteResponseError, match="response_time_ms must be > 0"):
            validate_response_completeness({
                "response_text": "Answer",
                "response_time_ms": 0,
                "content_metadata": {"question_type": "text"},
            })

    def test_negative_response_time(self):
        with pytest.raises(IncompleteResponseError, match="response_time_ms must be > 0"):
            validate_response_completeness({
                "response_text": "Answer",
                "response_time_ms": -100,
                "content_metadata": {"question_type": "text"},
            })


# ═══════════════════════════════════════════════════════════════════════════
# validate_response_completeness — coding questions
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateResponseCompletenessCoding:
    def test_valid_coding_response(self):
        validate_response_completeness({
            "response_code": "def solve(): pass",
            "response_time_ms": 60000,
            "content_metadata": {
                "question_type": "coding",
                "code_submission_id": 42,
            },
        })

    def test_missing_response_code(self):
        with pytest.raises(IncompleteResponseError, match="response_code required"):
            validate_response_completeness({
                "response_code": None,
                "response_time_ms": 60000,
                "content_metadata": {
                    "question_type": "coding",
                    "code_submission_id": 42,
                },
            })

    def test_missing_code_submission_id(self):
        with pytest.raises(IncompleteResponseError, match="code_submission_id required"):
            validate_response_completeness({
                "response_code": "def solve(): pass",
                "response_time_ms": 60000,
                "content_metadata": {"question_type": "coding"},
            })


# ═══════════════════════════════════════════════════════════════════════════
# validate_response_completeness — audio questions
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateResponseCompletenessAudio:
    def test_valid_audio_response(self):
        validate_response_completeness({
            "response_text": "Transcribed text",
            "response_time_ms": 30000,
            "content_metadata": {
                "question_type": "audio",
                "audio_recording_id": 7,
            },
        })

    def test_missing_response_text_audio(self):
        with pytest.raises(IncompleteResponseError, match="response_text.*transcription"):
            validate_response_completeness({
                "response_text": None,
                "response_time_ms": 30000,
                "content_metadata": {
                    "question_type": "audio",
                    "audio_recording_id": 7,
                },
            })

    def test_missing_audio_recording_id(self):
        with pytest.raises(IncompleteResponseError, match="audio_recording_id required"):
            validate_response_completeness({
                "response_text": "Transcribed",
                "response_time_ms": 30000,
                "content_metadata": {"question_type": "audio"},
            })


# ═══════════════════════════════════════════════════════════════════════════
# validate_response_completeness — edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateResponseCompletenessEdgeCases:
    def test_unknown_question_type(self):
        with pytest.raises(IncompleteResponseError, match="Unknown question_type"):
            validate_response_completeness({
                "response_text": "Answer",
                "response_time_ms": 10000,
                "content_metadata": {"question_type": "video"},
            })

    def test_no_content_metadata(self):
        """Without content_metadata, only response_time is validated."""
        validate_response_completeness({
            "response_text": "Answer",
            "response_time_ms": 10000,
        })

    def test_no_question_type_in_metadata(self):
        """Missing question_type in metadata — only response_time validated."""
        validate_response_completeness({
            "response_text": "Answer",
            "response_time_ms": 10000,
            "content_metadata": {},
        })

    def test_pydantic_content_metadata(self):
        """Works with Pydantic ContentMetadata objects too."""
        meta = ContentMetadata(question_type=ExchangeQuestionType.TEXT)
        validate_response_completeness({
            "response_text": "Answer",
            "response_time_ms": 10000,
            "content_metadata": meta,
        })

    def test_none_response_time_allowed(self):
        """None response_time_ms is allowed (no check)."""
        validate_response_completeness({
            "response_text": "Answer",
            "response_time_ms": None,
            "content_metadata": {"question_type": "text"},
        })
