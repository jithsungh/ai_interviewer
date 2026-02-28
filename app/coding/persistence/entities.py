"""
Coding Persistence Entities — Domain data classes for code submissions

Plain dataclasses representing rows from ``code_submissions`` and
``code_execution_results``.  These are returned by repository methods
and consumed by the execution layer.

Contains ZERO business logic and ZERO ORM dependencies.

References:
- persistence/REQUIREMENTS.md §2 (Owned Tables)
- persistence/REQUIREMENTS.md §4 (Output Contracts)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CodeSubmission:
    """
    Domain entity for a code submission.

    Maps 1:1 to the ``code_submissions`` table.
    Mutable to allow repository construction and updates.
    """

    id: Optional[int] = None
    interview_exchange_id: int = 0
    coding_problem_id: int = 0
    language: str = ""
    source_code: str = ""
    execution_status: str = "pending"
    score: Optional[Decimal] = None
    execution_time_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    compiler_output: Optional[str] = None
    submitted_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class CodeExecutionResult:
    """
    Domain entity for a single test case execution result.

    Maps 1:1 to the ``code_execution_results`` table.
    Mutable to allow repository construction.
    """

    id: Optional[int] = None
    code_submission_id: int = 0
    test_case_id: int = 0
    passed: bool = False
    actual_output: Optional[str] = None
    runtime_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    exit_code: Optional[int] = None
    compiler_output: Optional[str] = None
    runtime_output: Optional[str] = None
    feedback: Optional[str] = None
    created_at: Optional[datetime] = None
