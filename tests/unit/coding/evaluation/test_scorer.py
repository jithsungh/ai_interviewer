"""
Unit tests for coding.evaluation.scorer — Score calculation & feedback
"""

import pytest
from app.coding.enums import TestCaseStatus as _TCStatus
from app.coding.evaluation.scorer import (
    calculate_score,
    generate_feedback,
    generate_match_details,
)


class TestCalculateScore:
    """Verify weighted score calculation formula."""

    def test_all_passed_equal_weights(self):
        assert calculate_score([1.0, 1.0, 1.0], [True, True, True]) == 100.0

    def test_all_failed(self):
        assert calculate_score([1.0, 1.0], [False, False]) == 0.0

    def test_partial_equal_weights(self):
        # 2 of 3 passed, equal weights → 66.67
        assert calculate_score([1.0, 1.0, 1.0], [True, True, False]) == 66.67

    def test_weighted_scoring(self):
        # weight=1 pass, weight=2 pass, weight=1 fail → (1+2)/(1+2+1)*100 = 75.0
        assert calculate_score([1.0, 2.0, 1.0], [True, True, False]) == 75.0

    def test_single_test_passed(self):
        assert calculate_score([1.0], [True]) == 100.0

    def test_single_test_failed(self):
        assert calculate_score([1.0], [False]) == 0.0

    def test_zero_weight_excluded(self):
        # weight=0 doesn't count: total_weight = 1, earned = 1 → 100%
        assert calculate_score([0.0, 1.0], [True, True]) == 100.0

    def test_all_zero_weight(self):
        assert calculate_score([0.0, 0.0], [True, True]) == 0.0

    def test_empty_lists(self):
        assert calculate_score([], []) == 0.0

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            calculate_score([1.0, 2.0], [True])

    def test_fractional_weights(self):
        assert calculate_score([0.5, 0.5], [True, False]) == 50.0

    def test_large_weights(self):
        assert calculate_score([100.0, 100.0], [True, False]) == 50.0

    def test_precision(self):
        # (1)/(3)*100 = 33.33...
        result = calculate_score([1.0, 1.0, 1.0], [True, False, False])
        assert result == 33.33


class TestGenerateFeedback:
    """Verify feedback string generation."""

    def test_passed(self):
        assert generate_feedback(_TCStatus.PASSED) == "Passed"

    def test_failed(self):
        assert generate_feedback(_TCStatus.FAILED) == "Wrong Answer"

    def test_timeout(self):
        assert generate_feedback(_TCStatus.TIMEOUT) == "Time Limit Exceeded"

    def test_memory_exceeded(self):
        assert generate_feedback(_TCStatus.MEMORY_EXCEEDED) == "Memory Limit Exceeded"

    def test_runtime_error(self):
        assert generate_feedback(_TCStatus.RUNTIME_ERROR) == "Runtime Error"


class TestGenerateMatchDetails:
    """Verify match detail generation with hidden test protection."""

    def test_passed_returns_none(self):
        result = generate_match_details(
            _TCStatus.PASSED, is_hidden=False, expected="42", actual="42"
        )
        assert result is None

    def test_hidden_returns_none(self):
        result = generate_match_details(
            _TCStatus.FAILED, is_hidden=True, expected="42", actual="43"
        )
        assert result is None

    def test_no_output_produced(self):
        result = generate_match_details(
            _TCStatus.FAILED, is_hidden=False, expected="42", actual=""
        )
        assert result == "No output produced"

    def test_length_mismatch(self):
        result = generate_match_details(
            _TCStatus.FAILED, is_hidden=False, expected="42", actual="423"
        )
        assert "length mismatch" in result
        assert "expected 2 chars" in result
        assert "got 3 chars" in result

    def test_content_mismatch_same_length(self):
        result = generate_match_details(
            _TCStatus.FAILED, is_hidden=False, expected="42", actual="43"
        )
        assert result == "Output does not match expected"

    def test_hidden_never_leaks_details(self):
        """Hidden test cases must NEVER reveal expected output details."""
        for status in [_TCStatus.FAILED, _TCStatus.TIMEOUT, _TCStatus.RUNTIME_ERROR]:
            result = generate_match_details(
                status, is_hidden=True, expected="secret_answer", actual="wrong"
            )
            assert result is None
