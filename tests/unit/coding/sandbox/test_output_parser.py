"""
Unit Tests — Output Parser

Tests /usr/bin/time output parsing, metric extraction,
exit code classification, and output separation.
"""

import pytest

from app.coding.sandbox.output_parser import (
    separate_time_output,
    parse_wall_clock_time,
    parse_peak_memory,
    parse_exit_code_from_time,
    classify_exit_code,
    parse_execution_output,
    EXIT_CODE_TIMEOUT,
    EXIT_CODE_OOM,
    SeparatedOutput,
    ParsedMetrics,
)


# =============================================================================
# Sample /usr/bin/time -v Outputs
# =============================================================================

SAMPLE_TIME_OUTPUT = """\tCommand being timed: "./solution"
\tUser time (seconds): 0.01
\tSystem time (seconds): 0.00
\tPercent of CPU this job got: 95%
\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:00.01
\tAverage shared text size (kbytes): 0
\tAverage unshared data size (kbytes): 0
\tAverage stack size (kbytes): 0
\tAverage total size (kbytes): 0
\tMaximum resident set size (kbytes): 3456
\tAverage resident set size (kbytes): 0
\tMajor (requiring I/O) page faults: 0
\tMinor (reclaiming a frame) page faults: 150
\tVoluntary context switches: 1
\tInvoluntary context switches: 2
\tSwaps: 0
\tFile system inputs: 0
\tFile system outputs: 0
\tSocket messages sent: 0
\tSocket messages received: 0
\tSignals delivered: 0
\tPage size (bytes): 4096
\tExit status: 0"""

SAMPLE_TIME_OUTPUT_SLOW = """\tCommand being timed: "python3 solution.py"
\tUser time (seconds): 1.50
\tSystem time (seconds): 0.10
\tPercent of CPU this job got: 98%
\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:01.63
\tMaximum resident set size (kbytes): 45000
\tExit status: 0"""

SAMPLE_TIME_OUTPUT_HOURS = """\tCommand being timed: "./solution"
\tElapsed (wall clock) time (h:mm:ss or m:ss): 1:02:03.45
\tMaximum resident set size (kbytes): 100000
\tExit status: 0"""


# =============================================================================
# separate_time_output Tests
# =============================================================================

class TestSeparateTimeOutput:
    """Tests for separating program output from /usr/bin/time diagnostics."""

    def test_empty_output(self):
        """Empty output produces empty separated output."""
        result = separate_time_output("")
        assert result.program_stdout == ""
        assert result.program_stderr == ""
        assert result.time_output == ""

    def test_program_output_only(self):
        """Output with no time diagnostics is all program output."""
        result = separate_time_output("Hello, World!\n42")
        assert result.program_stdout == "Hello, World!\n42"
        assert result.time_output == ""

    def test_combined_output_separated(self):
        """Program output and time output are correctly separated."""
        combined = "Hello, World!\n" + SAMPLE_TIME_OUTPUT
        result = separate_time_output(combined)
        assert result.program_stdout == "Hello, World!"
        assert "Command being timed" in result.time_output
        assert "Maximum resident set size" in result.time_output

    def test_time_output_only(self):
        """Output with only time diagnostics (no program output)."""
        result = separate_time_output(SAMPLE_TIME_OUTPUT)
        assert result.program_stdout == ""
        assert "Command being timed" in result.time_output

    def test_multiline_program_output(self):
        """Multiple lines of program output before time diagnostics."""
        program_lines = "line1\nline2\nline3\n"
        combined = program_lines + SAMPLE_TIME_OUTPUT
        result = separate_time_output(combined)
        assert "line1" in result.program_stdout
        assert "line2" in result.program_stdout
        assert "line3" in result.program_stdout


# =============================================================================
# parse_wall_clock_time Tests
# =============================================================================

class TestParseWallClockTime:
    """Tests for wall clock time parsing."""

    def test_parse_short_time(self):
        """Parse sub-second time (0:00.01 = 10ms)."""
        ms = parse_wall_clock_time(SAMPLE_TIME_OUTPUT)
        assert ms == 10  # 0:00.01 = 0.01s = 10ms

    def test_parse_seconds_time(self):
        """Parse time with seconds (0:01.63 = 1630ms)."""
        ms = parse_wall_clock_time(SAMPLE_TIME_OUTPUT_SLOW)
        assert ms == 1630

    def test_parse_hours_time(self):
        """Parse time with hours (1:02:03.45)."""
        ms = parse_wall_clock_time(SAMPLE_TIME_OUTPUT_HOURS)
        # 1 hour + 2 min + 3.45s = 3600 + 120 + 3.45 = 3723.45s = 3723450ms
        assert ms == 3723450

    def test_no_time_output_returns_zero(self):
        """Missing time output returns 0."""
        assert parse_wall_clock_time("no time info here") == 0

    def test_empty_string_returns_zero(self):
        """Empty string returns 0."""
        assert parse_wall_clock_time("") == 0


# =============================================================================
# parse_peak_memory Tests
# =============================================================================

