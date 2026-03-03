"""
Interview Persistence — Dedicated Repository Layer

Provides read-optimised queries for the interview API layer.
Delegates writes to existing sub-module repositories:
- ``SubmissionRepository``           → app.interview.session.persistence.repository
- ``InterviewExchangeRepository``    → app.interview.exchanges.repository

This module adds:
- ``InterviewQueryRepository``   — read queries for exchanges, progress, admin listing
- Model re-exports for convenience

Architectural Invariants:
- NO business logic (belongs in domain/orchestration)
- NO direct DB writes (delegates to sub-module repositories)
- NO cross-module persistence access
- Reuses existing ORM models (no duplication)
"""

from app.interview.persistence.repository import InterviewQueryRepository

__all__ = ["InterviewQueryRepository"]
