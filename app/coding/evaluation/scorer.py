"""
Score Calculator — Deterministic weighted scoring for test case results

Implements the scoring formula from evaluation/REQUIREMENTS.md §5::

    score = (Σ weight × passed) / (Σ weight) × 100

Pure functions.  No side effects.  No randomness.

References:
- evaluation/REQUIREMENTS.md §5 (Weighted Score Calculation)
- evaluation/REQUIREMENTS.md §5 (Feedback Generation)
- evaluation/REQUIREMENTS.md §5 (Hidden Test Case Protection)
"""

from typing import List, Optional

from app.coding.enums import TestCaseStatus


def calculate_score(
    weights: List[float],
    passed: List[bool],
) -> float:
    """
    Calculate weighted score from test case results.

    Formula::

        score = (Σ weight_i × passed_i) / (Σ weight_i) × 100

    Args:
        weights: Weight for each test case (parallel with *passed*).
        passed: Whether each test case passed (parallel with *weights*).

    Returns:
        Score in range ``[0, 100]``, rounded to 2 decimal places.
        Returns ``0.0`` if total weight is zero.

    Raises:
        ValueError: If *weights* and *passed* have different lengths.
    """
    if len(weights) != len(passed):
        raise ValueError(
            f"weights and passed must have the same length: "
            f"{len(weights)} != {len(passed)}"
        )

    total_weight = sum(weights)

    if total_weight == 0:
        return 0.0

    earned_weight = sum(w for w, p in zip(weights, passed) if p)

    score = (earned_weight / total_weight) * 100
    return round(score, 2)


def generate_feedback(status: TestCaseStatus) -> str:
    """
    Generate human-readable feedback for a test case result.

    Args:
        status: The test case execution status.

    Returns:
        Feedback string (e.g. ``"Passed"``, ``"Wrong Answer"``).
    """
    _feedback_map = {
        TestCaseStatus.PASSED: "Passed",
        TestCaseStatus.FAILED: "Wrong Answer",
        TestCaseStatus.TIMEOUT: "Time Limit Exceeded",
        TestCaseStatus.MEMORY_EXCEEDED: "Memory Limit Exceeded",
        TestCaseStatus.RUNTIME_ERROR: "Runtime Error",
    }
    return _feedback_map.get(status, "Unknown Error")


def generate_match_details(
    status: TestCaseStatus,
    is_hidden: bool,
    expected: str,
    actual: str,
) -> Optional[str]:
    """
    Generate detailed match information for visible test cases.

    Hidden test cases **never** receive match details — this prevents
    information leakage of expected outputs.

    Args:
        status: Test case execution status.
        is_hidden: Whether the test case is hidden.
        expected: Expected output.
        actual: Actual output from execution.

    Returns:
        Match-details string, or ``None`` for hidden/passed cases.
    """
    if status == TestCaseStatus.PASSED:
        return None

    if is_hidden:
        return None

    if len(actual) == 0:
        return "No output produced"
    elif len(expected) != len(actual):
        return (
            f"Output length mismatch: "
            f"expected {len(expected)} chars, got {len(actual)} chars"
        )
    else:
        return "Output does not match expected"
