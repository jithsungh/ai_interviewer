"""
Coding Evaluation Submodule

Deterministic, stateless scoring engine for code submissions.
Pure functions — no side effects, no persistence, no randomness.

Public interface:
- normalize_output, compare_outputs (comparator)
- calculate_score, generate_feedback, generate_match_details (scorer)
"""

from app.coding.evaluation.comparator import compare_outputs, normalize_output
from app.coding.evaluation.scorer import (
    calculate_score,
    generate_feedback,
    generate_match_details,
)

__all__ = [
    "normalize_output",
    "compare_outputs",
    "calculate_score",
    "generate_feedback",
    "generate_match_details",
]
