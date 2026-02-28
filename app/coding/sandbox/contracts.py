"""
Sandbox Contracts — Input/Output DTOs for Sandbox Execution

Defines the strict Pydantic contracts for communication between
the execution layer and the sandbox layer.

These contracts are the ONLY interface for sandbox interaction.
No other data structures should cross the sandbox boundary.

References:
- REQUIREMENTS.md §3 (Input Contracts)
- REQUIREMENTS.md §4 (Output Contracts)
- SRS FR-7.3: Isolated execution environment
- SRS NR-5: No untrusted code outside isolated environments
- SRS FM-3: Timeout termination and result
"""

from pydantic import BaseModel, Field
from typing import Literal


class SandboxExecutionRequest(BaseModel):
    """
    Request to execute untrusted code in an isolated sandbox.

    Consumed by SandboxExecutor. Produced by coding/execution layer.

    Invariants:
    - language must be one of the supported languages (cpp, java, python3)
    - source_code must not exceed 50,000 characters
    - input_data must not exceed 10MB
    - time_limit_ms: 100ms–30,000ms (enforced via Docker timeout)
    - memory_limit_kb: 4MB–1GB (enforced via Docker memory limit)
    """

    language: Literal["cpp", "java", "python3"] = Field(
        description="Programming language for execution"
    )
    source_code: str = Field(
        max_length=50000,
        description="Source code to compile and/or execute"
    )
    input_data: str = Field(
        default="",
        max_length=10485760,  # 10MB max input
        description="Standard input data for the program"
    )
    time_limit_ms: int = Field(
        ge=100,
        le=30000,
        description="Maximum execution time in milliseconds (100ms–30s)"
    )
    memory_limit_kb: int = Field(
        ge=4096,
        le=1048576,
        description="Maximum memory in kilobytes (4MB–1GB)"
    )


class SandboxExecutionResult(BaseModel):
    """
    Result of a sandbox execution.

    Produced by SandboxExecutor. Consumed by coding/execution layer.

    The sandbox populates ALL fields. The execution layer interprets them
    to determine pass/fail/error status per test case.

    Invariants:
    - If timed_out is True, runtime_ms equals the time limit
    - If memory_exceeded is True, memory_kb equals the memory limit
    - stdout/stderr are sanitized (no internal paths, no host info)
    - stdout is truncated to 1MB max
    - compilation_output is populated only for compiled languages (cpp, java)
    """

    stdout: str = Field(
        default="",
        description="Standard output (sanitized, truncated to 1MB)"
    )
    stderr: str = Field(
        default="",
        description="Standard error (sanitized)"
    )
    exit_code: int = Field(
        default=-1,
        description="Process exit code (0=success, 124=timeout, 137=OOM)"
    )
    runtime_ms: int = Field(
        default=0,
        ge=0,
        description="Actual wall-clock execution time in milliseconds"
    )
    memory_kb: int = Field(
        default=0,
        ge=0,
        description="Peak resident set size in kilobytes"
    )
    timed_out: bool = Field(
        default=False,
        description="True if execution was killed due to timeout"
    )
    memory_exceeded: bool = Field(
        default=False,
        description="True if execution was killed by OOM killer"
    )
    compilation_output: str = Field(
        default="",
        description="Compiler output for C++/Java; empty for Python3"
    )
