"""
Unit Tests — Exchange Contracts (Pydantic DTOs)

Tests ExchangeCreationData, ContentMetadata, and ExchangeQuestionType validation.
"""

from __future__ import annotations

import pytest

from app.interview.exchanges.contracts import (
    ContentMetadata,
    ExchangeCreationData,
    ExchangeQuestionType,
)


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeQuestionType enum
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeQuestionType:
    def test_all_values(self):
        values = {e.value for e in ExchangeQuestionType}
        assert values == {"text", "coding", "audio"}

    def test_string_coercion(self):
        assert ExchangeQuestionType("text") is ExchangeQuestionType.TEXT
        assert ExchangeQuestionType("coding") is ExchangeQuestionType.CODING
        assert ExchangeQuestionType("audio") is ExchangeQuestionType.AUDIO

    def test_invalid(self):
        with pytest.raises(ValueError):
            ExchangeQuestionType("video")


# ═══════════════════════════════════════════════════════════════════════════
# ContentMetadata
# ═══════════════════════════════════════════════════════════════════════════


class TestContentMetadata:
    def test_minimal(self):
        meta = ContentMetadata(question_type=ExchangeQuestionType.TEXT)
        assert meta.question_type == ExchangeQuestionType.TEXT
        assert meta.section_name is None
        assert meta.clarification_count == 0
        assert meta.clarification_limit_exceeded is False
        assert meta.intent_sequence == []

    def test_full(self):
        meta = ContentMetadata(
            question_type=ExchangeQuestionType.CODING,
            section_name="coding",
            response_language="python",
            code_submission_id=42,
            clarification_count=2,
            clarification_limit_exceeded=False,
            intent_sequence=[{"intent": "ANSWER", "confidence": 0.9}],
            final_intent="ANSWER",
            final_intent_confidence=0.9,
        )
        assert meta.response_language == "python"
        assert meta.code_submission_id == 42

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            ContentMetadata(
                question_type=ExchangeQuestionType.TEXT,
                final_intent_confidence=1.5,
            )

    def test_serialization_roundtrip(self):
        meta = ContentMetadata(
            question_type=ExchangeQuestionType.TEXT,
            section_name="behavioral",
        )
        data = meta.model_dump(mode="json")
        restored = ContentMetadata.model_validate(data)
        assert restored.question_type == ExchangeQuestionType.TEXT
        assert restored.section_name == "behavioral"


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeCreationData
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeCreationData:
    def test_valid_text_exchange(self):
        data = ExchangeCreationData(
            submission_id=1,
            sequence_order=1,
            question_id=101,
            question_text="What is polymorphism?",
            difficulty_at_time="medium",
            response_text="Polymorphism is...",
            response_time_ms=45000,
            content_metadata=ContentMetadata(
                question_type=ExchangeQuestionType.TEXT,
                section_name="technical",
            ),
        )
        assert data.submission_id == 1
        assert data.sequence_order == 1
        assert data.question_text == "What is polymorphism?"

    def test_valid_coding_exchange(self):
        data = ExchangeCreationData(
            submission_id=1,
            sequence_order=2,
            coding_problem_id=50,
            question_text="Implement binary search",
            difficulty_at_time="hard",
            response_code="def binary_search(arr, target): ...",
            response_time_ms=120000,
            content_metadata=ContentMetadata(
                question_type=ExchangeQuestionType.CODING,
                section_name="coding",
                response_language="python",
                code_submission_id=99,
            ),
        )
        assert data.coding_problem_id == 50

    def test_requires_question_or_problem(self):
        """At least one of question_id or coding_problem_id required."""
        with pytest.raises(ValueError, match="question_id or coding_problem_id"):
            ExchangeCreationData(
                submission_id=1,
                sequence_order=1,
                question_text="Test",
                difficulty_at_time="easy",
            )

    def test_invalid_difficulty(self):
        with pytest.raises(ValueError, match="difficulty_at_time"):
            ExchangeCreationData(
                submission_id=1,
                sequence_order=1,
                question_id=1,
                question_text="Test",
                difficulty_at_time="impossible",
            )

    def test_submission_id_positive(self):
        with pytest.raises(Exception):
            ExchangeCreationData(
                submission_id=0,
                sequence_order=1,
                question_id=1,
                question_text="Test",
                difficulty_at_time="easy",
            )

    def test_sequence_order_positive(self):
        with pytest.raises(Exception):
            ExchangeCreationData(
                submission_id=1,
                sequence_order=0,
                question_id=1,
                question_text="Test",
                difficulty_at_time="easy",
            )

    def test_empty_question_text_rejected(self):
        with pytest.raises(Exception):
            ExchangeCreationData(
                submission_id=1,
                sequence_order=1,
                question_id=1,
                question_text="",
                difficulty_at_time="easy",
            )

    def test_response_time_non_negative(self):
        """response_time_ms must be >= 0."""
        with pytest.raises(Exception):
            ExchangeCreationData(
                submission_id=1,
                sequence_order=1,
                question_id=1,
                question_text="Test",
                difficulty_at_time="easy",
                response_time_ms=-1,
            )
