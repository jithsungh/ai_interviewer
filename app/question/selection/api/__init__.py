"""
Selection API Routes

Lightweight admin-facing endpoints for inspecting selection diagnostics
and adaptation audit logs. The primary selection flow is consumed
internally by the interview module — NOT via REST.

URL prefix: /api/v1/questions/selection (set via router_registry.py)

Endpoints:
    GET /adaptation-log/{submission_id}  — View adaptation decisions
    POST /preview                        — Preview selection (dry-run)

Auth: Requires admin JWT.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.persistence.postgres import get_db_session
from app.shared.auth_context.dependencies import require_admin
from app.shared.auth_context import IdentityContext
from app.shared.observability import get_context_logger

from app.question.selection.contracts import AdaptationDecision
from app.question.selection.persistence.adaptation_repository import (
    AdaptationLogRepository,
)

logger = get_context_logger(__name__)

router = APIRouter()


# ════════════════════════════════════════════════════════════════════════════
# Response Models
# ════════════════════════════════════════════════════════════════════════════


class AdaptationLogResponse(AdaptationDecision):
    """Adaptation log entry with record ID."""

    id: int


# ════════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════════


@router.get(
    "/adaptation-log/{submission_id}",
    response_model=List[AdaptationLogResponse],
    summary="Get adaptation log for a submission",
    description="Returns all difficulty adaptation decisions for an interview "
    "submission, ordered by exchange sequence. Admin only.",
)
def get_adaptation_log(
    submission_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> List[AdaptationLogResponse]:
    """Retrieve adaptation audit trail for a submission."""
    repo = AdaptationLogRepository(db)
    records = repo.get_by_submission(submission_id)

    return [
        AdaptationLogResponse(
            id=r.id,
            submission_id=r.submission_id,
            exchange_sequence_order=r.exchange_sequence_order,
            previous_difficulty=r.previous_difficulty,
            previous_score=float(r.previous_score) if r.previous_score else None,
            previous_question_id=r.previous_question_id,
            adaptation_rule=r.adaptation_rule,
            threshold_up=float(r.threshold_up) if r.threshold_up else None,
            threshold_down=float(r.threshold_down) if r.threshold_down else None,
            max_difficulty_jump=r.max_difficulty_jump,
            next_difficulty=r.next_difficulty,
            adaptation_reason=r.adaptation_reason,
            difficulty_changed=r.difficulty_changed,
            decided_at=r.decided_at,
            rule_version=r.rule_version,
        )
        for r in records
    ]
