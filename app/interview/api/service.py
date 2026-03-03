"""
Interview API Service — Business Logic Layer

Orchestrates read operations for the interview API endpoints.
Delegates to the InterviewQueryRepository for data access.

Does NOT handle state transitions (→ SessionService).
Does NOT handle exchange creation (→ ExchangeCoordinator).
Does NOT handle WebSocket events (→ RealtimeEventHandler).
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.interview.api.contracts import (
    ExchangeItemDTO,
    ExchangeListResponse,
    SectionProgressDTO,
    SectionProgressResponse,
)
from app.interview.persistence.repository import InterviewQueryRepository
from app.shared.errors import NotFoundError

logger = logging.getLogger(__name__)


class InterviewApiService:
    """
    Read-only service for the interview REST API.

    Provides:
    - Exchange listing with section filtering
    - Section-level progress breakdown
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = InterviewQueryRepository(db)

    # ────────────────────────────────────────────────────────────
    # Exchange Listing
    # ────────────────────────────────────────────────────────────

    def list_exchanges(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
        section: Optional[str] = None,
        include_responses: bool = True,
    ) -> ExchangeListResponse:
        """
        List exchanges for a submission.

        Args:
            submission_id: Submission ID.
            candidate_id: If provided, validates ownership (candidate path).
                          If None, allows any submission (admin path).
            section: Optional section name filter.
            include_responses: Whether to include response data.

        Returns:
            ExchangeListResponse with exchange DTOs.

        Raises:
            NotFoundError: Submission does not exist or not owned by candidate.
        """
        # Verify access
        if candidate_id is not None:
            self._repo.get_submission_for_candidate(submission_id, candidate_id)
        else:
            self._repo.get_submission_by_id(submission_id)

        # Fetch exchanges
        exchanges = self._repo.list_exchanges(
            submission_id=submission_id,
            section=section,
            include_responses=include_responses,
        )

        exchange_dtos = [
            ExchangeItemDTO.from_model(ex, include_responses=include_responses)
            for ex in exchanges
        ]

        return ExchangeListResponse(
            submission_id=submission_id,
            exchanges=exchange_dtos,
            total_exchanges=len(exchange_dtos),
        )

    # ────────────────────────────────────────────────────────────
    # Section Progress
    # ────────────────────────────────────────────────────────────

    def get_progress(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
    ) -> SectionProgressResponse:
        """
        Get section-level progress for a submission.

        Args:
            submission_id: Submission ID.
            candidate_id: If provided, validates ownership (candidate path).
                          If None, allows any submission (admin path).

        Returns:
            SectionProgressResponse with per-section breakdown.

        Raises:
            NotFoundError: Submission does not exist or not owned by candidate.
        """
        # Verify access
        if candidate_id is not None:
            self._repo.get_submission_for_candidate(submission_id, candidate_id)

        progress_data = self._repo.get_section_progress(submission_id)

        sections = [
            SectionProgressDTO(**s) for s in progress_data.get("sections", [])
        ]

        return SectionProgressResponse(
            submission_id=progress_data["submission_id"],
            overall_progress=progress_data["overall_progress"],
            sections=sections,
        )
