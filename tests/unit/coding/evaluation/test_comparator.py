"""
Unit tests for coding.evaluation.comparator — Output comparison logic
"""

import pytest
from app.coding.evaluation.comparator import compare_outputs, normalize_output


class TestNormalizeOutput:
    """Verify output normalization rules."""

    def test_empty_string(self):
        assert normalize_output("") == ""

    def test_single_line_no_trailing(self):
        assert normalize_output("Hello") == "Hello"

    def test_single_line_trailing_newline(self):
        assert normalize_output("Hello\n") == "Hello"

    def test_trailing_whitespace_stripped_per_line(self):
        assert normalize_output("Hello  \nWorld   \n") == "Hello\nWorld"

    def test_multiple_trailing_newlines(self):
        assert normalize_output("42\n\n\n") == "42"

    def test_preserves_leading_whitespace(self):
        assert normalize_output("  42\n") == "  42"

    def test_multiline(self):
        raw = "Line 1  \nLine 2\nLine 3  \n\n"
        expected = "Line 1\nLine 2\nLine 3"
        assert normalize_output(raw) == expected

    def test_only_whitespace_lines(self):
        assert normalize_output("  \n  \n") == ""

    def test_mixed_content_and_empty(self):
        raw = "data\n\n\nmore\n\n"
        assert normalize_output(raw) == "data\n\n\nmore"

    def test_tabs_stripped_trailing(self):
        assert normalize_output("data\t\n") == "data"


class TestCompareOutputs:
    """Verify output comparison with normalization."""

    def test_exact_match(self):
        assert compare_outputs("Hello", "Hello") is True

    def test_trailing_whitespace_match(self):
        assert compare_outputs("Hello World  \n\n", "Hello World\n") is True

    def test_trailing_newlines_match(self):
        assert compare_outputs("42\n\n\n", "42\n") is True

    def test_leading_whitespace_preserved(self):
        """Leading whitespace IS significant per REQUIREMENTS."""
        assert compare_outputs("  42", "42") is False

    def test_case_sensitive(self):
        assert compare_outputs("Hello", "hello") is False

    def test_both_empty(self):
        assert compare_outputs("", "") is True

    def test_empty_vs_whitespace(self):
        assert compare_outputs("", "  \n") is True

    def test_multiline_match(self):
        expected = "Line 1\nLine 2\nLine 3\n"
        actual = "Line 1\nLine 2\nLine 3"
        assert compare_outputs(expected, actual) is True

    def test_multiline_mismatch(self):
        expected = "Line 1\nLine 2"
        actual = "Line 1\nLine 3"
        assert compare_outputs(expected, actual) is False

    def test_extra_internal_newlines_differ(self):
        """Internal empty lines are preserved and must match."""
        expected = "A\n\nB"
        actual = "A\nB"
        assert compare_outputs(expected, actual) is False

    def test_numeric_output(self):
        assert compare_outputs("3.14159", "3.14159") is True
        assert compare_outputs("3.14159", "3.14158") is False

    def test_large_output(self):
        expected = "\n".join(str(i) for i in range(10000))
        actual = "\n".join(str(i) for i in range(10000))
        assert compare_outputs(expected, actual) is True

    def test_unicode(self):
        assert compare_outputs("héllo", "héllo") is True
        assert compare_outputs("héllo", "hello") is False
