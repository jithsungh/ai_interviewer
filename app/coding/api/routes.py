"""
Coding API Routes — FastAPI endpoint definitions

Provides HTTP endpoints for code submission and execution status.
Follows the routing pattern established by ``app/evaluation/api/routes.py``:
- Bare ``APIRouter()`` — prefix/tags set in ``router_registry.py``
- Auth via ``Depends(get_identity)`` / ``Depends(require_candidate)``
- ``get_db_session_with_commit`` for writes, ``get_db_session`` for reads

References:
- coding/api/REQUIREMENTS.md §5 (Endpoint Definitions)
- coding/api/REQUIREMENTS.md §6 (Invariants & Constraints)
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.coding.api.contracts import (
    CodeSubmissionError,
    ExecutionStatusResponse,
    SubmissionSummary,
    SubmitCodeRequest,
    SubmitCodeResponse,
)
from app.coding.api.service import CodingApiService
from app.persistence.postgres.session import get_db_session, get_db_session_with_commit
from app.shared.auth_context import IdentityContext
from app.shared.auth_context.dependencies import get_identity
from app.shared.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_service(db: Session) -> CodingApiService:
    """Construct the coding API service with a DB session."""
    return CodingApiService(db)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/submit",
    response_model=SubmitCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit code for execution",
    description=(
        "Submit source code for a coding exchange. "
        "Creates a submission with `pending` status and enqueues "
        "execution asynchronously."
    ),
    responses={
        401: {"description": "Missing or invalid auth token"},
        403: {"description": "Candidate does not own exchange"},
        404: {"description": "Exchange or problem not found"},
        409: {
            "description": "Submission already exists for exchange",
            "model": CodeSubmissionError,
        },
        422: {"description": "Validation error"},
    },
)
async def submit_code(
    request: SubmitCodeRequest,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session_with_commit),
) -> SubmitCodeResponse:
    """
    Submit code for a coding interview exchange.

    Creates a ``code_submission`` record with ``execution_status='pending'``.
    Execution is handled asynchronously by a background worker.
    """
    service = _build_service(db)
    return service.submit_code(
        identity=identity,
        interview_exchange_id=request.interview_exchange_id,
        coding_problem_id=request.coding_problem_id,
        language=request.language,
        source_code=request.source_code,
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=ExecutionStatusResponse,
    summary="Get execution status",
    description=(
        "Retrieve the execution status and test case results for a "
        "code submission. Hidden test case details are redacted."
    ),
    responses={
        401: {"description": "Missing or invalid auth token"},
        403: {"description": "Candidate does not own submission"},
        404: {"description": "Submission not found"},
    },
)
async def get_execution_status(
    submission_id: int,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> ExecutionStatusResponse:
    """
    Get execution status and results for a code submission.

    Hidden test case expected outputs are never returned.
    """
    service = _build_service(db)
    return service.get_execution_status(
        identity=identity,
        submission_id=submission_id,
    )


@router.get(
    "/interviews/{interview_id}/submissions",
    response_model=List[SubmissionSummary],
    summary="List submissions for interview",
    description=(
        "List all code submissions for an interview. "
        "Returns summary only — no source code or detailed test results."
    ),
    responses={
        401: {"description": "Missing or invalid auth token"},
        403: {"description": "Candidate does not own interview"},
        404: {"description": "Interview not found"},
    },
)
async def list_submissions_for_interview(
    interview_id: int,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> List[SubmissionSummary]:
    """
    List all code submissions for an interview (submission).

    Does NOT include source code or full test results.
    """
    service = _build_service(db)
    return service.list_submissions_for_interview(
        identity=identity,
        interview_id=interview_id,
    )
