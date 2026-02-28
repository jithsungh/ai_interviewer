"""
Admin Repository

Data access layer for the admins table.
Provides CRUD operations and query methods for admin user management.
"""

from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.shared.errors import ConflictError, DatabaseError
from app.shared.observability import get_context_logger

from .models import Admin

logger = get_context_logger(__name__)


class AdminRepository:
    """
    Repository for admin records.

    Admin records extend the base user identity with organization
    membership and role information.

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
        organization_id: int,
        role: str,
        status: str = "active",
    ) -> Admin:
        """
        Create a new admin record.

        Args:
            user_id: FK to users.id — must exist.
            organization_id: FK to organizations.id — must exist and be active.
            role: Admin role ('superadmin', 'admin', 'read_only').
            status: Initial status (default 'active').

        Returns:
            Created Admin ORM instance (with id populated after flush).

        Raises:
            ConflictError: If user already has an admin record for this org.
            DatabaseError: On unexpected DB failure.
        """
        admin = Admin(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            status=status,
        )
        try:
            self.session.add(admin)
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            err_str = str(exc.orig)
            if "admins_user_id_organization_id_key" in err_str:
                logger.warning(
                    "Duplicate admin record for user+org",
                    event_type="persistence.admin.duplicate",
                    metadata={
                        "user_id": user_id,
                        "organization_id": organization_id,
                    },
                )
                raise ConflictError(
                    message="Admin record already exists for this user and organization",
                    metadata={
                        "user_id": user_id,
                        "organization_id": organization_id,
                    },
                ) from exc
            logger.error(
                "Integrity error creating admin",
                event_type="persistence.admin.create_error",
                metadata={"error": err_str},
            )
            raise DatabaseError(
                message=f"Failed to create admin: {exc}",
            ) from exc

        logger.info(
            "Admin created",
            event_type="persistence.admin.created",
            metadata={
                "admin_id": admin.id,
                "user_id": user_id,
                "organization_id": organization_id,
                "role": role,
            },
        )
        return admin

    # ========================================================================
    # READ
    # ========================================================================

    def get_by_id(self, admin_id: int) -> Optional[Admin]:
        """
        Get admin by primary key.

        Args:
            admin_id: Admin ID.

        Returns:
            Admin or None if not found.
        """
        return self.session.query(Admin).filter(Admin.id == admin_id).first()

    def find_by_user_id(self, user_id: int) -> Optional[Admin]:
        """
        Find admin record by user_id.

        Args:
            user_id: FK user ID.

        Returns:
            Admin or None if user is not an admin.
        """
        return (
            self.session.query(Admin).filter(Admin.user_id == user_id).first()
        )

    def list_by_organization(self, organization_id: int) -> List[Admin]:
        """
        List all admins for an organization.

        Args:
            organization_id: Organization ID.

        Returns:
            List of Admin records (may be empty).
        """
        return (
            self.session.query(Admin)
            .filter(Admin.organization_id == organization_id)
            .order_by(Admin.created_at)
            .all()
        )

    # ========================================================================
    # UPDATE
    # ========================================================================

    def update_role(self, admin_id: int, new_role: str) -> None:
        """
        Update admin role.

        Args:
            admin_id: Admin ID.
            new_role: New role ('superadmin', 'admin', 'read_only').
        """
        self.session.query(Admin).filter(Admin.id == admin_id).update(
            {"role": new_role},
            synchronize_session="fetch",
        )

    def update_status(self, admin_id: int, new_status: str) -> None:
        """
        Update admin status.

        Args:
            admin_id: Admin ID.
            new_status: New status ('active', 'inactive', 'suspended').
        """
        self.session.query(Admin).filter(Admin.id == admin_id).update(
            {"status": new_status},
            synchronize_session="fetch",
        )