class TestParsePeakMemory:
    """Tests for peak memory (RSS) parsing."""

    def test_parse_small_memory(self):
        """Parse small memory usage."""
        kb = parse_peak_memory(SAMPLE_TIME_OUTPUT)
        assert kb == 3456

    def test_parse_large_memory(self):
        """Parse large memory usage."""
        kb = parse_peak_memory(SAMPLE_TIME_OUTPUT_SLOW)
        assert kb == 45000

    def test_no_memory_info_returns_zero(self):
        """Missing memory info returns 0."""
        assert parse_peak_memory("no memory info here") == 0

    def test_empty_string_returns_zero(self):
        """Empty string returns 0."""
        assert parse_peak_memory("") == 0


# =============================================================================
# parse_exit_code_from_time Tests
# =============================================================================

class TestParseExitCodeFromTime:
    """Tests for exit code extraction from time output."""

    def test_parse_success_exit_code(self):
        """Exit status 0 is parsed correctly."""
        code = parse_exit_code_from_time(SAMPLE_TIME_OUTPUT)
        assert code == 0

    def test_parse_error_exit_code(self):
        """Non-zero exit code is parsed."""
        text = "\tExit status: 1"
        code = parse_exit_code_from_time(text)
        assert code == 1

    def test_parse_timeout_exit_code(self):
        """Exit code 124 (timeout) is parsed."""
        text = "\tExit status: 124"
        code = parse_exit_code_from_time(text)
        assert code == 124

    def test_parse_oom_exit_code(self):
        """Exit code 137 (OOM/SIGKILL) is parsed."""
        text = "\tExit status: 137"
        code = parse_exit_code_from_time(text)
        assert code == 137

    def test_no_exit_code_returns_none(self):
        """Missing exit status returns None."""
        assert parse_exit_code_from_time("no exit info") is None


# =============================================================================
# classify_exit_code Tests
# =============================================================================

class TestClassifyExitCode:
    """Tests for exit code classification."""

    def test_success(self):
        """Exit code 0 = no timeout, no OOM."""
        result = classify_exit_code(0)
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.exit_code == 0

    def test_timeout(self):
        """Exit code 124 = timeout."""
        result = classify_exit_code(EXIT_CODE_TIMEOUT)
        assert result.timed_out is True
        assert result.memory_exceeded is False
        assert result.exit_code == 124

    def test_oom(self):
        """Exit code 137 = OOM (SIGKILL)."""
        result = classify_exit_code(EXIT_CODE_OOM)
        assert result.timed_out is False
        assert result.memory_exceeded is True
        assert result.exit_code == 137

    def test_runtime_error(self):
        """Random non-zero exit code = runtime error (no timeout/OOM)."""
        result = classify_exit_code(1)
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.exit_code == 1

    def test_segfault(self):
        """Exit code 139 (SIGSEGV = 128+11) = neither timeout nor OOM."""
        result = classify_exit_code(139)
        assert result.timed_out is False
        assert result.memory_exceeded is False
        assert result.exit_code == 139


# =============================================================================
# parse_execution_output Tests (Integration of all parsers)
# =============================================================================

class TestParseExecutionOutput:
    """Tests for the composite output parser."""

    def test_successful_execution(self):
        """Successful execution with program output and metrics."""
        combined = "42\n" + SAMPLE_TIME_OUTPUT
        separated, metrics = parse_execution_output(combined, container_exit_code=0)

        assert separated.program_stdout == "42"
        assert metrics.runtime_ms == 10
        assert metrics.memory_kb == 3456
        assert metrics.exit_code == 0
        assert metrics.timed_out is False
        assert metrics.memory_exceeded is False

    def test_timeout_execution(self):
        """Timed-out execution with exit code 124."""
        combined = ""  # No output on timeout
        separated, metrics = parse_execution_output(combined, container_exit_code=124)

        assert metrics.exit_code == 124
        assert metrics.timed_out is True
        assert metrics.memory_exceeded is False

    def test_oom_execution(self):
        """OOM-killed execution with exit code 137."""
        combined = "partial output"
        separated, metrics = parse_execution_output(combined, container_exit_code=137)

        assert metrics.exit_code == 137
        assert metrics.timed_out is False
        assert metrics.memory_exceeded is True

    def test_runtime_error_execution(self):
        """Runtime error with stderr."""
        error_output = "Traceback (most recent call last):\n  File \"solution.py\", line 1\nNameError: name 'x' is not defined"
        separated, metrics = parse_execution_output(error_output, container_exit_code=1)

        assert metrics.exit_code == 1
        assert metrics.timed_out is False
        assert metrics.memory_exceeded is False
        assert "NameError" in separated.program_stdout

    def test_empty_output(self):
        """Empty output with exit code 0."""
        separated, metrics = parse_execution_output("", container_exit_code=0)

        assert separated.program_stdout == ""
        assert metrics.exit_code == 0
        assert metrics.runtime_ms == 0
        assert metrics.memory_kb == 0

    def test_time_exit_code_takes_precedence(self):
        """Exit code from /usr/bin/time output overrides container exit code."""
        # Container returns 0, but time output says exit status 1
        time_output_with_error = SAMPLE_TIME_OUTPUT.replace(
            "Exit status: 0", "Exit status: 1"
        )
        combined = "output\n" + time_output_with_error
        separated, metrics = parse_execution_output(combined, container_exit_code=0)

        # /usr/bin/time exit code should take precedence
        assert metrics.exit_code == 1
