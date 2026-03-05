"""
Coding API Contracts — Pydantic request/response models

Defines the public HTTP API models for code submission and
execution status retrieval.  Follows the pattern established by
``app/evaluation/api/contracts.py``.

References:
- coding/api/REQUIREMENTS.md §3 (Input Contracts)
- coding/api/REQUIREMENTS.md §4 (Output Contracts)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class SubmitCodeRequest(BaseModel):
    """
    Request body for ``POST /api/v1/coding/submit``.

    Represents a candidate's code submission for a coding exchange.
    """

    interview_exchange_id: int = Field(
        gt=0,
        description="ID of the interview exchange",
    )
    coding_problem_id: int = Field(
        gt=0,
        description="ID of the coding problem",
    )
    language: Literal["cpp", "java", "python3"] = Field(
        description="Programming language",
    )
    source_code: str = Field(
        min_length=1,
        max_length=50000,
        description="Source code (max 50KB)",
    )

    @field_validator("source_code")
    @classmethod
    def validate_source_code(cls, v: str) -> str:
        """Strip leading/trailing whitespace and reject empty code."""
        v = v.strip()
        if not v:
            raise ValueError("Source code cannot be empty after trimming whitespace")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "source_code": (
                    "def two_sum(nums, target):\n"
                    "    seen = {}\n"
                    "    for i, num in enumerate(nums):\n"
                    "        complement = target - num\n"
                    "        if complement in seen:\n"
                    "            return [seen[complement], i]\n"
                    "        seen[num] = i\n"
                    "    return []"
                ),
            }
        }
    }


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class SubmitCodeResponse(BaseModel):
    """
    Response body for ``POST /api/v1/coding/submit`` (201 Created).
    """

    submission_id: int
    execution_status: Literal["pending", "running"] = "pending"
    message: str = "Code submitted successfully. Execution in progress."

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": 789,
                "execution_status": "pending",
                "message": "Code submitted successfully. Execution in progress.",
            }
        }
    }


class TestCaseResultDTO(BaseModel):
    """
    Individual test case result in an execution status response.

    Hidden test cases have ``actual_output`` and ``expected_output``
    set to ``None`` to prevent information leakage.
    """

    test_case_id: int
    test_case_name: str
    passed: bool
    visible: bool
    actual_output: Optional[str] = None
    expected_output: Optional[str] = None
    runtime_ms: int
    memory_kb: int
    feedback: str

    model_config = {"from_attributes": True}


class ExecutionStatusResponse(BaseModel):
    """
    Response body for ``GET /api/v1/coding/submissions/{submission_id}``.

    Contains full execution details including per-test-case results.
    """

    submission_id: int
    interview_exchange_id: int
    coding_problem_id: int
    language: str
    execution_status: Literal[
        "pending", "running", "passed", "failed",
        "error", "timeout", "memory_exceeded",
    ]
    score: float
    execution_time_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    compiler_output: Optional[str] = None
    test_results: List[TestCaseResultDTO]
    submitted_at: datetime
    executed_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "submission_id": 789,
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "execution_status": "passed",
                "score": 100.0,
                "execution_time_ms": 145,
                "memory_kb": 12000,
                "compiler_output": None,
                "test_results": [
                    {
                        "test_case_id": 1,
                        "test_case_name": "Example 1",
                        "passed": True,
                        "visible": True,
                        "actual_output": "[0, 1]",
                        "expected_output": "[0, 1]",
                        "runtime_ms": 45,
                        "memory_kb": 12000,
                        "feedback": "Passed",
                    },
                    {
                        "test_case_id": 2,
                        "test_case_name": "Hidden Test 1",
                        "passed": True,
                        "visible": False,
                        "actual_output": None,
                        "expected_output": None,
                        "runtime_ms": 50,
                        "memory_kb": 11500,
                        "feedback": "Passed",
                    },
                ],
                "submitted_at": "2026-02-14T10:30:00Z",
                "executed_at": "2026-02-14T10:30:05Z",
            }
        },
    }


class SubmissionSummary(BaseModel):
    """
    Summary of a code submission (used in list endpoints).

    Does NOT include source code or detailed test results
    (per REQUIREMENTS.md §6 — no full source code in list endpoints).
    """

    submission_id: int
    interview_exchange_id: int
    coding_problem_id: int
    language: str
    execution_status: str
    score: float
    submitted_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "submission_id": 789,
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "execution_status": "passed",
                "score": 100.0,
                "submitted_at": "2026-02-14T10:30:00Z",
            }
        },
    }


class CodeSubmissionError(BaseModel):
    """
    Structured error response for code submission endpoints.
    """

    error: str
    message: str
    details: Optional[dict] = None
    request_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "DUPLICATE_SUBMISSION",
                "message": "Code already submitted for this exchange",
                "details": {"existing_submission_id": 789},
            }
        }
    }
