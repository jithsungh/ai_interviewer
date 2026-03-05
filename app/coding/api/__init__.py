"""
Coding API — Public HTTP Interface for Code Submission

Exports the FastAPI router and request/response contracts.

Endpoints:
- POST /submit — Submit code for execution
- GET /submissions/{submission_id} — Get execution status and results
- GET /interviews/{interview_id}/submissions — List submissions for interview
"""

from app.coding.api.contracts import (
    CodeSubmissionError,
    ExecutionStatusResponse,
    SubmissionSummary,
    SubmitCodeRequest,
    SubmitCodeResponse,
    TestCaseResultDTO,
)
from app.coding.api.routes import router

__all__ = [
    "router",
    # Request models
    "SubmitCodeRequest",
    # Response models
    "SubmitCodeResponse",
    "ExecutionStatusResponse",
    "TestCaseResultDTO",
    "SubmissionSummary",
    "CodeSubmissionError",
]
