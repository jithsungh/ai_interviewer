"""
Unit Tests — Interview API Contracts

Tests Pydantic validation and DTO serialization:
  1. ExchangeItemDTO.from_model() — with and without responses
  2. ExchangeListResponse — structure, example data
  3. SectionProgressDTO — validation boundaries
  4. SectionProgressResponse — structure validation
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.interview.api.contracts import (
    ExchangeItemDTO,
    ExchangeListResponse,
    SectionProgressDTO,
    SectionProgressResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_exchange_model(**overrides):
    defaults = dict(
        id=789,
        sequence_order=1,
        question_text="Tell me about Python.",
        difficulty_at_time="medium",
        response_text="I have 5 years...",
        response_code=None,
        response_time_ms=45000,
        ai_followup_message=None,
        content_metadata={"question_type": "text", "section_name": "resume"},
        created_at=datetime(2026, 2, 14, 10, 5, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeItemDTO
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeItemDTO:
    def test_from_model_with_responses(self):
        model = _make_exchange_model()
        dto = ExchangeItemDTO.from_model(model, include_responses=True)

        assert dto.exchange_id == 789
        assert dto.sequence_order == 1
        assert dto.question_text == "Tell me about Python."
        assert dto.question_type == "text"
        assert dto.section_name == "resume"
        assert dto.difficulty_at_time == "medium"
        assert dto.response_text == "I have 5 years..."
        assert dto.response_time_ms == 45000

    def test_from_model_without_responses(self):
        model = _make_exchange_model()
        dto = ExchangeItemDTO.from_model(model, include_responses=False)

        assert dto.exchange_id == 789
        assert dto.question_text == "Tell me about Python."
        # Responses stripped
        assert dto.response_text is None
        assert dto.response_code is None
        assert dto.response_time_ms is None
        assert dto.ai_followup_message is None

    def test_from_model_coding_type(self):
        model = _make_exchange_model(
            response_text=None,
            response_code="def twoSum(nums, target): pass",
            content_metadata={
                "question_type": "coding",
                "section_name": "coding",
                "response_language": "python",
            },
        )
        dto = ExchangeItemDTO.from_model(model, include_responses=True)

        assert dto.question_type == "coding"
        assert dto.section_name == "coding"
        assert dto.response_code == "def twoSum(nums, target): pass"
        assert dto.response_language == "python"

    def test_from_model_no_metadata(self):
        model = _make_exchange_model(content_metadata=None)
        dto = ExchangeItemDTO.from_model(model)

        assert dto.question_type is None
        assert dto.section_name is None

    def test_from_model_empty_metadata(self):
        model = _make_exchange_model(content_metadata={})
        dto = ExchangeItemDTO.from_model(model)

        assert dto.question_type is None
        assert dto.section_name is None


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeListResponse
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeListResponse:
    def test_construction(self):
        dto = ExchangeItemDTO(
            exchange_id=1,
            sequence_order=1,
            question_text="Q1",
            difficulty_at_time="easy",
        )
        response = ExchangeListResponse(
            submission_id=123,
            exchanges=[dto],
            total_exchanges=1,
        )
        assert response.submission_id == 123
        assert len(response.exchanges) == 1
        assert response.total_exchanges == 1

    def test_empty_exchanges(self):
        response = ExchangeListResponse(
            submission_id=123,
            exchanges=[],
            total_exchanges=0,
        )
        assert response.total_exchanges == 0


# ═══════════════════════════════════════════════════════════════════════════
# SectionProgressDTO
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionProgressDTO:
    def test_valid_progress(self):
        dto = SectionProgressDTO(
            section_name="resume",
            questions_total=5,
            questions_answered=3,
            progress_percentage=60.0,
        )
        assert dto.section_name == "resume"
        assert dto.questions_answered == 3

    def test_zero_progress(self):
        dto = SectionProgressDTO(
            section_name="coding",
            questions_total=3,
            questions_answered=0,
            progress_percentage=0.0,
        )
        assert dto.progress_percentage == 0.0

    def test_full_progress(self):
        dto = SectionProgressDTO(
            section_name="behavioral",
            questions_total=2,
            questions_answered=2,
            progress_percentage=100.0,
        )
        assert dto.progress_percentage == 100.0

    def test_invalid_progress_over_100(self):
        with pytest.raises(Exception):
            SectionProgressDTO(
                section_name="test",
                questions_total=1,
                questions_answered=1,
                progress_percentage=101.0,
            )

    def test_invalid_progress_negative(self):
        with pytest.raises(Exception):
            SectionProgressDTO(
                section_name="test",
                questions_total=1,
                questions_answered=0,
                progress_percentage=-1.0,
            )


# ═══════════════════════════════════════════════════════════════════════════
# SectionProgressResponse
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionProgressResponse:
    def test_construction(self):
        sections = [
            SectionProgressDTO(
                section_name="resume",
                questions_total=2,
                questions_answered=2,
                progress_percentage=100.0,
            ),
            SectionProgressDTO(
                section_name="coding",
                questions_total=3,
                questions_answered=0,
                progress_percentage=0.0,
            ),
        ]
        response = SectionProgressResponse(
            submission_id=123,
            overall_progress=40.0,
            sections=sections,
        )
        assert response.submission_id == 123
        assert response.overall_progress == 40.0
        assert len(response.sections) == 2

    def test_empty_sections(self):
        response = SectionProgressResponse(
            submission_id=123,
            overall_progress=0.0,
            sections=[],
        )
        assert response.sections == []
