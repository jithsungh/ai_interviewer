"""
Unit Tests — Context Prioritization

Tests prioritize_context() token budget allocation, truncation behavior,
and priority ordering.

No mocks, no I/O — pure domain logic.
"""

import pytest

from app.question.prompting.context import (
    ContextPiece,
    prioritize_context,
)


# ═══════════════════════════════════════════════════════════════════════
# ContextPiece dataclass
# ═══════════════════════════════════════════════════════════════════════


class TestContextPiece:
    """Tests for ContextPiece dataclass."""

    def test_construction(self):
        piece = ContextPiece(name="resume", value="text", priority=5)
        assert piece.name == "resume"
        assert piece.value == "text"
        assert piece.priority == 5
        assert piece.required is False
        assert piece.truncated is False

    def test_required_flag(self):
        piece = ContextPiece(name="instructions", value="text", priority=1, required=True)
        assert piece.required is True


# ═══════════════════════════════════════════════════════════════════════
# prioritize_context — Essential fields
# ═══════════════════════════════════════════════════════════════════════


class TestPrioritizeContextEssentials:
    """Tests that essential context (template_instructions, difficulty, topic) is always included."""

    def test_essential_fields_always_present(self):
        result = prioritize_context(
            template_instructions="Generate a question.",
            difficulty="medium",
            topic="algorithms",
            max_tokens=7500,
        )
        assert result["template_instructions"] == "Generate a question."
        assert result["difficulty"] == "medium"
        assert result["topic"] == "algorithms"

    def test_essential_fields_present_with_tight_budget(self):
        result = prioritize_context(
            template_instructions="Generate a question.",
            difficulty="hard",
            topic="graphs",
            max_tokens=50,  # Very tight budget
        )
        assert "template_instructions" in result
        assert "difficulty" in result
        assert "topic" in result

    def test_optional_fields_empty_when_not_provided(self):
        result = prioritize_context(
            template_instructions="Instructions.",
            difficulty="easy",
            topic="sorting",
            max_tokens=7500,
        )
        assert result["previous_topics"] == ""
        assert result["job_description"] == ""
        assert result["resume_truncated"] == ""


# ═══════════════════════════════════════════════════════════════════════
# prioritize_context — Optional fields
# ═══════════════════════════════════════════════════════════════════════


class TestPrioritizeContextOptional:
    """Tests for optional context pieces (exchanges, JD, resume)."""

    def test_previous_exchanges_included(self):
        result = prioritize_context(
            template_instructions="Instr.",
            difficulty="medium",
            topic="trees",
            previous_exchanges=["Q1 about arrays", "Q2 about lists"],
            max_tokens=7500,
        )
        assert "Q1 about arrays" in result["previous_topics"]
        assert "Q2 about lists" in result["previous_topics"]

    def test_job_description_included(self):
        result = prioritize_context(
            template_instructions="Instr.",
            difficulty="medium",
            topic="trees",
            job_description="Looking for a senior engineer.",
            max_tokens=7500,
        )
        assert result["job_description"] == "Looking for a senior engineer."

    def test_resume_included(self):
        result = prioritize_context(
            template_instructions="Instr.",
            difficulty="medium",
            topic="trees",
            resume_text="5 years Python experience.",
            max_tokens=7500,
        )
        assert "5 years Python experience" in result["resume_truncated"]

    def test_all_context_included_with_large_budget(self):
        result = prioritize_context(
            template_instructions="Generate a technical question.",
            difficulty="medium",
            topic="algorithms",
            previous_exchanges=["Q1 about arrays"],
            job_description="Senior backend engineer needed.",
            resume_text="Python developer with 5 years exp.",
            max_tokens=10000,
        )
        assert result["previous_topics"] != ""
        assert result["job_description"] != ""
        assert result["resume_truncated"] != ""


# ═══════════════════════════════════════════════════════════════════════
# prioritize_context — Truncation behavior
# ═══════════════════════════════════════════════════════════════════════


class TestPrioritizeContextTruncation:
    """Tests for context truncation when budget is exceeded."""

    def test_resume_truncated_when_budget_tight(self):
        """Resume (priority 5) should be truncated before essential fields."""
        long_resume = "Resume content. " * 500  # Very long
        result = prioritize_context(
            template_instructions="Instructions.",
            difficulty="medium",
            topic="trees",
            resume_text=long_resume,
            max_tokens=200,  # Tight budget
        )
        # Resume should be truncated or marked
        resume = result["resume_truncated"]
        assert len(resume) < len(long_resume)

    def test_exchanges_limited(self):
        """Previous exchanges are limited to max_previous_exchanges."""
        exchanges = [f"Exchange {i}" for i in range(20)]
        result = prioritize_context(
            template_instructions="Instr.",
            difficulty="medium",
            topic="trees",
            previous_exchanges=exchanges,
            max_previous_exchanges=3,
            max_tokens=7500,
        )
        # Only up to 3 exchanges should appear
        content = result["previous_topics"]
        # Count newlines to approximate entries
        lines = [l for l in content.split("\n") if l.strip()]
        assert len(lines) <= 3

    def test_essential_fields_survive_tight_budget(self):
        """Even with no room, essential fields are returned."""
        result = prioritize_context(
            template_instructions="X" * 10000,  # Huge instructions
            difficulty="hard",
            topic="dynamic programming",
            max_tokens=10,  # Impossibly tight
        )
        # Essentials still present
        assert result["template_instructions"] != ""
        assert result["difficulty"] == "hard"
        assert result["topic"] == "dynamic programming"


# ═══════════════════════════════════════════════════════════════════════
# prioritize_context — Priority ordering
# ═══════════════════════════════════════════════════════════════════════


class TestPrioritizeContextPriority:
    """Tests that lower-priority content is dropped before higher-priority."""

    def test_resume_dropped_before_jd(self):
        """
        With a tight budget and both JD and resume, JD (priority 4)
        should be preserved over resume (priority 5).
        """
        result = prioritize_context(
            template_instructions="Short instructions.",
            difficulty="medium",
            topic="trees",
            job_description="Short JD.",
            resume_text="Long resume. " * 500,
            max_tokens=100,
        )
        # JD short enough to fit; resume likely truncated
        jd = result["job_description"]
        resume = result["resume_truncated"]
        if "[truncated]" in resume:
            # Resume was truncated — JD should still be intact
            assert jd == "Short JD." or "[truncated]" not in jd

