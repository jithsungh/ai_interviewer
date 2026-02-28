"""
Coding Execution Submodule

Orchestrates the execution lifecycle for code submissions:
compile → run per test case → evaluate → score → persist.

Public interface:
- ExecutionService: Main orchestrator
- ExecuteSubmissionCommand: Input command
- ExecutionResult: Output result
- TestCaseExecutionResult: Per-test-case outcome
"""

from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    ExecutionResult,
    SubmissionData,
    TestCase,
    TestCaseExecutionResult,
)
from app.coding.execution.service import ExecutionService

__all__ = [
    "ExecutionService",
    "ExecuteSubmissionCommand",
    "ExecutionResult",
    "SubmissionData",
    "TestCase",
    "TestCaseExecutionResult",
]
