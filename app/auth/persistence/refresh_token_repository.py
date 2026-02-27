"""
Refresh Token Repository

Data access layer for the refresh_tokens table.
Provides CRUD operations and query methods for JWT refresh token management.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.shared.errors import ConflictError, DatabaseError
from app.shared.observability import get_context_logger

from .models import RefreshToken

logger = get_context_logger(__name__)


class RefreshTokenRepository:
    """
    Repository for refresh token records.

    Tokens are stored as SHA-256 hashes — the raw token value is never persisted.

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
        token_hash: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RefreshToken:
        """
        Store a new refresh token (hashed).

        Args:
            user_id: FK to users.id.
            token_hash: SHA-256 hash of the raw refresh token.
            expires_at: Expiration timestamp (timezone-aware).
            device_info: Optional user-agent / device fingerprint.
            ip_address: Optional client IP.

        Returns:
            Created RefreshToken ORM instance.

        Raises:
            ConflictError: If token_hash already exists (UNIQUE violation).
            DatabaseError: On unexpected DB failure.
        """
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        try:
            self.session.add(token)
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            err_str = str(exc.orig)
            if "refresh_tokens_token_hash_unique" in err_str:
                logger.warning(
                    "Duplicate refresh token hash",
                    event_type="persistence.refresh_token.duplicate_hash",
                    metadata={"user_id": user_id},
                )
                raise ConflictError(
                    message="Refresh token hash collision",
                    metadata={"user_id": user_id},
                ) from exc
            logger.error(
                "Integrity error creating refresh token",
                event_type="persistence.refresh_token.create_error",
                metadata={"error": err_str},
            )
            raise DatabaseError(
                message=f"Failed to create refresh token: {exc}",
            ) from exc

        logger.info(
            "Refresh token stored",
            event_type="persistence.refresh_token.created",
            metadata={"user_id": user_id, "token_id": token.id},
        )
        return token

    # ========================================================================
    # READ
    # ========================================================================

    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """
        Find a refresh token by its hash.

        Returns the token regardless of revocation / expiration status —
        the domain layer decides whether to accept it.

        Args:
            token_hash: SHA-256 hash of the raw token.

        Returns:
            RefreshToken or None.
        """
        return (
            self.session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def list_active_for_user(self, user_id: int) -> List[RefreshToken]:
        """
        List active (non-revoked, non-expired) tokens for a user.

        Args:
            user_id: User ID.

        Returns:
            List of active RefreshToken records.
        """
        now = datetime.now(timezone.utc)
        return (
            self.session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.issued_at.desc())
            .all()
        )

    # ========================================================================
    # UPDATE (Revocation)
    # ========================================================================

    def revoke(self, token_id: int, reason: str) -> None:
        """
        Revoke a specific refresh token.

        Idempotent — succeeds even if already revoked.

        Args:
            token_id: Refresh token ID.
            reason: Revocation reason (e.g. 'logout', 'rotation', 'password_change').
        """
        now = datetime.now(timezone.utc)
        self.session.query(RefreshToken).filter(
            RefreshToken.id == token_id,
            RefreshToken.revoked_at.is_(None),
        ).update(
            {"revoked_at": now, "revoked_reason": reason},
            synchronize_session="fetch",
        )

    def revoke_all_for_user(self, user_id: int, reason: str) -> int:
        """
        Revoke all non-revoked refresh tokens for a user.

        Used on password change, suspicious activity, or admin action.

        Args:
            user_id: User ID.
            reason: Revocation reason.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        count = (
            self.session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .update(
                {"revoked_at": now, "revoked_reason": reason},
                synchronize_session="fetch",
            )
        )
        if count:
            logger.info(
                "Revoked all tokens for user",
                event_type="persistence.refresh_token.revoke_all",
                metadata={"user_id": user_id, "count": count, "reason": reason},
            )
        return count

    # ========================================================================
    # DELETE (Maintenance)
    # ========================================================================

    def cleanup_expired(self, grace_days: int = 7) -> int:
        """
        Delete expired tokens that are at least ``grace_days`` old.

        Intended to be called by a periodic maintenance task (e.g. daily).

        Args:
            grace_days: Minimum days past expiration before deletion.
                        Default 7 days.

        Returns:
            Number of tokens deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
        count = (
            self.session.query(RefreshToken)
            .filter(RefreshToken.expires_at < cutoff)
            .delete(synchronize_session="fetch")
        )
        if count:
            logger.info(
                "Expired tokens cleaned up",
                event_type="persistence.refresh_token.cleanup",
                metadata={"deleted": count, "grace_days": grace_days},
            )
        return count
