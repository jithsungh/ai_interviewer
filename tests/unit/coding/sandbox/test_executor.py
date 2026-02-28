"""
Unit Tests — Sandbox Executor

Tests the SandboxExecutor orchestration service.
Uses mocks for Docker execution (no actual containers needed).
Tests compilation error detection, output processing, timeout handling,
OOM handling, and metric reporting.
"""

import pytest
from unittest.mock import patch, MagicMock
from prometheus_client import CollectorRegistry

from app.coding.sandbox.contracts import SandboxExecutionRequest, SandboxExecutionResult
from app.coding.sandbox.executor import SandboxExecutor, HARD_TIMEOUT_MARGIN_SECONDS, COMPILATION_OVERHEAD_SECONDS
from app.coding.sandbox.docker_runner import DockerRunResult
from app.coding.sandbox.output_parser import EXIT_CODE_TIMEOUT, EXIT_CODE_OOM
from app.shared.errors.exceptions import SandboxExecutionError


# =============================================================================
# Fixtures
# =============================================================================

class FakeSandboxSettings:
    """Fake sandbox settings for unit tests."""
    sandbox_image_cpp = "code-sandbox-cpp:latest"
    sandbox_image_java = "code-sandbox-java:latest"
    sandbox_image_python = "code-sandbox-python:latest"
    sandbox_time_limit_ms = 2000
    sandbox_memory_limit_kb = 262144
    sandbox_process_limit = 64
    sandbox_max_output_size = 1048576
    sandbox_network_disabled = True
    sandbox_seccomp_profile = None


@pytest.fixture
def sandbox_settings():
    return FakeSandboxSettings()


@pytest.fixture
def executor(sandbox_settings):
    return SandboxExecutor(sandbox_settings)


@pytest.fixture
def python_request():
    return SandboxExecutionRequest(
        language="python3",
        source_code="print('hello')",
        input_data="",
        time_limit_ms=2000,
        memory_limit_kb=262144,
    )


@pytest.fixture
def cpp_request():
    return SandboxExecutionRequest(
        language="cpp",
        source_code='#include <iostream>\nint main() { std::cout << "hello"; return 0; }',
        input_data="",
        time_limit_ms=5000,
        memory_limit_kb=524288,
    )


# Sample /usr/bin/time output for successful execution
SAMPLE_TIME_OUTPUT = """\tCommand being timed: "python3 solution.py"
\tUser time (seconds): 0.01
\tSystem time (seconds): 0.00
\tPercent of CPU this job got: 95%
\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:00.15
\tMaximum resident set size (kbytes): 12000
\tExit status: 0"""


def _make_docker_result(
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    timed_out: bool = False,
) -> DockerRunResult:
    """Helper to create DockerRunResult."""
    return DockerRunResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
    )


# =============================================================================
# Successful Execution Tests
# =============================================================================

class TestSuccessfulExecution:
    """Tests for successful code execution scenarios."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_python3_hello_world(self, mock_metrics, mock_run, executor, python_request):
        """Successful Python3 execution returns correct result."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout="hello\n" + SAMPLE_TIME_OUTPUT,
            exit_code=0,
        )

        result = executor.execute(python_request)

        assert isinstance(result, SandboxExecutionResult)
        assert result.exit_code == 0
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.compilation_output == ""
        assert "hello" in result.stdout

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_execution_returns_metrics(self, mock_metrics, mock_run, executor, python_request):
        """Execution metrics (runtime, memory) are extracted from time output."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout="hello\n" + SAMPLE_TIME_OUTPUT,
            exit_code=0,
        )

        result = executor.execute(python_request)

        assert result.runtime_ms == 150  # 0:00.15 = 150ms
        assert result.memory_kb == 12000


# =============================================================================
# Compilation Error Tests
# =============================================================================

class TestCompilationErrors:
    """Tests for compilation error handling."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_cpp_compilation_error_detected(self, mock_metrics, mock_run, executor, cpp_request):
        """C++ compilation errors are detected and reported."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout="COMPILATION_ERROR\nsolution.cpp:1:1: error: expected ';'",
            exit_code=1,
        )

        result = executor.execute(cpp_request)

        assert result.exit_code == 1
        assert "error: expected ';'" in result.compilation_output
        assert result.stdout == ""
        assert result.runtime_ms == 0

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_python3_no_compilation_error_detection(self, mock_metrics, mock_run, executor, python_request):
        """Python3 does not trigger compilation error detection."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        # Even if output starts with COMPILATION_ERROR, Python3 shouldn't trigger it
        mock_run.return_value = _make_docker_result(
            stdout="COMPILATION_ERROR\nsome output",
            exit_code=1,
        )

        result = executor.execute(python_request)

        # Python3 has no compilation step, so this is treated as runtime output
        assert result.compilation_output == ""


