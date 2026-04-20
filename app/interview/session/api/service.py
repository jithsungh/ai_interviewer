"""
Session Service

Orchestrates state transitions, Redis session sync, and distributed locking
for interview submissions.
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.interview.session.contracts.schemas import (
    InterviewSessionDTO,
    InterviewSessionDetailDTO,
)
from app.interview.session.domain.state_machine import (
    StateTransitionError,
    SubmissionStatus,
)
from app.interview.session.persistence.repository import SubmissionRepository
from app.interview.session.expiry.service import SubmissionExpiryService
from app.evaluation.aggregation.service import AggregationService
from app.persistence.redis.locks import (
    LockAcquisitionError,
    acquire_lock,
    create_session_lock_key,
)
from app.shared.errors import ValidationError as AppValidationError

logger = logging.getLogger(__name__)

# How long the session snapshot lives in Redis (seconds).
_SESSION_TTL_SECONDS: int = 3600


class SessionService:
    """High-level interview session operations."""

    def __init__(self, db: Session, redis) -> None:
        self._db = db
        self._redis = redis
        self._repo = SubmissionRepository(db)

    # ────────────────────────────────────────────────────────────
    # Transitions
    # ────────────────────────────────────────────────────────────

    def start_interview(
        self,
        submission_id: int,
        candidate_id: int,
        consent_accepted: bool,
    ) -> Tuple[InterviewSessionDTO, bool]:
        """
        Start an interview: pending → in_progress.

        Raises:
            AppValidationError: If ``consent_accepted`` is ``False``.
            StateTransitionError: If the transition is forbidden.
        """
        if not consent_accepted:
            raise AppValidationError("Candidate consent is required to start the interview")

        lock_key = create_session_lock_key(submission_id)
        with self._optional_session_lock(lock_key):
            sub, transitioned = self._repo.transition_to_in_progress(
                submission_id,
                candidate_id,
                actor=f"candidate:{candidate_id}",
            )

        self._sync_redis(sub)
        dto = InterviewSessionDTO.from_model(sub)
        return dto, transitioned

    def complete_interview(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
    ) -> Tuple[InterviewSessionDTO, bool]:
        """in_progress → completed. Also triggers score calculation and aggregation."""
        lock_key = create_session_lock_key(submission_id)
        actor = f"candidate:{candidate_id}" if candidate_id is not None else "system:complete"
        with self._optional_session_lock(lock_key):
            sub, transitioned = self._repo.transition_to_completed(
                submission_id,
                candidate_id,
                actor=actor,
            )

        self._sync_redis(sub)
        
        # Trigger aggregation in background if submission was successfully transitioned
        if transitioned:
            try:
                thread = threading.Thread(
                    target=self._aggregate_and_update_score,
                    args=(submission_id,),
                    daemon=True,
                )
                thread.start()
            except Exception as e:
                # Log but don't fail if background aggregation fails
                logger.warning(
                    "Failed to trigger background aggregation",
                    extra={"submission_id": submission_id, "error": str(e)},
                )
        
        dto = InterviewSessionDTO.from_model(sub)
        return dto, transitioned

    def _aggregate_and_update_score(self, submission_id: int) -> None:
        """Background task to evaluate exchanges and calculate final_score.
        
        Steps:
            1. Evaluate all exchanges that don't have final evaluations
            2. Aggregate the evaluations into an interview result
            3. Update submission with final_score
        """
        try:
            logger.info(
                f"Starting background evaluation and aggregation for submission {submission_id}"
            )
            
            # Create a new DB session and event loop for the background task
            from app.persistence.postgres.session import SessionLocal
            from app.interview.session.persistence.models import InterviewSubmissionModel
            from app.evaluation.scoring.service import EvaluatorType, ScoringService
            import asyncio
            from sqlalchemy import text
            
            db = SessionLocal()
            
            try:
                # Create an event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Step 1: Evaluate all exchanges that don't have final evaluations
                    logger.info(f"Step 1: Evaluating exchanges for submission {submission_id}")
                    
                    exchange_rows = db.execute(
                        text(
                            "SELECT ie.id "
                            "FROM interview_exchanges ie "
                            "WHERE ie.interview_submission_id = :sid "
                            "ORDER BY ie.sequence_order"
                        ),
                        {"sid": submission_id},
                    ).fetchall()
                    
                    if not exchange_rows:
                        logger.warning(
                            f"No exchanges found for submission {submission_id}"
                        )
                        return
                    
                    scoring_service = ScoringService(db=db)
                    evaluated_count = 0
                    
                    for row in exchange_rows:
                        exchange_id = row.id
                        
                        try:
                            # Score the exchange
                            loop.run_until_complete(
                                scoring_service.score_exchange(
                                    interview_exchange_id=exchange_id,
                                    evaluator_type=EvaluatorType.AI,
                                    force_rescore=False,
                                )
                            )
                            evaluated_count += 1
                            logger.debug(
                                f"Exchange {exchange_id} evaluated successfully"
                            )
                        except Exception as e:
                            # Log and continue if single exchange fails
                            logger.warning(
                                f"Failed to evaluate exchange {exchange_id}: {str(e)}"
                            )
                    
                    if evaluated_count == 0:
                        logger.error(
                            f"No exchanges were successfully evaluated for submission {submission_id}"
                        )
                        return
                    
                    logger.info(
                        f"Step 1 complete: {evaluated_count} exchanges evaluated"
                    )
                    
                    # Step 2: Aggregate the evaluations
                    logger.info(f"Step 2: Aggregating results for submission {submission_id}")
                    
                    agg_service = AggregationService(db=db)
                    result_data = loop.run_until_complete(
                        agg_service.aggregate_interview_result(
                            submission_id=submission_id,
                            generated_by="system:completion",
                        )
                    )
                    
                    logger.info(
                        f"Step 2 complete: Aggregation successful for submission {submission_id}"
                    )
                    
                    # Step 3: Update the submission with the calculated final_score
                    logger.info(f"Step 3: Updating submission with final_score")
                    
                    sub = db.query(InterviewSubmissionModel).filter(
                        InterviewSubmissionModel.id == submission_id
                    ).first()
                    
                    if sub:
                        sub.final_score = result_data.normalized_score
                        db.commit()
                        logger.info(
                            f"Final score {result_data.normalized_score} persisted for submission {submission_id}"
                        )
                    else:
                        logger.error(
                            f"Submission {submission_id} not found when trying to update final_score"
                        )
                        
                finally:
                    loop.close()
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(
                f"Error during background evaluation/aggregation for submission {submission_id}: {str(e)}",
                exc_info=True,
            )

    def expire_interview(
        self,
        submission_id: int,
    ) -> Tuple[InterviewSessionDTO, bool]:
        """in_progress → expired (system-initiated)."""
        lock_key = create_session_lock_key(submission_id)
        with self._optional_session_lock(lock_key):
            sub, transitioned = self._repo.transition_to_expired(
                submission_id,
                actor="system:expiry",
            )

        self._sync_redis(sub)
        dto = InterviewSessionDTO.from_model(sub)
        return dto, transitioned

    def cancel_interview(
        self,
        submission_id: int,
        admin_id: int,
        reason: Optional[str] = None,
    ) -> Tuple[InterviewSessionDTO, bool]:
        """pending|in_progress → cancelled (admin only)."""
        lock_key = create_session_lock_key(submission_id)
        with self._optional_session_lock(lock_key):
            sub, transitioned = self._repo.transition_to_cancelled(
                submission_id,
                actor=f"admin:{admin_id}",
            )

        if transitioned:
            logger.info(
                "Interview cancelled",
                extra={
                    "submission_id": submission_id,
                    "admin_id": admin_id,
                    "reason": reason,
                },
            )

        self._sync_redis(sub)
        dto = InterviewSessionDTO.from_model(sub)
        return dto, transitioned

    def review_interview(
        self,
        submission_id: int,
        admin_id: int,
        review_notes: Optional[str] = None,
    ) -> Tuple[InterviewSessionDTO, bool]:
        """completed|expired|cancelled → reviewed (admin only)."""
        lock_key = create_session_lock_key(submission_id)
        with self._optional_session_lock(lock_key):
            sub, transitioned = self._repo.transition_to_reviewed(
                submission_id,
                actor=f"admin:{admin_id}",
            )

        if transitioned:
            logger.info(
                "Interview reviewed",
                extra={
                    "submission_id": submission_id,
                    "admin_id": admin_id,
                    "review_notes": review_notes,
                },
            )

        self._sync_redis(sub)
        dto = InterviewSessionDTO.from_model(sub)
        return dto, transitioned

    # ────────────────────────────────────────────────────────────
    # Read
    # ────────────────────────────────────────────────────────────

    def get_session_status(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
    ) -> InterviewSessionDetailDTO:
        """
        Return full session status with exchanges.

        If *candidate_id* is provided the query is scoped to that candidate;
        otherwise any submission is returned (admin path).
        """
        if candidate_id is not None:
            sub = self._repo.get_by_id_for_candidate(submission_id, candidate_id)
        else:
            sub = self._repo.get_by_id(submission_id)

        return InterviewSessionDetailDTO.from_model(sub)

    def expire_overdue_submissions(
        self,
        *,
        actor: str,
        limit: int = 500,
    ) -> int:
        """Bulk expire in-progress submissions whose scheduled_end has passed."""
        expiry_service = SubmissionExpiryService(self._db)
        return expiry_service.expire_overdue_submissions(actor=actor, limit=limit)

    # ────────────────────────────────────────────────────────────
    # Redis sync
    # ────────────────────────────────────────────────────────────

    def _sync_redis(self, sub: object) -> None:
        """Push the latest status snapshot to Redis for runtime reads."""
        key = f"interview_session:{sub.id}"
        payload = json.dumps(
            {
                "submission_id": sub.id,
                "status": sub.status,
                "candidate_id": sub.candidate_id,
                "started_at": (
                    sub.started_at.isoformat() if getattr(sub, "started_at", None) else None
                ),
                "updated_at": (
                    sub.updated_at.isoformat() if getattr(sub, "updated_at", None) else None
                ),
                "version": getattr(sub, "version", None),
            },
            default=str,
        )
        try:
            self._redis.set(key, payload, ex=_SESSION_TTL_SECONDS)
        except Exception:
            logger.warning("Failed to sync session to Redis", exc_info=True)

    @contextmanager
    def _optional_session_lock(self, lock_key: str):
        """
        Best-effort lock wrapper.

        DB constraints + optimistic versioning remain the source of correctness,
        so lock acquisition failure degrades gracefully instead of failing the request.
        """
        try:
            with acquire_lock(lock_key, client=self._redis):
                yield
        except LockAcquisitionError:
            logger.warning(
                "Session lock acquisition failed; proceeding with DB-enforced concurrency",
                extra={"lock_key": lock_key},
                exc_info=True,
            )
            yield
