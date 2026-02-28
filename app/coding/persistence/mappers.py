"""
Coding Persistence Mappers — Bidirectional ORM ↔ entity conversion

Keeps the domain / execution layer free of SQLAlchemy dependencies.
Follows the pattern established by admin/persistence/mappers.py.

References:
- admin/persistence/mappers.py (pattern reference)
- persistence/REQUIREMENTS.md §4 (ORM → entity mapping)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.coding.persistence.entities import CodeExecutionResult, CodeSubmission
from app.coding.persistence.models import (
    CodeExecutionResultModel,
    CodeSubmissionModel,
)


# ---------------------------------------------------------------------------
# CodeSubmission
# ---------------------------------------------------------------------------

def submission_model_to_entity(m: CodeSubmissionModel) -> CodeSubmission:
    """Convert an ORM ``CodeSubmissionModel`` to a domain ``CodeSubmission``."""
    return CodeSubmission(
        id=m.id,
        interview_exchange_id=m.interview_exchange_id,
        coding_problem_id=m.coding_problem_id,
        language=m.language,
        source_code=m.source_code,
        execution_status=m.execution_status,
        score=Decimal(str(m.score)) if m.score is not None else None,
        execution_time_ms=m.execution_time_ms,
        memory_kb=m.memory_kb,
        compiler_output=None,  # Not stored on code_submissions table
        submitted_at=m.submitted_at,
        executed_at=m.executed_at,
        created_at=m.created_at,
    )


def submission_entity_to_model(
    e: CodeSubmission,
    model: Optional[CodeSubmissionModel] = None,
) -> CodeSubmissionModel:
    """
    Convert a domain ``CodeSubmission`` to an ORM model.

    If *model* is provided, updates it in place (for UPDATE operations).
    Otherwise creates a new model instance (for INSERT).
    """
    if model is None:
        model = CodeSubmissionModel()

    model.interview_exchange_id = e.interview_exchange_id
    model.coding_problem_id = e.coding_problem_id
    model.language = e.language
    model.source_code = e.source_code
    model.execution_status = e.execution_status
    model.score = e.score
    model.execution_time_ms = e.execution_time_ms
    model.memory_kb = e.memory_kb
    model.submitted_at = e.submitted_at
    model.executed_at = e.executed_at
    return model


# ---------------------------------------------------------------------------
# CodeExecutionResult
# ---------------------------------------------------------------------------

def result_model_to_entity(m: CodeExecutionResultModel) -> CodeExecutionResult:
    """Convert an ORM ``CodeExecutionResultModel`` to a domain entity."""
    return CodeExecutionResult(
        id=m.id,
        code_submission_id=m.code_submission_id,
        test_case_id=m.test_case_id,
        passed=m.passed,
        actual_output=m.actual_output,
        runtime_ms=m.runtime_ms,
        memory_kb=m.memory_kb,
        exit_code=m.exit_code,
        compiler_output=m.compiler_output,
        runtime_output=m.runtime_output,
        feedback=m.feedback,
        created_at=m.created_at,
    )


def result_entity_to_model(
    e: CodeExecutionResult,
    model: Optional[CodeExecutionResultModel] = None,
) -> CodeExecutionResultModel:
    """
    Convert a domain ``CodeExecutionResult`` to an ORM model.

    If *model* is provided, updates it in place.
    Otherwise creates a new instance.
    """
    if model is None:
        model = CodeExecutionResultModel()

    model.code_submission_id = e.code_submission_id
    model.test_case_id = e.test_case_id
    model.passed = e.passed
    model.actual_output = e.actual_output
    model.runtime_ms = e.runtime_ms
    model.memory_kb = e.memory_kb
    model.exit_code = e.exit_code
    model.compiler_output = e.compiler_output
    model.runtime_output = e.runtime_output
    model.feedback = e.feedback
    return model
