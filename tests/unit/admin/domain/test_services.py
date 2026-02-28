"""
Unit tests for admin domain services.

All repository dependencies are mocked. Tests cover:
- Template CRUD with versioning invariant
- Rubric creation with weight validation
- Window creation with overlap detection
- Override management
- RBAC enforcement throughout
- Edge cases and error paths
"""

import pytest
import time
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call

from app.shared.auth_context.models import AdminRole, IdentityContext, UserType
from app.shared.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    TemplateImmutabilityViolation,
    TenantIsolationViolation,
    ValidationError,
)

from app.admin.domain.entities import (
    SUPER_ORG_ID,
    ContentType,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    Question,
    QuestionType,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRubric,
    TemplateScope,
    Topic,
    Window,
    WindowRoleTemplate,
)
from app.admin.domain.services import (
    CodingProblemService,
    QuestionService,
    RoleService,
    RubricService,
    TemplateService,
    TopicService,
    WindowService,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════

def _now() -> int:
    return int(time.time())


def make_identity(
    user_id: int = 1,
    organization_id: int = SUPER_ORG_ID,
    admin_role: AdminRole = AdminRole.SUPERADMIN,
) -> IdentityContext:
    now = _now()
    return IdentityContext(
        user_id=user_id,
        user_type=UserType.ADMIN,
        organization_id=organization_id,
        admin_role=admin_role,
        token_version=1,
        issued_at=now,
        expires_at=now + 3600,
    )


def make_template(**overrides) -> Template:
    defaults = dict(
        id=1,
        name="Test Template",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=SUPER_ORG_ID,
        template_structure={"sections": []},
        rules=None,
        total_estimated_time_minutes=60,
        version=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Template(**defaults)


def make_rubric(**overrides) -> Rubric:
    defaults = dict(
        id=1,
        organization_id=SUPER_ORG_ID,
        name="Test Rubric",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        schema=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Rubric(**defaults)


def make_dimension(rubric_id=1, weight="0.5", order=0, **overrides) -> RubricDimension:
    defaults = dict(
        id=None,
        rubric_id=rubric_id,
        dimension_name=f"Dim {order}",
        description="Dim desc",
        max_score=Decimal("10"),
        weight=Decimal(weight),
        criteria=None,
        sequence_order=order,
    )
    defaults.update(overrides)
    return RubricDimension(**defaults)


def make_role(**overrides) -> Role:
    defaults = dict(
        id=1,
        name="Backend Engineer",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=SUPER_ORG_ID,
    )
    defaults.update(overrides)
    return Role(**defaults)


def make_window(**overrides) -> Window:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        organization_id=5,
        admin_id=42,
        name="Test Window",
        scope=InterviewScope.GLOBAL,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=15),
        timezone="UTC",
        max_allowed_submissions=None,
        allow_after_end_time=False,
        allow_resubmission=False,
    )
    defaults.update(overrides)
    return Window(**defaults)


# ─── Mock repos ───────────────────────────────────────────────────

def mock_repos():
    """Create a dict of all mocked repository dependencies."""
    return {
        "template_repo": MagicMock(),
        "rubric_repo": MagicMock(),
        "role_repo": MagicMock(),
        "topic_repo": MagicMock(),
        "question_repo": MagicMock(),
        "problem_repo": MagicMock(),
        "window_repo": MagicMock(),
        "submission_repo": MagicMock(),
        "override_repo": MagicMock(),
        "audit_repo": MagicMock(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TemplateService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTemplateService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.template_repo = repos["template_repo"]
        self.submission_repo = repos["submission_repo"]
        self.override_repo = repos["override_repo"]
        self.rubric_repo = repos["rubric_repo"]
        self.role_repo = repos["role_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = TemplateService(
            template_repo=self.template_repo,
            submission_repo=self.submission_repo,
            override_repo=self.override_repo,
            rubric_repo=self.rubric_repo,
            role_repo=self.role_repo,
            audit_repo=self.audit_repo,
        )
        self.superadmin = make_identity(admin_role=AdminRole.SUPERADMIN, organization_id=SUPER_ORG_ID)
        self.tenant_admin = make_identity(user_id=2, admin_role=AdminRole.ADMIN, organization_id=5)
        self.read_only = make_identity(user_id=3, admin_role=AdminRole.READ_ONLY, organization_id=5)

    # ── get_template ──────────────────────────────────────────────

    def test_get_template_success(self):
        template = make_template()
        self.template_repo.get_by_id.return_value = template

        result = self.service.get_template(1, self.superadmin)
        assert result.id == 1
        self.template_repo.get_by_id.assert_called_once_with(1)

    def test_get_template_not_found(self):
        self.template_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            self.service.get_template(999, self.superadmin)

    def test_get_template_tenant_isolation(self):
        """Tenant admin cannot see a template from another org (not super-org)."""
        template = make_template(organization_id=99)
        self.template_repo.get_by_id.return_value = template

        with pytest.raises(NotFoundError):
            self.service.get_template(1, self.tenant_admin)

    def test_get_template_tenant_can_see_super_org(self):
        """Tenant admin CAN see super-org content."""
        template = make_template(organization_id=SUPER_ORG_ID)
        self.template_repo.get_by_id.return_value = template

        result = self.service.get_template(1, self.tenant_admin)
        assert result.id == 1

    # ── create_template ───────────────────────────────────────────

    def test_create_template_superadmin_base(self):
        template = make_template(id=None, organization_id=SUPER_ORG_ID)
        self.template_repo.exists_with_name.return_value = False
        self.template_repo.create.return_value = make_template(id=10)

        result = self.service.create_template(template, self.superadmin)
        assert result.id == 10
        self.audit_repo.log.assert_called_once()

    def test_create_template_duplicate_name_fails(self):
        template = make_template(id=None, organization_id=SUPER_ORG_ID)
        self.template_repo.exists_with_name.return_value = True

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_template(template, self.superadmin)

    def test_create_template_tenant_admin_own_org(self):
        template = make_template(id=None, organization_id=5)
        self.template_repo.exists_with_name.return_value = False
        self.template_repo.create.return_value = make_template(id=20, organization_id=5)

        result = self.service.create_template(template, self.tenant_admin)
        assert result.id == 20

    def test_create_base_template_blocked_for_tenant_admin(self):
        """Non-superadmin cannot create content in super-org."""
        template = make_template(id=None, organization_id=SUPER_ORG_ID)
        self.template_repo.exists_with_name.return_value = False

        with pytest.raises(AuthorizationError, match="superadmin"):
            self.service.create_template(template, self.tenant_admin)

    def test_create_template_read_only_blocked(self):
        template = make_template(id=None, organization_id=5)

        with pytest.raises(AuthorizationError, match="Read-only"):
            self.service.create_template(template, self.read_only)

    # ── update_template (versioning invariant) ────────────────────

    def test_update_unused_template_mutates_in_place(self):
        existing = make_template(id=1, name="Old Name")
        self.template_repo.get_by_id.return_value = existing
        self.submission_repo.template_is_in_use.return_value = False
        self.template_repo.update.return_value = make_template(id=1, name="New Name")

        result = self.service.update_template(1, {"name": "New Name"}, self.superadmin)
        assert result.name == "New Name"
        self.template_repo.update.assert_called_once()
        # Should NOT create a new template
        self.template_repo.create.assert_not_called()

    def test_update_in_use_template_creates_new_version(self):
        """ERD Invariant #3: Template in use → create new version."""
        existing = make_template(id=1, version=1, name="Old")
        self.template_repo.get_by_id.return_value = existing
        self.submission_repo.template_is_in_use.return_value = True
        self.template_repo.get_latest_version.return_value = 1
        created = make_template(id=50, version=2, name="Updated")
        self.template_repo.create.return_value = created

        result = self.service.update_template(1, {"name": "Updated"}, self.superadmin)
        assert result.id == 50
        assert result.version == 2
        self.template_repo.create.assert_called_once()
        self.template_repo.update.assert_not_called()

    def test_update_template_not_found(self):
        self.template_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            self.service.update_template(999, {"name": "X"}, self.superadmin)

    # ── activate / deactivate ─────────────────────────────────────

    def test_activate_template(self):
        template = make_template(is_active=False)
        self.template_repo.get_by_id.return_value = template
        self.template_repo.update.return_value = make_template(is_active=True)

        result = self.service.activate_template(1, self.superadmin)
        assert result.is_active is True

    def test_activate_already_active_is_idempotent(self):
        template = make_template(is_active=True)
        self.template_repo.get_by_id.return_value = template

        result = self.service.activate_template(1, self.superadmin)
        assert result.is_active is True
        self.template_repo.update.assert_not_called()

    def test_deactivate_cascades_to_overrides(self):
        template = make_template(is_active=True)
        self.template_repo.get_by_id.return_value = template
        self.template_repo.update.return_value = make_template(is_active=False)
        self.override_repo.mark_overrides_stale.return_value = 3

        self.service.deactivate_template(1, self.superadmin)
        self.override_repo.mark_overrides_stale.assert_called_once_with(1, ContentType.TEMPLATE)

    # ── set_template_roles ────────────────────────────────────────

    def test_set_template_roles_validates_roles(self):
        self.template_repo.get_by_id.return_value = make_template()
        self.role_repo.get_by_id.side_effect = [make_role(id=1), None]  # Second role missing

        with pytest.raises(ValidationError, match="Role with ID"):
            self.service.set_template_roles(1, [1, 999], self.superadmin)

    def test_set_template_roles_success(self):
        self.template_repo.get_by_id.return_value = make_template()
        self.role_repo.get_by_id.return_value = make_role()

        self.service.set_template_roles(1, [1], self.superadmin)
        self.template_repo.set_template_roles.assert_called_once_with(1, [1])

    # ── set_template_rubrics ──────────────────────────────────────

    def test_set_template_rubrics_validates_rubrics(self):
        self.template_repo.get_by_id.return_value = make_template()
        self.rubric_repo.get_by_id.return_value = None  # Rubric missing

        mapping = TemplateRubric(id=None, interview_template_id=1, rubric_id=999)
        with pytest.raises(ValidationError, match="Rubric with ID"):
            self.service.set_template_rubrics(1, [mapping], self.superadmin)

    # ── override management ───────────────────────────────────────

    def test_create_template_override_success(self):
        self.template_repo.get_by_id.return_value = make_template(organization_id=SUPER_ORG_ID)
        self.override_repo.get_override.return_value = None
        override = OverrideRecord(
            id=1, organization_id=5, base_content_id=1,
            content_type=ContentType.TEMPLATE, override_fields={"name": "Custom"},
        )
        self.override_repo.create_override.return_value = override

        result = self.service.create_template_override(1, {"name": "Custom"}, self.tenant_admin)
        assert result.override_fields == {"name": "Custom"}

    def test_create_override_on_non_super_org_fails(self):
        self.template_repo.get_by_id.return_value = make_template(organization_id=99)

        with pytest.raises(AuthorizationError, match="super-org"):
            self.service.create_template_override(1, {"name": "X"}, self.tenant_admin)

    def test_create_duplicate_override_fails(self):
        self.template_repo.get_by_id.return_value = make_template(organization_id=SUPER_ORG_ID)
        self.override_repo.get_override.return_value = OverrideRecord(
            id=1, organization_id=5, base_content_id=1,
            content_type=ContentType.TEMPLATE, override_fields={},
        )

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_template_override(1, {"name": "X"}, self.tenant_admin)

    def test_create_override_with_immutable_field_fails(self):
        self.template_repo.get_by_id.return_value = make_template(organization_id=SUPER_ORG_ID)
        self.override_repo.get_override.return_value = None

        with pytest.raises(ValidationError, match="immutable"):
            self.service.create_template_override(1, {"id": 999}, self.tenant_admin)

    def test_update_override_success(self):
        existing_override = OverrideRecord(
            id=1, organization_id=5, base_content_id=1,
            content_type=ContentType.TEMPLATE, override_fields={"name": "Old"},
        )
        self.override_repo.get_override.return_value = existing_override
        self.override_repo.update_override.return_value = OverrideRecord(
            id=1, organization_id=5, base_content_id=1,
            content_type=ContentType.TEMPLATE, override_fields={"name": "New"},
        )

        result = self.service.update_template_override(1, {"name": "New"}, self.tenant_admin)
        assert result.override_fields == {"name": "New"}

    def test_delete_override_success(self):
        self.override_repo.delete_override.return_value = True
        self.service.delete_template_override(1, self.tenant_admin)
        self.override_repo.delete_override.assert_called_once()

    def test_delete_override_not_found(self):
        self.override_repo.delete_override.return_value = False
        with pytest.raises(NotFoundError):
            self.service.delete_template_override(1, self.tenant_admin)

    # ── get_effective_template (override merge) ───────────────────

    def test_get_effective_template_with_override(self):
        base = make_template(id=1, name="Base Name", organization_id=SUPER_ORG_ID)
        override = OverrideRecord(
            id=10, organization_id=5, base_content_id=1,
            content_type=ContentType.TEMPLATE,
            override_fields={"name": "Custom Name"},
            is_active=True,
        )
        self.template_repo.get_by_id.return_value = base
        self.override_repo.get_override.return_value = override

        effective, returned_override = self.service.get_effective_template(1, self.tenant_admin)
        assert effective.name == "Custom Name"
        assert returned_override is not None

    def test_get_effective_template_without_override(self):
        base = make_template(id=1, name="Base Name", organization_id=SUPER_ORG_ID)
        self.template_repo.get_by_id.return_value = base
        self.override_repo.get_override.return_value = None

        effective, returned_override = self.service.get_effective_template(1, self.tenant_admin)
        assert effective.name == "Base Name"
        assert returned_override is None

    def test_get_effective_template_non_super_org_no_override(self):
        """Non-super-org templates do not participate in override resolution."""
        native = make_template(id=1, name="Native", organization_id=5)
        self.template_repo.get_by_id.return_value = native

        effective, returned_override = self.service.get_effective_template(1, self.tenant_admin)
        assert effective.name == "Native"
        assert returned_override is None

    # ── list_templates ────────────────────────────────────────────

    def test_list_templates(self):
        self.template_repo.list_for_organization.return_value = [make_template()]
        self.template_repo.count_for_organization.return_value = 1

        templates, total = self.service.list_templates(self.superadmin)
        assert len(templates) == 1
        assert total == 1


# ═══════════════════════════════════════════════════════════════════════════
# RubricService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRubricService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.rubric_repo = repos["rubric_repo"]
        self.submission_repo = repos["submission_repo"]
        self.override_repo = repos["override_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = RubricService(
            rubric_repo=self.rubric_repo,
            submission_repo=self.submission_repo,
            override_repo=self.override_repo,
            audit_repo=self.audit_repo,
        )
        self.superadmin = make_identity()

    # ── create_rubric ─────────────────────────────────────────────

    def test_create_rubric_with_valid_weights(self):
        rubric = make_rubric(id=None)
        dims = [
            make_dimension(weight="0.6", order=0),
            make_dimension(weight="0.4", order=1),
        ]
        self.rubric_repo.exists_with_name.return_value = False
        self.rubric_repo.create.return_value = make_rubric(id=10)

        result = self.service.create_rubric(rubric, dims, self.superadmin)
        assert result.id == 10
        self.rubric_repo.set_dimensions.assert_called_once()

    def test_create_rubric_weight_sum_invalid(self):
        rubric = make_rubric(id=None)
        dims = [
            make_dimension(weight="0.6", order=0),
            make_dimension(weight="0.6", order=1),  # Sum = 1.2
        ]
        self.rubric_repo.exists_with_name.return_value = False

        with pytest.raises(ValidationError, match="sum to 1.0"):
            self.service.create_rubric(rubric, dims, self.superadmin)

    def test_create_rubric_weight_sum_zero(self):
        rubric = make_rubric(id=None)
        dims = [
            make_dimension(weight="0.0", order=0),
            make_dimension(weight="0.0", order=1),
        ]
        self.rubric_repo.exists_with_name.return_value = False

        with pytest.raises(ValidationError, match="sum to 1.0"):
            self.service.create_rubric(rubric, dims, self.superadmin)

    def test_create_rubric_weight_within_tolerance(self):
        """Sum = 0.9999 should pass within 0.001 tolerance."""
        rubric = make_rubric(id=None)
        dims = [
            make_dimension(weight="0.5", order=0),
            make_dimension(weight="0.4999", order=1),
        ]
        self.rubric_repo.exists_with_name.return_value = False
        self.rubric_repo.create.return_value = make_rubric(id=10)

        result = self.service.create_rubric(rubric, dims, self.superadmin)
        assert result.id == 10

    def test_create_rubric_duplicate_sequence_order(self):
        rubric = make_rubric(id=None)
        dims = [
            make_dimension(weight="0.5", order=0),
            make_dimension(weight="0.5", order=0),  # Duplicate order
        ]
        self.rubric_repo.exists_with_name.return_value = False

        with pytest.raises(ValidationError, match="sequence_order"):
            self.service.create_rubric(rubric, dims, self.superadmin)

    def test_create_rubric_duplicate_name_fails(self):
        rubric = make_rubric(id=None)
        self.rubric_repo.exists_with_name.return_value = True

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_rubric(rubric, [], self.superadmin)

    def test_create_rubric_no_dimensions(self):
        """Rubric without dimensions is valid (dimensions added later)."""
        rubric = make_rubric(id=None)
        self.rubric_repo.exists_with_name.return_value = False
        self.rubric_repo.create.return_value = make_rubric(id=10)

        result = self.service.create_rubric(rubric, [], self.superadmin)
        assert result.id == 10
        self.rubric_repo.set_dimensions.assert_not_called()

    # ── deactivate_rubric ─────────────────────────────────────────

    def test_deactivate_rubric_cascades_overrides(self):
        self.rubric_repo.get_by_id.return_value = make_rubric(is_active=True)
        self.rubric_repo.update.return_value = make_rubric(is_active=False)
        self.override_repo.mark_overrides_stale.return_value = 2

        self.service.deactivate_rubric(1, self.superadmin)
        self.override_repo.mark_overrides_stale.assert_called_once_with(1, ContentType.RUBRIC)

    def test_deactivate_already_inactive_is_idempotent(self):
        self.rubric_repo.get_by_id.return_value = make_rubric(is_active=False)

        result = self.service.deactivate_rubric(1, self.superadmin)
        self.rubric_repo.update.assert_not_called()

    # ── get_rubric / list ─────────────────────────────────────────

    def test_get_rubric_not_found(self):
        self.rubric_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_rubric(999, self.superadmin)

    def test_list_rubrics(self):
        self.rubric_repo.list_for_organization.return_value = [make_rubric()]
        self.rubric_repo.count_for_organization.return_value = 1

        rubrics, total = self.service.list_rubrics(self.superadmin)
        assert len(rubrics) == 1
        assert total == 1


# ═══════════════════════════════════════════════════════════════════════════
# RoleService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRoleService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.role_repo = repos["role_repo"]
        self.submission_repo = repos["submission_repo"]
        self.override_repo = repos["override_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = RoleService(
            role_repo=self.role_repo,
            submission_repo=self.submission_repo,
            override_repo=self.override_repo,
            audit_repo=self.audit_repo,
        )
        self.superadmin = make_identity()

    def test_create_role_success(self):
        role = make_role(id=None)
        self.role_repo.exists_with_name.return_value = False
        self.role_repo.create.return_value = make_role(id=10)

        result = self.service.create_role(role, self.superadmin)
        assert result.id == 10

    def test_create_role_duplicate_name(self):
        role = make_role(id=None)
        self.role_repo.exists_with_name.return_value = True

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_role(role, self.superadmin)

    def test_update_role_name_conflict(self):
        existing = make_role(id=1, name="Old")
        self.role_repo.get_by_id.return_value = existing
        self.role_repo.exists_with_name.return_value = True  # Conflict

        with pytest.raises(ConflictError):
            self.service.update_role(1, {"name": "Taken"}, self.superadmin)

    def test_update_role_same_name_allowed(self):
        existing = make_role(id=1, name="Same")
        self.role_repo.get_by_id.return_value = existing
        self.role_repo.update.return_value = make_role(id=1, name="Same", description="Updated")

        result = self.service.update_role(1, {"description": "Updated"}, self.superadmin)
        assert result.description == "Updated"
        # exists_with_name should not even be called when name unchanged
        self.role_repo.exists_with_name.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# TopicService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTopicService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.topic_repo = repos["topic_repo"]
        self.override_repo = repos["override_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = TopicService(
            topic_repo=self.topic_repo,
            override_repo=self.override_repo,
            audit_repo=self.audit_repo,
        )
        self.superadmin = make_identity()

    def test_create_topic_success(self):
        topic = Topic(
            id=None, name="System Design", description=None,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.topic_repo.topic_exists_with_name.return_value = False
        self.topic_repo.create_topic.return_value = Topic(
            id=10, name="System Design", description=None,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )

        result = self.service.create_topic(topic, self.superadmin)
        assert result.id == 10

    def test_create_topic_duplicate_name(self):
        topic = Topic(
            id=None, name="Dupe", description=None,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.topic_repo.topic_exists_with_name.return_value = True

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_topic(topic, self.superadmin)

    def test_circular_reference_self_parent(self):
        topic = Topic(
            id=5, name="Loop", description=None,
            parent_topic_id=5,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.topic_repo.topic_exists_with_name.return_value = False

        with pytest.raises(ValidationError, match="cannot be its own parent"):
            self.service.create_topic(topic, self.superadmin)

    def test_circular_reference_via_ancestors(self):
        """Topic A → B → C, setting C.parent=A would create cycle."""
        topic = Topic(
            id=3, name="C", description=None,
            parent_topic_id=1,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.topic_repo.topic_exists_with_name.return_value = False
        self.topic_repo.get_topic_ancestors.return_value = [1, 2, 3]  # 3 is in ancestors

        with pytest.raises(ValidationError, match="Circular reference"):
            self.service.create_topic(topic, self.superadmin)

    def test_update_topic_parent_cycle_check(self):
        existing = Topic(
            id=1, name="T1", description=None,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.topic_repo.get_topic_by_id.return_value = existing
        self.topic_repo.get_topic_ancestors.return_value = [1]  # Self in ancestors of new parent

        with pytest.raises(ValidationError, match="Circular reference"):
            self.service.update_topic(1, {"parent_topic_id": 5}, self.superadmin)


# ═══════════════════════════════════════════════════════════════════════════
# QuestionService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestQuestionService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.question_repo = repos["question_repo"]
        self.override_repo = repos["override_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = QuestionService(
            question_repo=self.question_repo,
            override_repo=self.override_repo,
            audit_repo=self.audit_repo,
        )
        self.superadmin = make_identity()
        self.tenant_admin = make_identity(user_id=2, admin_role=AdminRole.ADMIN, organization_id=5)

    def test_create_question_success(self):
        q = Question(
            id=None, question_text="Tell me about a time...",
            answer_text=None, question_type=QuestionType.BEHAVIORAL,
            difficulty=DifficultyLevel.MEDIUM, scope=TemplateScope.PUBLIC,
            organization_id=SUPER_ORG_ID,
        )
        self.question_repo.create.return_value = Question(
            id=10, question_text="Tell me about a time...",
            answer_text=None, question_type=QuestionType.BEHAVIORAL,
            difficulty=DifficultyLevel.MEDIUM, scope=TemplateScope.PUBLIC,
            organization_id=SUPER_ORG_ID,
        )

        result = self.service.create_question(q, self.superadmin)
        assert result.id == 10

    def test_create_question_override(self):
        base = Question(
            id=1, question_text="Original", answer_text=None,
            question_type=QuestionType.BEHAVIORAL, difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.question_repo.get_by_id.return_value = base
        self.override_repo.get_override.return_value = None
        self.override_repo.create_override.return_value = OverrideRecord(
            id=1, organization_id=5, base_content_id=1,
            content_type=ContentType.QUESTION,
            override_fields={"question_text": "Modified?"},
        )

        result = self.service.create_question_override(1, {"question_text": "Modified?"}, self.tenant_admin)
        assert result.override_fields["question_text"] == "Modified?"

    def test_create_question_override_immutable_field(self):
        base = Question(
            id=1, question_text="Original", answer_text=None,
            question_type=QuestionType.BEHAVIORAL, difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC, organization_id=SUPER_ORG_ID,
        )
        self.question_repo.get_by_id.return_value = base
        self.override_repo.get_override.return_value = None

        with pytest.raises(ValidationError, match="immutable"):
            self.service.create_question_override(1, {"id": 999}, self.tenant_admin)


# ═══════════════════════════════════════════════════════════════════════════
# WindowService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowService:
    @pytest.fixture(autouse=True)
    def setup(self):
        repos = mock_repos()
        self.window_repo = repos["window_repo"]
        self.role_repo = repos["role_repo"]
        self.template_repo = repos["template_repo"]
        self.submission_repo = repos["submission_repo"]
        self.audit_repo = repos["audit_repo"]

        self.service = WindowService(
            window_repo=self.window_repo,
            role_repo=self.role_repo,
            template_repo=self.template_repo,
            submission_repo=self.submission_repo,
            audit_repo=self.audit_repo,
        )
        self.admin = make_identity(user_id=42, admin_role=AdminRole.ADMIN, organization_id=5)

    def _make_mapping(self, role_id=1, template_id=1) -> WindowRoleTemplate:
        return WindowRoleTemplate(
            id=None, window_id=0, role_id=role_id,
            template_id=template_id, selection_weight=1,
        )

    # ── create_window ─────────────────────────────────────────────

    def test_create_window_success(self):
        window = make_window(id=None, organization_id=5)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = make_template(is_active=True)
        self.window_repo.find_overlapping_windows.return_value = []
        self.window_repo.create.return_value = make_window(id=10, organization_id=5)

        result = self.service.create_window(window, [mapping], self.admin)
        assert result.id == 10

    def test_create_window_end_before_start(self):
        now = datetime.now(timezone.utc)
        window = make_window(
            id=None, organization_id=5,
            start_time=now + timedelta(days=15),
            end_time=now + timedelta(days=1),  # End before start
        )
        mapping = self._make_mapping()

        with pytest.raises(ValidationError, match="end_time must be after"):
            self.service.create_window(window, [mapping], self.admin)

    def test_create_window_no_mappings(self):
        window = make_window(id=None, organization_id=5)

        with pytest.raises(ValidationError, match="at least one"):
            self.service.create_window(window, [], self.admin)

    def test_create_window_missing_role(self):
        window = make_window(id=None, organization_id=5)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = None

        with pytest.raises(ValidationError, match="Role"):
            self.service.create_window(window, [mapping], self.admin)

    def test_create_window_inactive_template(self):
        window = make_window(id=None, organization_id=5)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = make_template(is_active=False)

        with pytest.raises(ValidationError, match="not active"):
            self.service.create_window(window, [mapping], self.admin)

    def test_create_window_missing_template(self):
        window = make_window(id=None, organization_id=5)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = None

        with pytest.raises(ValidationError, match="Template"):
            self.service.create_window(window, [mapping], self.admin)

    def test_create_window_invalid_selection_weight(self):
        window = make_window(id=None, organization_id=5)
        mapping = self._make_mapping()
        mapping.selection_weight = 0
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = make_template(is_active=True)

        with pytest.raises(ValidationError, match="selection_weight"):
            self.service.create_window(window, [mapping], self.admin)

    # ── overlap detection ─────────────────────────────────────────

    def test_create_window_overlap_rejected(self):
        window = make_window(id=None, organization_id=5, allow_resubmission=False)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = make_template(is_active=True)
        self.window_repo.find_overlapping_windows.return_value = [make_window(id=99)]

        with pytest.raises(ConflictError, match="Overlapping"):
            self.service.create_window(window, [mapping], self.admin)

    def test_create_window_overlap_allowed_with_resubmission(self):
        """When allow_resubmission=True, overlap is allowed."""
        window = make_window(id=None, organization_id=5, allow_resubmission=True)
        mapping = self._make_mapping()
        self.role_repo.get_by_id.return_value = make_role()
        self.template_repo.get_by_id.return_value = make_template(is_active=True)
        self.window_repo.create.return_value = make_window(id=10, organization_id=5, allow_resubmission=True)

        result = self.service.create_window(window, [mapping], self.admin)
        assert result.id == 10
        # find_overlapping_windows should NOT be called
        self.window_repo.find_overlapping_windows.assert_not_called()

    # ── get / list ────────────────────────────────────────────────

    def test_get_window_not_found(self):
        self.window_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_window(999, self.admin)

    def test_get_window_tenant_isolation(self):
        window = make_window(organization_id=99)
        self.window_repo.get_by_id.return_value = window
        with pytest.raises(NotFoundError):
            self.service.get_window(1, self.admin)
