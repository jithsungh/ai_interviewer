"""
Unit Tests — Generation Contracts (DTOs)

Tests Pydantic validation on GenerationRequest and GenerationResult.
Pure validation logic — no mocks needed.
"""

import pytest
from pydantic import ValidationError

from app.question.generation.contracts import (
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
)


# ════════════════════════════════════════════════════════════════════════════
# GenerationRequest
# ════════════════════════════════════════════════════════════════════════════


class TestGenerationRequest:

    def test_minimal_valid_request(self):
        req = GenerationRequest(
            submission_id=1,
            organization_id=42,
            difficulty="medium",
            topic="algorithms",
        )
        assert req.difficulty == "medium"
        assert req.question_type == "technical"  # default
        assert req.max_retries == 3

    def test_difficulty_normalised_lowercase(self):
        req = GenerationRequest(
            submission_id=1,
            organization_id=1,
            difficulty="HARD",
            topic="x",
        )
        assert req.difficulty == "hard"

    def test_invalid_difficulty_rejected(self):
        with pytest.raises(ValidationError, match="difficulty"):
            GenerationRequest(
                submission_id=1,
                organization_id=1,
                difficulty="extreme",
                topic="x",
            )

    def test_invalid_question_type_rejected(self):
        with pytest.raises(ValidationError, match="question_type"):
            GenerationRequest(
                submission_id=1,
                organization_id=1,
                difficulty="easy",
                topic="x",
                question_type="essay",
            )

    def test_zero_submission_id_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequest(
                submission_id=0,
                organization_id=1,
                difficulty="easy",
                topic="x",
            )

    def test_empty_topic_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequest(
                submission_id=1,
                organization_id=1,
                difficulty="easy",
                topic="",
            )

    def test_similarity_threshold_range(self):
        with pytest.raises(ValidationError):
            GenerationRequest(
                submission_id=1,
                organization_id=1,
                difficulty="easy",
                topic="x",
                similarity_threshold=1.5,
            )

    def test_max_retries_range(self):
        with pytest.raises(ValidationError):
            GenerationRequest(
                submission_id=1,
                organization_id=1,
                difficulty="easy",
                topic="x",
                max_retries=10,
            )

    def test_full_request_with_context(self):
        req = GenerationRequest(
            submission_id=5,
            organization_id=42,
            difficulty="medium",
            topic="data_structures",
            subtopic="binary trees",
            question_type="technical",
            resume_text="Python developer with 5 years experience.",
            job_description="Backend role requiring Python, SQL.",
            previous_questions=["What is a linked list?"],
            last_score_percent=72.5,
            performance_trend="improving",
            exchange_number=3,
            total_exchanges=8,
            remaining_time_minutes=20,
        )
        assert req.subtopic == "binary trees"
        assert len(req.previous_questions) == 1


# ════════════════════════════════════════════════════════════════════════════
# GenerationResult
# ════════════════════════════════════════════════════════════════════════════


class TestGenerationResult:

    def test_success_result(self):
        result = GenerationResult(
            status=GenerationStatus.SUCCESS,
            question_text="What is a hash table?",
            difficulty="medium",
            topic="data_structures",
        )
        assert result.is_success is True
        assert result.is_fallback is False

    def test_fallback_result(self):
        result = GenerationResult(
            status=GenerationStatus.FALLBACK_USED,
            question_text="Generic question.",
            source_type="fallback_generic",
            fallback_question_id=99,
            fallback_reason="max_retries_exhausted",
        )
        assert result.is_success is False
        assert result.is_fallback is True

    def test_no_fallback_result(self):
        result = GenerationResult(
            status=GenerationStatus.NO_FALLBACK,
            source_type="none",
        )
        assert result.is_success is False
        assert result.is_fallback is False

    def test_generated_at_auto_populated(self):
        result = GenerationResult(status=GenerationStatus.SUCCESS, question_text="X")
        assert result.generated_at is not None
