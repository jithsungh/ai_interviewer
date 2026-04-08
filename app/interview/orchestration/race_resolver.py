"""
Race Resolver — Concurrent Exchange Creation Protection

Uses Redis distributed locks to prevent duplicate exchange creation
when audio and code completion signals arrive simultaneously.

Reuses existing infrastructure:
- ``app.persistence.redis.locks.acquire_lock`` (context manager)
- ``app.persistence.redis.locks.create_interview_lock_key`` (key pattern)
- ``InterviewExchangeRepository.exists_for_sequence`` (duplicate check)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy.orm import Session

from app.interview.exchanges.repository import InterviewExchangeRepository
from app.interview.session.persistence.models import InterviewExchangeModel
from app.persistence.redis.locks import (
    LockAcquisitionError,
    acquire_lock,
    create_interview_lock_key,
)

logger = logging.getLogger(__name__)


class RaceResolver:
    """
    Resolves race conditions during exchange creation.

    Scenario: Audio silence detected at T=30.000s, code execution
    completes at T=30.001s. Both trigger exchange creation for the
    same sequence_order.

    Solution:
    1. Acquire Redis lock: ``interview:lock:{submission_id}:{sequence_order}``
    2. Check if exchange already exists (idempotent check)
    3. If exists → return existing exchange (second handler loses race)
    4. If not → proceed with creation (first handler wins race)
    5. Release lock automatically (context manager)
    """

    def __init__(self, db: Session, redis, lock_timeout: int = 10) -> None:
        self._db = db
        self._redis = redis
        self._lock_timeout = lock_timeout
        self._exchange_repo = InterviewExchangeRepository(db)

    @contextmanager
    def acquire_exchange_lock(
        self,
        submission_id: int,
        sequence_order: int,
    ):
        """
        Acquire distributed lock for exchange creation.

        Yields control to the caller while lock is held.
        Lock is released automatically on exit (success or failure).

        Args:
            submission_id: Interview submission ID.
            sequence_order: Exchange sequence number.

        Yields:
            None — lock is held during yield.

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout.
        """
        lock_key = create_interview_lock_key(submission_id, sequence_order)

        with acquire_lock(
            lock_key,
            timeout_seconds=self._lock_timeout,
            client=self._redis,
        ):
            logger.debug(
                "Exchange lock acquired",
                extra={
                    "submission_id": submission_id,
                    "sequence_order": sequence_order,
                },
            )
            yield

    def check_exchange_exists(
        self,
        submission_id: int,
        sequence_order: int,
    ) -> Optional[InterviewExchangeModel]:
        """
        Check if exchange already exists for this (submission, sequence) pair.

        Used after acquiring lock to detect if another handler already created
        the exchange (idempotent race resolution).

        Args:
            submission_id: Interview submission ID.
            sequence_order: Exchange sequence number.

        Returns:
            Existing exchange model if found, None otherwise.
        """
        return self._exchange_repo.get_by_submission_and_sequence(
            submission_id, sequence_order
        )

    def resolve_or_create(
        self,
        submission_id: int,
        sequence_order: int,
        create_fn,
    ) -> InterviewExchangeModel:
        """
        Acquire lock, check for existing exchange, create if not exists.

        This is the primary entry point for race-safe exchange creation.

        Args:
            submission_id: Interview submission ID.
            sequence_order: Exchange sequence number.
            create_fn: Callable that creates the exchange (called inside lock).
                Must return InterviewExchangeModel.

        Returns:
            Created or existing exchange model.

        Raises:
            LockAcquisitionError: If lock cannot be acquired.
            Any exceptions from create_fn.
        """
        try:
            with self.acquire_exchange_lock(submission_id, sequence_order):
                # Idempotent check: exchange may already exist
                existing = self.check_exchange_exists(submission_id, sequence_order)
                if existing is not None:
                    logger.info(
                        "Exchange already exists (race resolved: idempotent)",
                        extra={
                            "submission_id": submission_id,
                            "sequence_order": sequence_order,
                            "exchange_id": existing.id,
                        },
                    )
                    return existing

                # Create exchange (caller provides creation logic)
                return create_fn()
        except LockAcquisitionError:
            logger.warning(
                "Exchange lock acquisition failed; falling back to DB constraints",
                extra={
                    "submission_id": submission_id,
                    "sequence_order": sequence_order,
                },
                exc_info=True,
            )
            existing = self.check_exchange_exists(submission_id, sequence_order)
            if existing is not None:
                return existing
            return create_fn()
