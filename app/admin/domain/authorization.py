"""
Admin RBAC Authorization

Centralised authorization logic for admin domain operations.

Reuses:
- app.shared.auth_context.models.IdentityContext  (identity)
- app.shared.auth_context.models.AdminRole        (role enum)
- app.shared.auth_context.scope.enforce_organization_scope (tenant isolation)
- app.shared.errors.AuthorizationError             (error type)

This module adds *admin-domain-specific* checks on top of the shared primitives.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.shared.auth_context.models import AdminRole, IdentityContext
from app.shared.auth_context.scope import enforce_organization_scope
from app.shared.errors import AuthorizationError

from .entities import SUPER_ORG_ID

logger = logging.getLogger(__name__)


def authorize_admin_operation(
    identity: IdentityContext,
    *,
    operation: str,
    resource_org_id: int,
) -> None:
    """
    Gate-check that the calling admin may perform *operation* on resources
    belonging to *resource_org_id*.

    Rules (from REQUIREMENTS.md §3 / §5):
      • superadmin → all operations on all organisations
      • admin     → all CRUD on own organisation only
      • read_only → GET only on own organisation only

    Raises:
        AuthorizationError  – insufficient privilege
        (TenantIsolationViolation is raised by enforce_organization_scope
         if a non-superadmin tries cross-tenant access)
    """
    # 1.  read_only may only read
    if identity.admin_role == AdminRole.READ_ONLY and operation != "GET":
        raise AuthorizationError(
            message="Read-only admins cannot perform mutating operations",
            metadata={
                "user_id": identity.user_id,
                "admin_role": identity.admin_role.value,
                "operation": operation,
            },
        )

    # 2.  Enforce tenant isolation  (superadmin is pass-through)
    enforce_organization_scope(identity, resource_org_id)


def authorize_base_content_mutation(
    identity: IdentityContext,
) -> None:
    """
    Only superadmin may create/edit base content (org_id=1).

    Raises:
        AuthorizationError — if caller is not superadmin
    """
    if not identity.is_superadmin():
        raise AuthorizationError(
            message="Only superadmin can modify base (super-org) content",
            metadata={
                "user_id": identity.user_id,
                "admin_role": identity.admin_role.value if identity.admin_role else None,
            },
        )


def authorize_override_operation(
    identity: IdentityContext,
    *,
    base_content_org_id: int,
    override_org_id: int,
    operation: str,
) -> None:
    """
    Validate that an override operation is permitted.

    Rules:
      • Base content MUST belong to super org (org_id = 1).
      • Caller MUST have access to the override's organisation.
      • read_only may only read overrides.

    Raises:
        AuthorizationError — on any rule violation
    """
    if base_content_org_id != SUPER_ORG_ID:
        raise AuthorizationError(
            message="Overrides can only be created for super-org base content",
            metadata={
                "base_content_org_id": base_content_org_id,
                "expected_org_id": SUPER_ORG_ID,
            },
        )

    # Delegate standard operation + tenant check
    authorize_admin_operation(
        identity,
        operation=operation,
        resource_org_id=override_org_id,
    )
