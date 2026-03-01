"""
Difficulty Adaptation Logic

Pure domain computation — no I/O, no DB calls.

Algorithm (from REQUIREMENTS):
  1. No previous score → use template default difficulty
  2. Score >= threshold_up → increase difficulty (max one jump)
  3. Score < threshold_down → decrease difficulty (max one jump)
  4. Score in range → maintain current difficulty
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from app.question.selection.contracts import (
    AdaptationDecision,
    DifficultyAdaptationConfig,
)

# ════════════════════════════════════════════════════════════════════════════
# Default constants
# ════════════════════════════════════════════════════════════════════════════

DEFAULT_DIFFICULTY_ORDER: List[str] = ["easy", "medium", "hard"]
RULE_VERSION = "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# Core adaptation functions
# ════════════════════════════════════════════════════════════════════════════


def increase_difficulty(
    current: str,
    max_jump: int = 1,
    order: Optional[List[str]] = None,
) -> str:
    """
    Increase difficulty by up to max_jump levels.

    Args:
        current: Current difficulty level.
        max_jump: Maximum levels to advance.
        order: Difficulty ordering (default: easy → medium → hard).

    Returns:
        New difficulty level (clamped to max).
    """
    order = order or DEFAULT_DIFFICULTY_ORDER
    current_lower = current.lower()

    if current_lower not in order:
        return current_lower

    idx = order.index(current_lower)
    new_idx = min(idx + max_jump, len(order) - 1)
    return order[new_idx]


def decrease_difficulty(
    current: str,
    max_jump: int = 1,
    order: Optional[List[str]] = None,
) -> str:
    """
    Decrease difficulty by up to max_jump levels.

    Args:
        current: Current difficulty level.
        max_jump: Maximum levels to regress.
        order: Difficulty ordering (default: easy → medium → hard).

    Returns:
        New difficulty level (clamped to min).
    """
    order = order or DEFAULT_DIFFICULTY_ORDER
    current_lower = current.lower()

    if current_lower not in order:
        return current_lower

    idx = order.index(current_lower)
    new_idx = max(idx - max_jump, 0)
    return order[new_idx]


def adapt_difficulty(
    previous_difficulty: Optional[str],
    previous_score: Optional[float],
    config: DifficultyAdaptationConfig,
) -> Tuple[str, str]:
    """
    Adapt difficulty based on previous performance.

    Args:
        previous_difficulty: Difficulty of previous exchange (None if first).
        previous_score: Score of previous exchange (0-100, None if first).
        config: Adaptation configuration.

    Returns:
        Tuple of (next_difficulty, adaptation_reason).
    """
    order = config.difficulty_order

    # No previous score → use template default (first in difficulty_range)
    if previous_score is None or previous_difficulty is None:
        default = order[0] if order else "medium"
        return (default, "first_question")

    prev_lower = previous_difficulty.lower()

    # Score above threshold → escalate
    if previous_score >= config.threshold_up:
        next_diff = increase_difficulty(
            prev_lower, config.max_difficulty_jump, order
        )
        changed = next_diff != prev_lower
        reason = (
            f"score_{previous_score:.1f}_above_threshold_{config.threshold_up}"
        )
        if not changed:
            reason += "_at_max"
        return (next_diff, reason)

    # Score below threshold → downgrade
    if previous_score < config.threshold_down:
        next_diff = decrease_difficulty(
            prev_lower, config.max_difficulty_jump, order
        )
        changed = next_diff != prev_lower
        reason = (
            f"score_{previous_score:.1f}_below_threshold_{config.threshold_down}"
        )
        if not changed:
            reason += "_at_min"
        return (next_diff, reason)

    # Score in range → maintain
    reason = f"score_{previous_score:.1f}_in_range"
    return (prev_lower, reason)


def build_adaptation_decision(
    submission_id: int,
    exchange_sequence_order: int,
    previous_difficulty: Optional[str],
    previous_score: Optional[float],
    previous_question_id: Optional[int],
    next_difficulty: str,
    adaptation_reason: str,
    config: DifficultyAdaptationConfig,
) -> AdaptationDecision:
    """
    Build an AdaptationDecision audit record.

    Pure factory function — no I/O.
    """
    prev_lower = previous_difficulty.lower() if previous_difficulty else None
    changed = prev_lower != next_difficulty if prev_lower else True

    # Determine rule name
    if previous_score is None or previous_difficulty is None:
        rule = "template_default"
    elif previous_score >= config.threshold_up:
        rule = "score_escalation"
    elif previous_score < config.threshold_down:
        rule = "score_downgrade"
    else:
        rule = "score_maintain"

    return AdaptationDecision(
        submission_id=submission_id,
        exchange_sequence_order=exchange_sequence_order,
        previous_difficulty=prev_lower,
        previous_score=previous_score,
        previous_question_id=previous_question_id,
        adaptation_rule=rule,
        threshold_up=config.threshold_up,
        threshold_down=config.threshold_down,
        max_difficulty_jump=config.max_difficulty_jump,
        next_difficulty=next_difficulty,
        adaptation_reason=adaptation_reason,
        difficulty_changed=changed,
        decided_at=datetime.utcnow(),
        rule_version=RULE_VERSION,
    )