# =============================================================================
# Timeout Tests
# =============================================================================

class TestTimeoutHandling:
    """Tests for timeout detection and handling."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_hard_timeout_returns_timeout_result(self, mock_metrics, mock_run, executor, python_request):
        """Hard timeout (Docker process killed) returns timeout result."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_metrics.sandbox_timeout_total = MagicMock()
        mock_run.return_value = _make_docker_result(
            timed_out=True,
            exit_code=124,
        )

        result = executor.execute(python_request)

        assert result.timed_out is True
        assert result.exit_code == EXIT_CODE_TIMEOUT
        assert result.runtime_ms == python_request.time_limit_ms

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_in_container_timeout_detected(self, mock_metrics, mock_run, executor, python_request):
        """In-container timeout (exit code 124) is detected."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_metrics.sandbox_timeout_total = MagicMock()
        # Container completes (not hard timeout) but exit code 124
        time_output = SAMPLE_TIME_OUTPUT.replace("Exit status: 0", "Exit status: 124")
        mock_run.return_value = _make_docker_result(
            stdout=time_output,
            exit_code=124,
            timed_out=False,
        )

        result = executor.execute(python_request)

        assert result.timed_out is True
        assert result.runtime_ms == python_request.time_limit_ms


# =============================================================================
# OOM Tests
# =============================================================================

class TestOOMHandling:
    """Tests for out-of-memory detection and handling."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_oom_detected_from_exit_code(self, mock_metrics, mock_run, executor, python_request):
        """OOM (exit code 137) is detected and reported."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_metrics.sandbox_error_total = MagicMock()
        mock_metrics.sandbox_error_total.labels.return_value = MagicMock()
        mock_run.return_value = _make_docker_result(
            stdout="",
            exit_code=137,
            timed_out=False,
        )

        result = executor.execute(python_request)

        assert result.memory_exceeded is True
        assert result.exit_code == EXIT_CODE_OOM
        assert result.memory_kb == python_request.memory_limit_kb


# =============================================================================
# Infrastructure Error Tests
# =============================================================================

class TestInfrastructureErrors:
    """Tests for sandbox infrastructure failures."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_docker_not_available_raises_sandbox_error(self, mock_metrics, mock_run, executor, python_request):
        """Docker not being available raises SandboxExecutionError."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_metrics.sandbox_error_total = MagicMock()
        mock_metrics.sandbox_error_total.labels.return_value = MagicMock()
        mock_run.side_effect = RuntimeError("Docker daemon not running")

        with pytest.raises(SandboxExecutionError):
            executor.execute(python_request)


# =============================================================================
# Output Sanitization Tests
# =============================================================================

class TestOutputSanitization:
    """Tests that executor sanitizes output before returning."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_internal_paths_sanitized_in_output(self, mock_metrics, mock_run, executor, python_request):
        """Internal paths like /tmp/sandbox/ are removed from output."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout="/tmp/sandbox/solution.py: error message\n" + SAMPLE_TIME_OUTPUT,
            exit_code=1,
        )

        result = executor.execute(python_request)

        assert "/tmp/sandbox/" not in result.stdout
        assert "/tmp/sandbox/" not in result.stderr


# =============================================================================
# Compilation Error Detection (Static Methods)
# =============================================================================

class TestCompilationErrorDetection:
    """Tests for the static compilation error detection methods."""

    def test_is_compilation_error_with_marker(self):
        """Detects COMPILATION_ERROR marker."""
        assert SandboxExecutor._is_compilation_error("COMPILATION_ERROR\nerror details", 1) is True

    def test_is_not_compilation_error_on_success(self):
        """Exit code 0 is never a compilation error."""
        assert SandboxExecutor._is_compilation_error("COMPILATION_ERROR\n", 0) is False

    def test_is_not_compilation_error_without_marker(self):
        """Without marker, non-zero exit is not a compilation error."""
        assert SandboxExecutor._is_compilation_error("some runtime error", 1) is False

    def test_extract_compilation_output_removes_marker(self):
        """Extracts error message after COMPILATION_ERROR marker."""
        output = "COMPILATION_ERROR\nsolution.cpp:1: error: undeclared identifier"
        result = SandboxExecutor._extract_compilation_output(output)
        assert result == "solution.cpp:1: error: undeclared identifier"
        assert "COMPILATION_ERROR" not in result

    def test_extract_compilation_output_multiline(self):
        """Extracts multi-line compilation errors."""
        output = "COMPILATION_ERROR\nerror line 1\nerror line 2\nnote: some note"
        result = SandboxExecutor._extract_compilation_output(output)
        assert "error line 1" in result
        assert "error line 2" in result
        assert "note: some note" in result


# =============================================================================
# Hard Timeout Calculation Tests
# =============================================================================

class TestHardTimeoutCalculation:
    """Tests that hard timeout is correctly calculated."""

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_python3_hard_timeout_no_compilation_overhead(self, mock_metrics, mock_run, executor):
        """Python3 hard timeout = time_limit + margin (no compilation)."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout=SAMPLE_TIME_OUTPUT,
            exit_code=0,
        )

        request = SandboxExecutionRequest(
            language="python3",
            source_code="print('hi')",
            time_limit_ms=2000,
            memory_limit_kb=262144,
        )

        executor.execute(request)

        # Verify run_container was called with correct timeout
        call_args = mock_run.call_args
        hard_timeout = call_args.kwargs.get("overall_timeout_seconds") or call_args[1].get("overall_timeout_seconds")
        expected = 2.0 + HARD_TIMEOUT_MARGIN_SECONDS
        assert hard_timeout == expected

    @patch("app.coding.sandbox.executor.run_container")
    @patch("app.coding.sandbox.executor.metrics")
    def test_cpp_hard_timeout_includes_compilation_overhead(self, mock_metrics, mock_run, executor):
        """C++ hard timeout = time_limit + compilation_overhead + margin."""
        mock_metrics.sandbox_execution_duration_seconds = MagicMock()
        mock_metrics.sandbox_execution_duration_seconds.__enter__ = MagicMock(return_value=None)
        mock_metrics.sandbox_execution_duration_seconds.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = _make_docker_result(
            stdout=SAMPLE_TIME_OUTPUT,
            exit_code=0,
        )

        request = SandboxExecutionRequest(
            language="cpp",
            source_code="int main() { return 0; }",
            time_limit_ms=5000,
            memory_limit_kb=524288,
        )

        executor.execute(request)

        call_args = mock_run.call_args
        hard_timeout = call_args.kwargs.get("overall_timeout_seconds") or call_args[1].get("overall_timeout_seconds")
        expected = 5.0 + COMPILATION_OVERHEAD_SECONDS + HARD_TIMEOUT_MARGIN_SECONDS
        assert hard_timeout == expected
