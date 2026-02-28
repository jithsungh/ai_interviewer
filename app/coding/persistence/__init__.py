"""
Coding Persistence Submodule

Repository pattern implementations for code submission data access.
This is the ONLY layer that directly accesses coding tables.

Public interface:
- CodeSubmission, CodeExecutionResult (domain entities)
- CodeSubmissionRepository, CodeExecutionResultRepository (protocols)
- SqlCodeSubmissionRepository, SqlCodeExecutionResultRepository (implementations)
"""

from app.coding.persistence.entities import CodeExecutionResult, CodeSubmission
from app.coding.persistence.protocols import (
    CodeExecutionResultRepository,
    CodeSubmissionRepository,
)
from app.coding.persistence.repositories import (
    SqlCodeExecutionResultRepository,
    SqlCodeSubmissionRepository,
)

__all__ = [
    "CodeSubmission",
    "CodeExecutionResult",
    "CodeSubmissionRepository",
    "CodeExecutionResultRepository",
    "SqlCodeSubmissionRepository",
    "SqlCodeExecutionResultRepository",
]
