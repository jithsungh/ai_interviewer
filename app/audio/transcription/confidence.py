"""
Confidence Score Aggregation

Pure functions for computing aggregate confidence from per-segment scores.
No I/O, no side effects.
"""

from __future__ import annotations

from typing import Sequence

from .contracts import TranscriptSegment


def calculate_aggregate_confidence(
    segments: Sequence[TranscriptSegment],
    *,
    weighted: bool = False,
) -> float:
    """
    Compute overall confidence from word-level segment scores.

    Parameters
    ----------
    segments : Sequence[TranscriptSegment]
        Word/phrase segments with per-segment ``confidence``.
    weighted : bool
        If ``True``, weight each segment by its duration (``end_ms - start_ms``).
        If ``False``, use simple arithmetic mean.

    Returns
    -------
    float
        Aggregate confidence clamped to ``[0.0, 1.0]``.
        Returns ``0.0`` for empty input.
    """
    if not segments:
        return 0.0

    if weighted:
        total_weight = 0.0
        weighted_sum = 0.0
        for seg in segments:
            duration = max(0, seg.end_ms - seg.start_ms)
            # Fall back to equal weight when timestamps are absent / zero
            if duration == 0:
                duration = 1
            weighted_sum += seg.confidence * duration
            total_weight += duration
        if total_weight == 0.0:
            return 0.0
        return _clamp(weighted_sum / total_weight)

    total = sum(seg.confidence for seg in segments)
    return _clamp(total / len(segments))


def _clamp(value: float) -> float:
    """Clamp *value* to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))
