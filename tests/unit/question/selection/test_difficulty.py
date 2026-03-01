"""
Unit Tests — Difficulty Adaptation Logic

Tests pure domain logic — no mocks, no I/O, no DB.

Covers:
  1. Score above threshold → escalate
  2. Score below threshold → downgrade
  3. Score in range → maintain
  4. Max jump constraint
  5. Already at max/min → clamped
  6. First question → template default
  7. Edge cases: exact threshold, None inputs
"""

import pytest
from datetime import datetime

from app.question.selection.contracts import DifficultyAdaptationConfig
from app.question.selection.domain.difficulty import (
    RULE_VERSION,
    adapt_difficulty,
    build_adaptation_decision,
    decrease_difficulty,
    increase_difficulty,
)


# ═══════════════════════════════════════════════════════════════════════
# increase_difficulty
# ═══════════════════════════════════════════════════════════════════════


class TestIncreaseDifficulty:
    """Tests for increase_difficulty()."""

    def test_easy_to_medium(self):
        assert increase_difficulty("easy", max_jump=1) == "medium"

    def test_medium_to_hard(self):
        assert increase_difficulty("medium", max_jump=1) == "hard"

    def test_hard_stays_hard(self):
        """Already at max → clamped."""
        assert increase_difficulty("hard", max_jump=1) == "hard"

    def test_easy_to_hard_jump_2(self):
        """max_jump=2 allows skipping medium."""
        assert increase_difficulty("easy", max_jump=2) == "hard"

    def test_medium_to_hard_jump_2(self):
        """max_jump=2 from medium → hard (clamped)."""
        assert increase_difficulty("medium", max_jump=2) == "hard"

    def test_unknown_difficulty_unchanged(self):
        """Unknown difficulty → returned as-is."""
        assert increase_difficulty("extreme", max_jump=1) == "extreme"

    def test_custom_order(self):
        order = ["beginner", "intermediate", "advanced", "expert"]
        assert increase_difficulty("beginner", max_jump=1, order=order) == "intermediate"
        assert increase_difficulty("advanced", max_jump=1, order=order) == "expert"
        assert increase_difficulty("expert", max_jump=1, order=order) == "expert"


# ═══════════════════════════════════════════════════════════════════════
# decrease_difficulty
# ═══════════════════════════════════════════════════════════════════════


class TestDecreaseDifficulty:
    """Tests for decrease_difficulty()."""

    def test_hard_to_medium(self):
        assert decrease_difficulty("hard", max_jump=1) == "medium"

    def test_medium_to_easy(self):
        assert decrease_difficulty("medium", max_jump=1) == "easy"

    def test_easy_stays_easy(self):
        """Already at min → clamped."""
        assert decrease_difficulty("easy", max_jump=1) == "easy"

    def test_hard_to_easy_jump_2(self):
        """max_jump=2 allows skipping medium."""
        assert decrease_difficulty("hard", max_jump=2) == "easy"

    def test_unknown_difficulty_unchanged(self):
        assert decrease_difficulty("extreme", max_jump=1) == "extreme"


# ═══════════════════════════════════════════════════════════════════════
# adapt_difficulty
# ═══════════════════════════════════════════════════════════════════════


