"""
Coding Enums — Shared status enumerations for the coding module

Defines execution status and test case status enums used across
coding submodules (execution, evaluation, persistence).

Placed at the coding module root to prevent circular imports
between execution and evaluation submodules.

References:
- execution/REQUIREMENTS.md §4 (Output Contracts)
- schema.sql: code_execution_status enum type
- persistence/REQUIREMENTS.md §2 (execution_status column)
"""

from enum import Enum


class ExecutionStatus(str, Enum):
    """
    Overall submission execution status.

    Maps to the ``code_execution_status`` PostgreSQL enum.
    Defines the state machine for the execution lifecycle.

    Terminal states: PASSED, FAILED, ERROR, TIMEOUT, MEMORY_EXCEEDED.
    Non-terminal states: PENDING, RUNNING.
    """

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"


class TestCaseStatus(str, Enum):
    """
    Individual test case execution outcome.

    Used internally by the execution service to classify
    per-test-case results before persisting them as a
    ``passed`` boolean + ``feedback`` string.
    """

    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    RUNTIME_ERROR = "runtime_error"
