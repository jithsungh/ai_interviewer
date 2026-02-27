"""
Candidate Repository

Data access layer for the candidates table.
Provides CRUD operations and query methods for candidate user management.
"""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.shared.errors import ConflictError, DatabaseError
from app.shared.observability import get_context_logger

from .models import Candidate

logger = get_context_logger(__name__)


class CandidateRepository:
    """
    Repository for candidate records.

    Candidate records extend the base user identity with profile
    data and plan information.

    All methods receive an injected SQLAlchemy Session.
    Transaction commit/rollback is the caller's responsibility.
    """

    def __init__(self, session: Session):
        self.session = session

    # ========================================================================
    # CREATE
    # ========================================================================

    def create(
        self,
        user_id: int,
        plan: str = "free",
        status: str = "active",
        profile_metadata: Optional[dict] = None,
    ) -> Candidate:
        """
        Create a new candidate record.

        Args:
            user_id: FK to users.id — must exist.
            plan: Candidate plan ('free', 'pro', 'prime'). Default 'free'.
            status: Initial status ('active', 'inactive', 'banned'). Default 'active'.
            profile_metadata: Optional JSONB profile data (full_name, phone, etc.).

        Returns:
            Created Candidate ORM instance (with id populated after flush).

        Raises:
            ConflictError: If user already has a candidate record.
            DatabaseError: On unexpected DB failure.
        """
        candidate = Candidate(
            user_id=user_id,
            plan=plan,
            status=status,
            profile_metadata=profile_metadata,
        )
        try:
            self.session.add(candidate)
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            err_str = str(exc.orig)
            if "candidates_user_id_key" in err_str:
                logger.warning(
                    "Duplicate candidate record for user",
                    event_type="persistence.candidate.duplicate",
                    metadata={"user_id": user_id},
                )
                raise ConflictError(
                    message="Candidate record already exists for this user",
                    metadata={"user_id": user_id},
                ) from exc
            logger.error(
                "Integrity error creating candidate",
                event_type="persistence.candidate.create_error",
                metadata={"error": err_str},
            )
            raise DatabaseError(
                message=f"Failed to create candidate: {exc}",
            ) from exc

        logger.info(
            "Candidate created",
            event_type="persistence.candidate.created",
            metadata={
                "candidate_id": candidate.id,
                "user_id": user_id,
                "plan": plan,
            },
        )
        return candidate

    # ========================================================================
    # READ
    # ========================================================================

    def get_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """
        Get candidate by primary key.

        Args:
            candidate_id: Candidate ID.

        Returns:
            Candidate or None if not found.
        """
        return (
            self.session.query(Candidate)
            .filter(Candidate.id == candidate_id)
            .first()
        )

    def find_by_user_id(self, user_id: int) -> Optional[Candidate]:
        """
        Find candidate record by user_id.

        Args:
            user_id: FK user ID.

        Returns:
            Candidate or None if user is not a candidate.
        """
        return (
            self.session.query(Candidate)
            .filter(Candidate.user_id == user_id)
            .first()
        )

    # ========================================================================
    # UPDATE
    # ========================================================================

    def update_profile(
        self,
        candidate_id: int,
        profile_metadata: dict,
    ) -> None:
        """
        Update candidate profile metadata.

        Merges the provided dict into existing profile_metadata.
        Only keys present in ``profile_metadata`` are overwritten;
        existing keys not in the argument are preserved.

        Args:
            candidate_id: Candidate ID.
            profile_metadata: Dict of profile fields to upsert.
        """
        candidate = (
            self.session.query(Candidate)
            .filter(Candidate.id == candidate_id)
            .first()
        )
        if candidate is None:
            return

        existing = candidate.profile_metadata or {}
        existing.update(profile_metadata)
        candidate.profile_metadata = existing
        # Mark JSONB column as modified so SQLAlchemy detects the change.
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(candidate, "profile_metadata")

    def update_status(self, candidate_id: int, new_status: str) -> None:
        """
        Update candidate status.

        Args:
            candidate_id: Candidate ID.
            new_status: New status ('active', 'inactive', 'banned').
        """
        self.session.query(Candidate).filter(
            Candidate.id == candidate_id
        ).update(
            {"status": new_status},
            synchronize_session="fetch",
        )
