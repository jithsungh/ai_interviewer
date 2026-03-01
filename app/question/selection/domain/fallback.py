"""
Fallback Strategy Logic

Determines which fallback to try when primary selection fails.
Pure domain logic — no I/O (actual I/O is in the service layer).
"""

from __future__ import annotations

from enum import IntEnum
from typing import List, Optional

from app.question.selection.contracts import FallbackType


class FallbackLevel(IntEnum):
    """Ordered fallback levels (0 = first attempt)."""

    RELAX_DIFFICULTY = 0
    RELAX_TOPIC = 1
    RELAX_SIMILARITY = 2
    LLM_GENERATION = 3
    GENERIC_FALLBACK = 4


MAX_FALLBACK_ATTEMPTS = 5


def get_fallback_type(attempt: int) -> Optional[FallbackType]:
    """
    Determine which fallback strategy to use for a given attempt number.

    Args:
        attempt: Zero-based fallback attempt index.

    Returns:
        FallbackType or None if all fallbacks exhausted.
    """
    mapping = {
        0: FallbackType.RELAXED_DIFFICULTY,
        1: FallbackType.RELAXED_TOPIC,
        2: FallbackType.RELAXED_SIMILARITY,
        3: FallbackType.LLM_GENERATION,
        4: FallbackType.GENERIC_FALLBACK,
    }
    return mapping.get(attempt)


def get_relaxed_difficulties(
    original: str,
    difficulty_order: Optional[List[str]] = None,
) -> List[str]:
    """
    When original difficulty yields no results, return all difficulties.

    Args:
        original: Originally requested difficulty.
        difficulty_order: Ordered list of difficulties.

    Returns:
        Full list of difficulties.
    """
    order = difficulty_order or ["easy", "medium", "hard"]
    return order


def should_relax_similarity(
    attempt: int,
    original_threshold: float,
    relaxed_threshold: float,
) -> float:
    """
    Determine the effective similarity threshold for a given fallback attempt.

    Args:
        attempt: Fallback attempt number.
        original_threshold: Default threshold (e.g. 0.85).
        relaxed_threshold: Relaxed threshold (e.g. 0.90).

    Returns:
        Effective threshold. Higher = more permissive.
    """
    if attempt >= FallbackLevel.RELAX_SIMILARITY:
        return relaxed_threshold
    return original_threshold