class TestAdaptDifficulty:
    """Tests for adapt_difficulty() — core adaptation algorithm."""

    @pytest.fixture
    def default_config(self) -> DifficultyAdaptationConfig:
        return DifficultyAdaptationConfig(
            threshold_up=80.0,
            threshold_down=50.0,
            max_difficulty_jump=1,
        )

    # Escalation tests

    def test_score_above_threshold_escalates(self, default_config):
        """Score 85 (>= 80) → easy → medium."""
        diff, reason = adapt_difficulty("easy", 85.0, default_config)
        assert diff == "medium"
        assert "above_threshold" in reason

    def test_score_at_exact_threshold_escalates(self, default_config):
        """Score exactly at threshold_up → treated as escalation."""
        diff, reason = adapt_difficulty("easy", 80.0, default_config)
        assert diff == "medium"
        assert "above_threshold" in reason

    def test_escalation_at_max_stays(self, default_config):
        """Score 95 on hard → stays hard, reason includes 'at_max'."""
        diff, reason = adapt_difficulty("hard", 95.0, default_config)
        assert diff == "hard"
        assert "at_max" in reason

    def test_escalation_respects_max_jump(self):
        """max_jump=1: easy with score 95 → medium (not hard)."""
        config = DifficultyAdaptationConfig(
            threshold_up=80.0, max_difficulty_jump=1
        )
        diff, _ = adapt_difficulty("easy", 95.0, config)
        assert diff == "medium"

    def test_escalation_with_jump_2(self):
        """max_jump=2: easy with score 95 → hard."""
        config = DifficultyAdaptationConfig(
            threshold_up=80.0, max_difficulty_jump=2
        )
        diff, _ = adapt_difficulty("easy", 95.0, config)
        assert diff == "hard"

    # Downgrade tests

    def test_score_below_threshold_downgrades(self, default_config):
        """Score 45 (< 50) → hard → medium."""
        diff, reason = adapt_difficulty("hard", 45.0, default_config)
        assert diff == "medium"
        assert "below_threshold" in reason

    def test_downgrade_at_min_stays(self, default_config):
        """Score 30 on easy → stays easy, reason includes 'at_min'."""
        diff, reason = adapt_difficulty("easy", 30.0, default_config)
        assert diff == "easy"
        assert "at_min" in reason

    def test_score_just_below_threshold_downgrades(self, default_config):
        """Score 49.9 (< 50) → downgrade."""
        diff, reason = adapt_difficulty("medium", 49.9, default_config)
        assert diff == "easy"
        assert "below_threshold" in reason

    # Maintain tests

    def test_score_in_range_maintains(self, default_config):
        """Score 65 (50 <= 65 < 80) → maintain medium."""
        diff, reason = adapt_difficulty("medium", 65.0, default_config)
        assert diff == "medium"
        assert "in_range" in reason

    def test_score_at_lower_bound_maintains(self, default_config):
        """Score exactly at threshold_down → NOT downgraded (>=)."""
        diff, reason = adapt_difficulty("medium", 50.0, default_config)
        assert diff == "medium"
        assert "in_range" in reason

    def test_score_just_below_upper_bound_maintains(self, default_config):
        """Score 79.9 → maintain."""
        diff, reason = adapt_difficulty("medium", 79.9, default_config)
        assert diff == "medium"
        assert "in_range" in reason

    # First question (None inputs)

    def test_no_previous_score_uses_default(self, default_config):
        """No previous score → template default (first in order)."""
        diff, reason = adapt_difficulty(None, None, default_config)
        assert diff == "easy"  # First in default order
        assert reason == "first_question"

    def test_no_previous_difficulty_uses_default(self, default_config):
        """None difficulty → template default."""
        diff, reason = adapt_difficulty(None, 75.0, default_config)
        assert diff == "easy"
        assert reason == "first_question"

    def test_previous_difficulty_no_score(self, default_config):
        """Has difficulty but no score → template default."""
        diff, reason = adapt_difficulty("medium", None, default_config)
        assert diff == "easy"
        assert reason == "first_question"

    # Case insensitivity

    def test_case_insensitive_difficulty(self, default_config):
        """Difficulty strings normalized to lowercase."""
        diff, reason = adapt_difficulty("EASY", 85.0, default_config)
        assert diff == "medium"

    def test_mixed_case_medium(self, default_config):
        diff, reason = adapt_difficulty("Medium", 45.0, default_config)
        assert diff == "easy"

    # Boundary/edge cases

    def test_score_zero_downgrades(self, default_config):
        """Score 0.0 → downgrade."""
        diff, _ = adapt_difficulty("hard", 0.0, default_config)
        assert diff == "medium"

    def test_score_100_escalates(self, default_config):
        """Score 100.0 → escalate."""
        diff, _ = adapt_difficulty("easy", 100.0, default_config)
        assert diff == "medium"


# ═══════════════════════════════════════════════════════════════════════
# build_adaptation_decision
# ═══════════════════════════════════════════════════════════════════════


class TestBuildAdaptationDecision:
    """Tests for build_adaptation_decision() factory."""

    def test_escalation_decision(self):
        config = DifficultyAdaptationConfig(threshold_up=80.0, threshold_down=50.0)
        decision = build_adaptation_decision(
            submission_id=1,
            exchange_sequence_order=3,
            previous_difficulty="easy",
            previous_score=85.0,
            previous_question_id=42,
            next_difficulty="medium",
            adaptation_reason="score_85.0_above_threshold_80.0",
            config=config,
        )
        assert decision.submission_id == 1
        assert decision.exchange_sequence_order == 3
        assert decision.previous_difficulty == "easy"
        assert decision.next_difficulty == "medium"
        assert decision.difficulty_changed is True
        assert decision.adaptation_rule == "score_escalation"
        assert decision.rule_version == RULE_VERSION
        assert isinstance(decision.decided_at, datetime)

    def test_maintain_decision(self):
        config = DifficultyAdaptationConfig(threshold_up=80.0, threshold_down=50.0)
        decision = build_adaptation_decision(
            submission_id=1,
            exchange_sequence_order=2,
            previous_difficulty="medium",
            previous_score=65.0,
            previous_question_id=10,
            next_difficulty="medium",
            adaptation_reason="score_65.0_in_range",
            config=config,
        )
        assert decision.difficulty_changed is False
        assert decision.adaptation_rule == "score_maintain"

    def test_first_question_decision(self):
        config = DifficultyAdaptationConfig()
        decision = build_adaptation_decision(
            submission_id=1,
            exchange_sequence_order=1,
            previous_difficulty=None,
            previous_score=None,
            previous_question_id=None,
            next_difficulty="easy",
            adaptation_reason="first_question",
            config=config,
        )
        assert decision.adaptation_rule == "template_default"
        assert decision.difficulty_changed is True  # None → easy = changed

    def test_downgrade_decision(self):
        config = DifficultyAdaptationConfig(threshold_up=80.0, threshold_down=50.0)
        decision = build_adaptation_decision(
            submission_id=5,
            exchange_sequence_order=4,
            previous_difficulty="hard",
            previous_score=35.0,
            previous_question_id=99,
            next_difficulty="medium",
            adaptation_reason="score_35.0_below_threshold_50.0",
            config=config,
        )
        assert decision.difficulty_changed is True
        assert decision.adaptation_rule == "score_downgrade"
