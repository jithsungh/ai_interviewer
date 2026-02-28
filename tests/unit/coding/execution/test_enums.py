"""
Unit tests for coding.enums — ExecutionStatus and TestCaseStatus
"""

import pytest
from app.coding.enums import ExecutionStatus
from app.coding.enums import TestCaseStatus as _TCStatus


class TestExecutionStatus:
    """Verify ExecutionStatus enum values match the DB enum."""

    def test_all_values_present(self):
        expected = {"pending", "running", "passed", "failed", "error", "timeout", "memory_exceeded"}
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected

    def test_string_inheritance(self):
        """ExecutionStatus values are usable as plain strings."""
        assert ExecutionStatus.PENDING == "pending"
        assert str(ExecutionStatus.RUNNING) == "ExecutionStatus.RUNNING"
        assert ExecutionStatus.PASSED.value == "passed"

    def test_construction_from_string(self):
        assert ExecutionStatus("pending") is ExecutionStatus.PENDING
        assert ExecutionStatus("memory_exceeded") is ExecutionStatus.MEMORY_EXCEEDED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ExecutionStatus("nonexistent")

    def test_member_count(self):
        assert len(ExecutionStatus) == 7


class TestTCStatus:
    """Verify TestCaseStatus enum values."""

    def test_all_values_present(self):
        expected = {"passed", "failed", "timeout", "memory_exceeded", "runtime_error"}
        actual = {s.value for s in _TCStatus}
        assert actual == expected

    def test_string_inheritance(self):
        assert _TCStatus.PASSED == "passed"
        assert _TCStatus.RUNTIME_ERROR == "runtime_error"

    def test_construction_from_string(self):
        assert _TCStatus("timeout") is _TCStatus.TIMEOUT

    def test_member_count(self):
        assert len(_TCStatus) == 5
