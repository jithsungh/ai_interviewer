"""
Unit Tests — Fallback Strategy Logic

Tests pure domain logic — no mocks, no I/O, no DB.

Covers:
  1. Fallback type mapping (attempt → type)
  2. Relaxed difficulties
  3. Similarity threshold relaxation
  4. Undefined attempt → None
"""

import pytest

from app.question.selection.contracts import FallbackType
from app.question.selection.domain.fallback import (
    MAX_FALLBACK_ATTEMPTS,
    FallbackLevel,
    get_fallback_type,
    get_relaxed_difficulties,
    should_relax_similarity,
)


# ═══════════════════════════════════════════════════════════════════════
# get_fallback_type
# ═══════════════════════════════════════════════════════════════════════


class TestGetFallbackType:
    """Tests for get_fallback_type()."""

    def test_attempt_0_relaxed_difficulty(self):
        assert get_fallback_type(0) == FallbackType.RELAXED_DIFFICULTY

    def test_attempt_1_relaxed_topic(self):
        assert get_fallback_type(1) == FallbackType.RELAXED_TOPIC

    def test_attempt_2_relaxed_similarity(self):
        assert get_fallback_type(2) == FallbackType.RELAXED_SIMILARITY

    def test_attempt_3_generation(self):
        assert get_fallback_type(3) == FallbackType.LLM_GENERATION

    def test_attempt_4_generic(self):
        assert get_fallback_type(4) == FallbackType.GENERIC_FALLBACK

    def test_attempt_5_none(self):
        """Beyond max → None."""
        assert get_fallback_type(5) is None

    def test_negative_attempt_none(self):
        assert get_fallback_type(-1) is None


# ═══════════════════════════════════════════════════════════════════════
# get_relaxed_difficulties
# ═══════════════════════════════════════════════════════════════════════


class TestGetRelaxedDifficulties:
    """Tests for get_relaxed_difficulties()."""

    def test_returns_all_difficulties(self):
        result = get_relaxed_difficulties("medium")
        assert result == ["easy", "medium", "hard"]

    def test_custom_order(self):
        result = get_relaxed_difficulties(
            "b", difficulty_order=["a", "b", "c"]
        )
        assert result == ["a", "b", "c"]

    def test_default_order_regardless_of_input(self):
        """Always returns full order."""
        result = get_relaxed_difficulties("easy")
        assert len(result) == 3


# ═══════════════════════════════════════════════════════════════════════
# should_relax_similarity
# ═══════════════════════════════════════════════════════════════════════


class TestShouldRelaxSimilarity:
    """Tests for should_relax_similarity()."""

    def test_before_relax_level(self):
        """Before RELAX_SIMILARITY level → original threshold."""
        threshold = should_relax_similarity(
            attempt=0, original_threshold=0.85, relaxed_threshold=0.90
        )
        assert threshold == 0.85

    def test_at_relax_level(self):
        """At RELAX_SIMILARITY level → relaxed threshold."""
        threshold = should_relax_similarity(
            attempt=2, original_threshold=0.85, relaxed_threshold=0.90
        )
        assert threshold == 0.90

    def test_beyond_relax_level(self):
        """Beyond RELAX_SIMILARITY level → still relaxed."""
        threshold = should_relax_similarity(
            attempt=4, original_threshold=0.85, relaxed_threshold=0.90
        )
        assert threshold == 0.90


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackConstants:
    """Tests for fallback constants."""

    def test_max_attempts(self):
        assert MAX_FALLBACK_ATTEMPTS == 5

    def test_fallback_levels_ordered(self):
        assert FallbackLevel.RELAX_DIFFICULTY < FallbackLevel.RELAX_TOPIC
        assert FallbackLevel.RELAX_TOPIC < FallbackLevel.RELAX_SIMILARITY
        assert FallbackLevel.RELAX_SIMILARITY < FallbackLevel.LLM_GENERATION
        assert FallbackLevel.LLM_GENERATION < FallbackLevel.GENERIC_FALLBACK
