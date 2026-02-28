"""
User Repository

Data access layer for the users table.
Provides CRUD operations and query methods for user identity management.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import exists, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.shared.errors import ConflictError, DatabaseError
from app.shared.observability import get_context_logger

from .models import User

logger = get_context_logger(__name__)


class UserRepository:
    """
    Repository for user identity records.

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
        name: str,
        email: str,
        password_hash: str,
        user_type: str,
        status: str = "active",
        token_version: int = 1,
    ) -> User:
        """
        Create a new user record.

        Args:
            name: Display name.
            email: Unique email address.
            password_hash: Bcrypt/argon2 password hash.
            user_type: 'admin' or 'candidate'.
            status: Initial status (default 'active').
            token_version: Initial token version (default 1).

        Returns:
            Created User ORM instance (with id populated after flush).

        Raises:
            ConflictError: If email already exists (UNIQUE violation).
            DatabaseError: On unexpected DB failure.
        """
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            user_type=user_type,
            status=status,
            token_version=token_version,
        )
        try:
            self.session.add(user)
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            if "users_email_key" in str(exc.orig):
                logger.warning(
                    "Duplicate email on user creation",
                    event_type="persistence.user.duplicate_email",
                    metadata={"email": email},
                )
                raise ConflictError(
                    message="Email already registered",
                    metadata={"email": email},
                ) from exc
            logger.error(
                "Integrity error creating user",
                event_type="persistence.user.create_error",
                metadata={"error": str(exc)},
            )
            raise DatabaseError(
                message=f"Failed to create user: {exc}",
            ) from exc

        logger.info(
            "User created",
            event_type="persistence.user.created",
            metadata={"user_id": user.id, "user_type": user_type},
        )
        return user

    # ========================================================================
    # READ
    # ========================================================================

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by primary key.

        Args:
            user_id: User ID.

        Returns:
            User or None if not found.
        """
        return self.session.query(User).filter(User.id == user_id).first()

    def find_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email (case-insensitive).

        Uses func.lower() for case-insensitive comparison,
        leveraging the UNIQUE index on email.

        Args:
            email: Email address to search.

        Returns:
            User or None if not found.
        """
        return (
            self.session.query(User)
            .filter(func.lower(User.email) == email.lower())
            .first()
        )

    def email_exists(self, email: str) -> bool:
        """
        Check if email is already registered.

        Efficient check using EXISTS subquery (no full model load).

        Args:
            email: Email address to check.

        Returns:
            True if email exists, False otherwise.
        """
        return self.session.query(
            exists().where(func.lower(User.email) == email.lower())
        ).scalar()

    # ========================================================================
    # UPDATE
    # ========================================================================

    def update_last_login(self, user_id: int) -> None:
        """
        Update last_login_at to current UTC timestamp.

        Args:
            user_id: User ID.
        """
        self.session.query(User).filter(User.id == user_id).update(
            {"last_login_at": datetime.now(timezone.utc)},
            synchronize_session="fetch",
        )

    def update_password(self, user_id: int, new_password_hash: str) -> None:
        """
        Update password hash.

        Args:
            user_id: User ID.
            new_password_hash: New bcrypt/argon2 hash.
        """
        self.session.query(User).filter(User.id == user_id).update(
            {"password_hash": new_password_hash},
            synchronize_session="fetch",
        )

    def update_status(self, user_id: int, new_status: str) -> None:
        """
        Update user status.

        Args:
            user_id: User ID.
            new_status: New status ('active', 'inactive', 'banned').
        """
        self.session.query(User).filter(User.id == user_id).update(
            {"status": new_status},
            synchronize_session="fetch",
        )

    def increment_token_version(self, user_id: int) -> None:
        """
        Atomically increment token_version.

        Uses SQL expression to prevent race conditions:
            SET token_version = token_version + 1

        Used for forced logout / invalidating all active JWTs.

        Args:
            user_id: User ID.
        """
        self.session.query(User).filter(User.id == user_id).update(
            {"token_version": User.token_version + 1},
            synchronize_session="fetch",
        )
