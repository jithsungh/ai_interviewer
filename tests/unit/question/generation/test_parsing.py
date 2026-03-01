"""
Unit Tests — LLM Response Parsing

Tests parse_llm_response() against valid, invalid, and edge-case inputs.
Pure domain logic — no mocks needed.
"""

import pytest

from app.question.generation.domain.parsing import (
    ResponseParseError,
    parse_llm_response,
)
from app.question.generation.domain.entities import GeneratedQuestionOutput


# ════════════════════════════════════════════════════════════════════════════
# Valid responses
# ════════════════════════════════════════════════════════════════════════════


class TestValidParsing:
    """Tests for valid LLM JSON responses."""

    def test_minimal_valid_response(self):
        raw = '{"question_text": "What is a binary tree?", "difficulty": "easy"}'
        output = parse_llm_response(raw)

        assert isinstance(output, GeneratedQuestionOutput)
        assert output.question_text == "What is a binary tree?"
        assert output.difficulty == "easy"
        assert output.expected_answer == ""
        assert output.estimated_time_seconds == 120  # default

    def test_full_response_with_all_fields(self):
        raw = """{
            "question_text": "Explain the CAP theorem and its trade-offs.",
            "expected_answer_outline": "Consistency, Availability, Partition tolerance. Pick two.",
            "difficulty": "hard",
            "topic": "distributed_systems",
            "subtopic": "consistency models",
            "skill_tags": ["system design", "distributed systems"],
            "expected_answer_type": "conceptual",
            "estimated_answer_minutes": 5,
            "followup_suggestions": ["Give a real-world example.", "How does Spanner differ?"]
        }"""
        output = parse_llm_response(raw)

        assert output.question_text == "Explain the CAP theorem and its trade-offs."
        assert output.expected_answer == "Consistency, Availability, Partition tolerance. Pick two."
        assert output.difficulty == "hard"
        assert output.topic == "distributed_systems"
        assert output.subtopic == "consistency models"
        assert output.skill_tags == ["system design", "distributed systems"]
        assert output.expected_answer_type == "conceptual"
        assert output.estimated_time_seconds == 300  # 5 min * 60
        assert len(output.followup_suggestions) == 2

    def test_difficulty_normalised_to_lowercase(self):
        raw = '{"question_text": "What is a stack?", "difficulty": "MEDIUM"}'
        output = parse_llm_response(raw)
        assert output.difficulty == "medium"

    def test_markdown_fences_stripped(self):
        raw = '```json\n{"question_text": "What is REST?", "difficulty": "easy"}\n```'
        output = parse_llm_response(raw)
        assert output.question_text == "What is REST?"

    def test_estimated_time_clamped(self):
        raw = '{"question_text": "Explain Docker.", "difficulty": "easy", "estimated_time_seconds": 5}'
        output = parse_llm_response(raw)
        assert output.estimated_time_seconds == 30  # clamped min

    def test_estimated_time_max_clamped(self):
        raw = '{"question_text": "Explain Docker.", "difficulty": "easy", "estimated_time_seconds": 99999}'
        output = parse_llm_response(raw)
        assert output.estimated_time_seconds == 900  # clamped max

    def test_expected_answer_field_fallback(self):
        """Both expected_answer and expected_answer_outline accepted."""
        raw = '{"question_text": "What is OOP?", "difficulty": "easy", "expected_answer": "Encapsulation, inheritance, polymorphism."}'
        output = parse_llm_response(raw)
        assert output.expected_answer == "Encapsulation, inheritance, polymorphism."

    def test_invalid_answer_type_ignored(self):
        raw = '{"question_text": "What is X?", "difficulty": "easy", "expected_answer_type": "unknown_type"}'
        output = parse_llm_response(raw)
        assert output.expected_answer_type is None

    def test_non_list_skill_tags_normalised(self):
        raw = '{"question_text": "What is X?", "difficulty": "easy", "skill_tags": "not a list"}'
        output = parse_llm_response(raw)
        assert output.skill_tags == []


# ════════════════════════════════════════════════════════════════════════════
# Invalid responses
# ════════════════════════════════════════════════════════════════════════════


class TestInvalidParsing:
    """Tests for LLM responses that should raise ResponseParseError."""

    def test_empty_string(self):
        with pytest.raises(ResponseParseError, match="empty"):
            parse_llm_response("")

    def test_whitespace_only(self):
        with pytest.raises(ResponseParseError, match="empty"):
            parse_llm_response("   \n  ")

    def test_invalid_json(self):
        with pytest.raises(ResponseParseError, match="Invalid JSON"):
            parse_llm_response("This is not JSON at all.")

    def test_missing_question_text(self):
        with pytest.raises(ResponseParseError, match="question_text"):
            parse_llm_response('{"difficulty": "easy"}')

    def test_missing_difficulty(self):
        with pytest.raises(ResponseParseError, match="difficulty"):
            parse_llm_response('{"question_text": "What is X?"}')

    def test_invalid_difficulty_value(self):
        with pytest.raises(ResponseParseError, match="difficulty must be"):
            parse_llm_response('{"question_text": "What is X?", "difficulty": "extreme"}')

    def test_wrong_type_question_text(self):
        with pytest.raises(ResponseParseError, match="must be str"):
            parse_llm_response('{"question_text": 42, "difficulty": "easy"}')

    def test_wrong_type_difficulty(self):
        with pytest.raises(ResponseParseError, match="must be str"):
            parse_llm_response('{"question_text": "What?", "difficulty": 2}')
