"""
Unit tests for admin domain authorization.

Tests RBAC enforcement, tenant isolation, and override authorization rules.
All tests use IdentityContext from shared/auth_context — no duplication.
"""

import pytest
import time

from app.shared.auth_context.models import AdminRole, IdentityContext, UserType
from app.shared.errors import AuthorizationError, TenantIsolationViolation

from app.admin.domain.authorization import (
    authorize_admin_operation,
    authorize_base_content_mutation,
    authorize_override_operation,
)
from app.admin.domain.entities import SUPER_ORG_ID


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

def _now() -> int:
    return int(time.time())


def make_identity(
    user_id: int = 1,
    user_type: UserType = UserType.ADMIN,
    organization_id: int = 1,
    admin_role: AdminRole = AdminRole.ADMIN,
) -> IdentityContext:
    """Helper to build IdentityContext for tests."""
    now = _now()
    return IdentityContext(
        user_id=user_id,
        user_type=user_type,
        organization_id=organization_id if user_type == UserType.ADMIN else None,
        admin_role=admin_role if user_type == UserType.ADMIN else None,
        token_version=1,
        issued_at=now,
        expires_at=now + 3600,
    )


@pytest.fixture
def superadmin():
    return make_identity(user_id=1, organization_id=SUPER_ORG_ID, admin_role=AdminRole.SUPERADMIN)


@pytest.fixture
def tenant_admin():
    return make_identity(user_id=2, organization_id=5, admin_role=AdminRole.ADMIN)


@pytest.fixture
def read_only_admin():
    return make_identity(user_id=3, organization_id=5, admin_role=AdminRole.READ_ONLY)


# ─────────────────────────────────────────────────────────────────
# authorize_admin_operation
# ─────────────────────────────────────────────────────────────────

class TestAuthorizeAdminOperation:
    """Tests for the main RBAC gate-check."""

    def test_superadmin_can_access_any_org(self, superadmin):
        # Should not raise for any org
        authorize_admin_operation(superadmin, operation="POST", resource_org_id=99)

    def test_superadmin_can_read(self, superadmin):
        authorize_admin_operation(superadmin, operation="GET", resource_org_id=99)

    def test_admin_can_access_own_org(self, tenant_admin):
        authorize_admin_operation(tenant_admin, operation="POST", resource_org_id=5)

    def test_admin_cannot_access_other_org(self, tenant_admin):
        with pytest.raises(TenantIsolationViolation):
            authorize_admin_operation(tenant_admin, operation="GET", resource_org_id=99)

    def test_admin_can_mutate_own_org(self, tenant_admin):
        authorize_admin_operation(tenant_admin, operation="PUT", resource_org_id=5)

    def test_read_only_can_read_own_org(self, read_only_admin):
        authorize_admin_operation(read_only_admin, operation="GET", resource_org_id=5)

    def test_read_only_cannot_post(self, read_only_admin):
        with pytest.raises(AuthorizationError, match="Read-only"):
            authorize_admin_operation(read_only_admin, operation="POST", resource_org_id=5)

    def test_read_only_cannot_put(self, read_only_admin):
        with pytest.raises(AuthorizationError, match="Read-only"):
            authorize_admin_operation(read_only_admin, operation="PUT", resource_org_id=5)

    def test_read_only_cannot_delete(self, read_only_admin):
        with pytest.raises(AuthorizationError, match="Read-only"):
            authorize_admin_operation(read_only_admin, operation="DELETE", resource_org_id=5)

    def test_read_only_cannot_access_other_org(self, read_only_admin):
        """Read-only blocked on mutation before tenant check, but GET on other org still blocked."""
        with pytest.raises(TenantIsolationViolation):
            authorize_admin_operation(read_only_admin, operation="GET", resource_org_id=99)


# ─────────────────────────────────────────────────────────────────
# authorize_base_content_mutation
# ─────────────────────────────────────────────────────────────────

class TestAuthorizeBaseContentMutation:
    """Only superadmin may modify base (super-org) content."""

    def test_superadmin_allowed(self, superadmin):
        authorize_base_content_mutation(superadmin)  # No exception

    def test_admin_blocked(self, tenant_admin):
        with pytest.raises(AuthorizationError, match="superadmin"):
            authorize_base_content_mutation(tenant_admin)

    def test_read_only_blocked(self, read_only_admin):
        with pytest.raises(AuthorizationError, match="superadmin"):
            authorize_base_content_mutation(read_only_admin)


# ─────────────────────────────────────────────────────────────────
# authorize_override_operation
# ─────────────────────────────────────────────────────────────────

class TestAuthorizeOverrideOperation:
    """Override operations require base content in super org and caller access."""

    def test_admin_can_create_override_on_super_org_content(self, tenant_admin):
        authorize_override_operation(
            tenant_admin,
            base_content_org_id=SUPER_ORG_ID,
            override_org_id=5,
            operation="POST",
        )

    def test_admin_cannot_override_non_super_org_content(self, tenant_admin):
        with pytest.raises(AuthorizationError, match="super-org"):
            authorize_override_operation(
                tenant_admin,
                base_content_org_id=99,  # Not super org
                override_org_id=5,
                operation="POST",
            )

    def test_read_only_cannot_create_override(self, read_only_admin):
        with pytest.raises(AuthorizationError, match="Read-only"):
            authorize_override_operation(
                read_only_admin,
                base_content_org_id=SUPER_ORG_ID,
                override_org_id=5,
                operation="POST",
            )

    def test_read_only_can_read_override(self, read_only_admin):
        authorize_override_operation(
            read_only_admin,
            base_content_org_id=SUPER_ORG_ID,
            override_org_id=5,
            operation="GET",
        )

    def test_superadmin_can_override_for_any_org(self, superadmin):
        authorize_override_operation(
            superadmin,
            base_content_org_id=SUPER_ORG_ID,
            override_org_id=99,
            operation="POST",
        )

    def test_admin_cannot_override_for_other_org(self, tenant_admin):
        with pytest.raises(TenantIsolationViolation):
            authorize_override_operation(
                tenant_admin,
                base_content_org_id=SUPER_ORG_ID,
                override_org_id=99,  # Not their org
                operation="POST",
            )
