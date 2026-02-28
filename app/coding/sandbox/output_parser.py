"""
Output Parser — Extracts Execution Metrics from Container Output

Parses /usr/bin/time -v output to extract:
- Wall clock time (runtime_ms)
- Peak memory usage (memory_kb)
- Exit code interpretation (timeout, OOM, success, error)

Also separates program stdout from /usr/bin/time diagnostic output.

References:
- REQUIREMENTS.md §5 (Execution Monitoring)
- REQUIREMENTS.md §9 (Edge Cases)
"""

import re
from typing import Final, NamedTuple, Optional


# Exit codes with special meaning
EXIT_CODE_TIMEOUT: Final[int] = 124       # timeout(1) killed the process
EXIT_CODE_OOM: Final[int] = 137           # Docker OOM killer (SIGKILL = 128 + 9)
EXIT_CODE_SIGKILL: Final[int] = 137       # SIGKILL
EXIT_CODE_COMPILATION_TIMEOUT: Final[int] = 124

# Regex patterns for /usr/bin/time -v output
_WALL_CLOCK_PATTERN: Final[re.Pattern] = re.compile(
    r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*"
    r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)"
)

_MAX_RSS_PATTERN: Final[re.Pattern] = re.compile(
    r"Maximum resident set size \(kbytes\):\s*(\d+)"
)

_EXIT_STATUS_PATTERN: Final[re.Pattern] = re.compile(
    r"Exit status:\s*(\d+)"
)

# Marker for the start of /usr/bin/time -v output
_TIME_OUTPUT_MARKER: Final[str] = "\tCommand being timed:"


class ParsedMetrics(NamedTuple):
    """Parsed execution metrics from /usr/bin/time output."""
    runtime_ms: int
    memory_kb: int
    exit_code: int
    timed_out: bool
    memory_exceeded: bool


class SeparatedOutput(NamedTuple):
    """Separated program output from time diagnostics."""
    program_stdout: str
    program_stderr: str
    time_output: str


def separate_time_output(combined_output: str) -> SeparatedOutput:
    """
    Separate program output from /usr/bin/time -v diagnostic output.

    /usr/bin/time -v writes to stderr. When both stdout and stderr are
    captured together (2>&1), we need to separate them.

    The time output starts with a line containing 'Command being timed:'
    and continues to the end.

    Args:
        combined_output: Combined stdout+stderr from container execution

    Returns:
        SeparatedOutput with program stdout, stderr, and time diagnostic text
    """
    if not combined_output:
        return SeparatedOutput(
            program_stdout="",
            program_stderr="",
            time_output=""
        )

    lines = combined_output.split("\n")
    time_start_idx: Optional[int] = None

    # Find where /usr/bin/time output starts
    for i, line in enumerate(lines):
        if _TIME_OUTPUT_MARKER in line:
            time_start_idx = i
            break

    if time_start_idx is None:
        # No time output found — entire output is program output
        return SeparatedOutput(
            program_stdout=combined_output,
            program_stderr="",
            time_output=""
        )

    program_output = "\n".join(lines[:time_start_idx])
    time_output = "\n".join(lines[time_start_idx:])

    return SeparatedOutput(
        program_stdout=program_output,
        program_stderr="",
        time_output=time_output
    )


def parse_wall_clock_time(time_output: str) -> int:
    """
    Parse wall clock time from /usr/bin/time -v output.

    Format: 'Elapsed (wall clock) time (h:mm:ss or m:ss): H:MM:SS.ss'
    Converts to milliseconds.

    Args:
        time_output: Raw /usr/bin/time -v output text

    Returns:
        Wall clock time in milliseconds, or 0 if not found
    """
    match = _WALL_CLOCK_PATTERN.search(time_output)
    if not match:
        return 0

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2))
    seconds = float(match.group(3))

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return int(total_seconds * 1000)


def parse_peak_memory(time_output: str) -> int:
    """
    Parse peak memory usage from /usr/bin/time -v output.

    Format: 'Maximum resident set size (kbytes): NNNN'

    Args:
        time_output: Raw /usr/bin/time -v output text

    Returns:
        Peak memory usage in kilobytes, or 0 if not found
    """
    match = _MAX_RSS_PATTERN.search(time_output)
    if not match:
        return 0

    return int(match.group(1))


def parse_exit_code_from_time(time_output: str) -> Optional[int]:
    """
    Parse exit code from /usr/bin/time -v output.

    Format: 'Exit status: N'

    Args:
        time_output: Raw /usr/bin/time -v output text

    Returns:
        Exit code, or None if not found
    """
    match = _EXIT_STATUS_PATTERN.search(time_output)
    if not match:
        return None

    return int(match.group(1))


def classify_exit_code(exit_code: int) -> ParsedMetrics:
    """
    Classify an exit code into timeout/OOM/normal status.

    Exit code meanings:
    - 0: Successful execution
    - 124: Killed by timeout(1) command
    - 137: Killed by SIGKILL (typically Docker OOM killer)
    - Other non-zero: Runtime error

    Args:
        exit_code: Process exit code

    Returns:
        ParsedMetrics with timed_out and memory_exceeded flags set,
        and runtime_ms/memory_kb set to 0 (to be filled by caller)
    """
    timed_out = exit_code == EXIT_CODE_TIMEOUT
    memory_exceeded = exit_code == EXIT_CODE_OOM

    return ParsedMetrics(
        runtime_ms=0,
        memory_kb=0,
        exit_code=exit_code,
        timed_out=timed_out,
        memory_exceeded=memory_exceeded
    )


def parse_execution_output(
    combined_output: str,
    container_exit_code: int
) -> tuple[SeparatedOutput, ParsedMetrics]:
    """
    Parse combined container output into structured metrics and separated output.

    This is the main entry point for output parsing.

    Steps:
    1. Separate program output from /usr/bin/time diagnostic output
    2. Parse execution metrics from time output
    3. Classify exit code for timeout/OOM detection

    Args:
        combined_output: Raw combined output from container (stdout+stderr via 2>&1)
        container_exit_code: Exit code from docker container

    Returns:
        Tuple of (SeparatedOutput, ParsedMetrics) with all parsed data
    """
    separated = separate_time_output(combined_output)

    # Parse metrics from /usr/bin/time output
    runtime_ms = parse_wall_clock_time(separated.time_output)
    memory_kb = parse_peak_memory(separated.time_output)

    # Use exit code from time output if available, else container exit code
    time_exit_code = parse_exit_code_from_time(separated.time_output)
    effective_exit_code = time_exit_code if time_exit_code is not None else container_exit_code

    # Classify exit code
    base_metrics = classify_exit_code(effective_exit_code)

    metrics = ParsedMetrics(
        runtime_ms=runtime_ms,
        memory_kb=memory_kb,
        exit_code=effective_exit_code,
        timed_out=base_metrics.timed_out,
        memory_exceeded=base_metrics.memory_exceeded
    )

    return separated, metrics
