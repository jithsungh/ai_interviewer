"""
Unit Tests — Sandbox Contracts (SandboxExecutionRequest, SandboxExecutionResult)

Tests Pydantic validation, boundary conditions, and contract invariants.
"""

import pytest
from pydantic import ValidationError

from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult


# =============================================================================
# SandboxExecutionRequest Tests
# =============================================================================

class TestSandboxExecutionRequest:
    """Tests for SandboxExecutionRequest validation."""

    # -------------------------------------------------------------------------
    # Happy path
    # -------------------------------------------------------------------------

    def test_valid_python3_request(self):
        """Minimal valid Python3 request."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="print('hello')",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        assert req.language == "python3"
        assert req.source_code == "print('hello')"
        assert req.input_data == ""  # default
        assert req.time_limit_ms == 2000
        assert req.memory_limit_kb == 262144

    def test_valid_cpp_request(self):
        """Valid C++ request with input data."""
        code = '#include <iostream>\nint main() { int n; std::cin >> n; std::cout << n; }'
        req = SandboxExecutionRequest(
            language="cpp",
            source_code=code,
            input_data="42",
            time_limit_ms=5000,
            memory_limit_kb=524288,
        )
        assert req.language == "cpp"
        assert req.input_data == "42"

    def test_valid_java_request(self):
        """Valid Java request."""
        code = 'public class Solution { public static void main(String[] args) { System.out.println("Hi"); } }'
        req = SandboxExecutionRequest(
            language="java",
            source_code=code,
            time_limit_ms=3000,
            memory_limit_kb=524288,
        )
        assert req.language == "java"

    def test_all_supported_languages(self):
        """All three supported languages are accepted."""
        for lang in ("cpp", "java", "python3"):
            req = SandboxExecutionRequest(
                language=lang,
                source_code="x",
                time_limit_ms=100,
                memory_limit_kb=4096,
            )
            assert req.language == lang

    # -------------------------------------------------------------------------
    # Language validation
    # -------------------------------------------------------------------------

    def test_invalid_language_rejected(self):
        """Unsupported language raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            SandboxExecutionRequest(
                language="ruby",
                source_code="puts 'hello'",
                time_limit_ms=2000,
                memory_limit_kb=262144,
            )
        assert "language" in str(exc_info.value).lower()

    def test_empty_language_rejected(self):
        """Empty language string is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="",
                source_code="x",
                time_limit_ms=2000,
                memory_limit_kb=262144,
            )

    # -------------------------------------------------------------------------
    # Source code validation
    # -------------------------------------------------------------------------

    def test_source_code_at_max_length(self):
        """Source code exactly at 50,000 characters is accepted."""
        code = "x" * 50000
        req = SandboxExecutionRequest(
            language="python3",
            source_code=code,
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        assert len(req.source_code) == 50000

    def test_source_code_exceeds_max_length(self):
        """Source code over 50,000 characters is rejected."""
        code = "x" * 50001
        with pytest.raises(ValidationError) as exc_info:
            SandboxExecutionRequest(
                language="python3",
                source_code=code,
                time_limit_ms=2000,
                memory_limit_kb=262144,
            )
        assert "source_code" in str(exc_info.value).lower()

    def test_empty_source_code_accepted(self):
        """Empty source code is technically valid (will fail at runtime)."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        assert req.source_code == ""

    # -------------------------------------------------------------------------
    # Input data validation
    # -------------------------------------------------------------------------

    def test_input_data_defaults_to_empty(self):
        """Input data defaults to empty string."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        assert req.input_data == ""

    def test_input_data_at_max_length(self):
        """Input data exactly at 10MB is accepted."""
        data = "a" * 10485760
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            input_data=data,
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        assert len(req.input_data) == 10485760

    def test_input_data_exceeds_max_length(self):
        """Input data over 10MB is rejected."""
        data = "a" * 10485761
        with pytest.raises(ValidationError) as exc_info:
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                input_data=data,
                time_limit_ms=2000,
                memory_limit_kb=262144,
            )
        assert "input_data" in str(exc_info.value).lower()

    # -------------------------------------------------------------------------
    # Time limit validation
    # -------------------------------------------------------------------------

    def test_time_limit_at_minimum(self):
        """Time limit at 100ms boundary."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=100,
            memory_limit_kb=4096,
        )
        assert req.time_limit_ms == 100

    def test_time_limit_at_maximum(self):
        """Time limit at 30,000ms boundary."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=30000,
            memory_limit_kb=4096,
        )
        assert req.time_limit_ms == 30000

    def test_time_limit_below_minimum_rejected(self):
        """Time limit below 100ms is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=99,
                memory_limit_kb=4096,
            )

    def test_time_limit_above_maximum_rejected(self):
        """Time limit above 30,000ms is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=30001,
                memory_limit_kb=4096,
            )

    def test_time_limit_zero_rejected(self):
        """Time limit of 0 is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=0,
                memory_limit_kb=4096,
            )

    def test_time_limit_negative_rejected(self):
        """Negative time limit is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=-1,
                memory_limit_kb=4096,
            )

    # -------------------------------------------------------------------------
    # Memory limit validation
    # -------------------------------------------------------------------------

    def test_memory_limit_at_minimum(self):
        """Memory limit at 4096 KB (4MB) boundary."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=100,
            memory_limit_kb=4096,
        )
        assert req.memory_limit_kb == 4096

    def test_memory_limit_at_maximum(self):
        """Memory limit at 1,048,576 KB (1GB) boundary."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="x",
            time_limit_ms=100,
            memory_limit_kb=1048576,
        )
        assert req.memory_limit_kb == 1048576

    def test_memory_limit_below_minimum_rejected(self):
        """Memory limit below 4096 KB is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=100,
                memory_limit_kb=4095,
            )

    def test_memory_limit_above_maximum_rejected(self):
        """Memory limit above 1,048,576 KB is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionRequest(
                language="python3",
                source_code="x",
                time_limit_ms=100,
                memory_limit_kb=1048577,
            )

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def test_model_serialization_roundtrip(self):
        """Request can be serialized to dict and back."""
        req = SandboxExecutionRequest(
            language="python3",
            source_code="print('hello')",
            input_data="world",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )
        data = req.model_dump()
        restored = SandboxExecutionRequest(**data)
        assert restored == req

    def test_model_json_roundtrip(self):
        """Request can be serialized to JSON and back."""
        req = SandboxExecutionRequest(
            language="cpp",
            source_code="int main() { return 0; }",
            time_limit_ms=5000,
            memory_limit_kb=524288,
        )
        json_str = req.model_dump_json()
        restored = SandboxExecutionRequest.model_validate_json(json_str)
        assert restored == req


# =============================================================================
# SandboxExecutionResult Tests
# =============================================================================

class TestSandboxExecutionResult:
    """Tests for SandboxExecutionResult validation."""

    def test_default_result(self):
        """Default result has sensible initial values."""
        result = SandboxExecutionResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == -1
        assert result.runtime_ms == 0
        assert result.memory_kb == 0
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.compilation_output == ""

    def test_successful_execution_result(self):
        """Result for a successful execution."""
        result = SandboxExecutionResult(
            stdout="Hello, World!\n",
            stderr="",
            exit_code=0,
            runtime_ms=150,
            memory_kb=12000,
            timed_out=False,
            memory_exceeded=False,
        )
        assert result.exit_code == 0
        assert result.runtime_ms == 150
        assert result.memory_kb == 12000

    def test_timeout_result(self):
        """Result for a timed-out execution."""
        result = SandboxExecutionResult(
            stdout="",
            stderr="",
            exit_code=124,
            runtime_ms=2000,
            memory_kb=0,
            timed_out=True,
            memory_exceeded=False,
        )
        assert result.timed_out is True
        assert result.exit_code == 124

    def test_oom_result(self):
        """Result for an OOM-killed execution."""
        result = SandboxExecutionResult(
            stdout="",
            stderr="",
            exit_code=137,
            runtime_ms=500,
            memory_kb=262144,
            timed_out=False,
            memory_exceeded=True,
        )
        assert result.memory_exceeded is True
        assert result.exit_code == 137

    def test_compilation_error_result(self):
        """Result for a compilation error."""
        result = SandboxExecutionResult(
            stdout="",
            stderr="",
            exit_code=1,
            runtime_ms=0,
            memory_kb=0,
            timed_out=False,
            memory_exceeded=False,
            compilation_output="solution.cpp:1:1: error: expected declaration",
        )
        assert result.compilation_output != ""
        assert result.exit_code == 1

    def test_runtime_ms_rejects_negative(self):
        """Negative runtime_ms is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionResult(runtime_ms=-1)

    def test_memory_kb_rejects_negative(self):
        """Negative memory_kb is rejected."""
        with pytest.raises(ValidationError):
            SandboxExecutionResult(memory_kb=-1)

    def test_result_serialization_roundtrip(self):
        """Result can be serialized to dict and back."""
        result = SandboxExecutionResult(
            stdout="42\n",
            stderr="warning: unused variable",
            exit_code=0,
            runtime_ms=250,
            memory_kb=15000,
            timed_out=False,
            memory_exceeded=False,
            compilation_output="",
        )
        data = result.model_dump()
        restored = SandboxExecutionResult(**data)
        assert restored == result
