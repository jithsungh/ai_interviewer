"""
Coding API — Dependency Injection

Factory functions for constructing coding repositories bound to
a database session.  Follows the pattern established by
``app/evaluation/api/dependencies.py``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.coding.persistence.repositories import (
    SqlCodeExecutionResultRepository,
    SqlCodeSubmissionRepository,
)


def build_submission_repository(session: Session) -> SqlCodeSubmissionRepository:
    """Create a SqlCodeSubmissionRepository bound to the given DB session."""
    return SqlCodeSubmissionRepository(session)


def build_execution_result_repository(
    session: Session,
) -> SqlCodeExecutionResultRepository:
    """Create a SqlCodeExecutionResultRepository bound to the given DB session."""
    return SqlCodeExecutionResultRepository(session)
