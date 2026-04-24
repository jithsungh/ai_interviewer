"""
Admin Domain Services

Pure business-logic orchestrators. Each service:
  • Accepts validated inputs from the API layer.
  • Enforces RBAC via authorization module (reuses shared/auth_context).
  • Enforces domain invariants (immutability, versioning, weight sums, cycles).
  • Delegates persistence to repository protocols (no direct DB access).
  • Logs domain events via shared/observability.

No HTTP concerns, no raw SQL, no SQLAlchemy imports.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.shared.auth_context.models import AdminRole, IdentityContext
from app.shared.errors import (
    ConflictError,
    NotFoundError,
    TemplateImmutabilityViolation,
    ValidationError,
)

from .authorization import (
    authorize_admin_operation,
    authorize_base_content_mutation,
    authorize_override_operation,
)
from .entities import (
    IMMUTABLE_OVERRIDE_FIELDS,
    RUBRIC_WEIGHT_TOLERANCE,
    SUPER_ORG_ID,
    CodingProblem,
    CodingTopic,
    ContentType,
    OverrideRecord,
    Question,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRubric,
    Topic,
    Window,
    WindowRoleTemplate,
)
from .protocols import (
    AuditLogRepository,
    CodingProblemRepository,
    OverrideRepository,
    QuestionRepository,
    RoleRepository,
    RubricRepository,
    SubmissionRepository,
    TemplateRepository,
    TopicRepository,
    WindowRepository,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _effective_org_id(identity: IdentityContext, explicit_org: Optional[int] = None) -> int:
    """
    Resolve the target organization ID.

    If the caller supplies an explicit org (superadmin cross-tenant),
    use it.  Otherwise fall back to the caller's own org.
    """
    if explicit_org is not None:
        return explicit_org
    assert identity.organization_id is not None, "Admin must have organization_id"
    return identity.organization_id


def _validate_override_fields(override_fields: Dict[str, Any]) -> None:
    """
    Reject override payloads that try to override immutable fields.

    Raises:
        ValidationError — if any forbidden field is present
    """
    forbidden = set(override_fields.keys()) & IMMUTABLE_OVERRIDE_FIELDS
    if forbidden:
        raise ValidationError(
            message=f"Cannot override immutable fields: {sorted(forbidden)}",
            field="override_fields",
        )


def _merge_override(base_dict: Dict[str, Any], override_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce an effective (merged) content dict.

    Override priority: tenant override > base content.
    """
    merged = dict(base_dict)
    merged.update(override_fields)
    return merged


# ═══════════════════════════════════════════════════════════════════════════
# Template Service
# ═══════════════════════════════════════════════════════════════════════════

class TemplateService:
    """
    Business logic for interview templates.

    Handles:
      • CRUD with RBAC
      • Immutability-safe versioning (ERD Invariant #3)
      • Activation / deactivation
      • Template-role and template-rubric mappings
      • Override management for tenants
    """

    def __init__(
        self,
        template_repo: TemplateRepository,
        submission_repo: SubmissionRepository,
        override_repo: OverrideRepository,
        rubric_repo: RubricRepository,
        role_repo: RoleRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._templates = template_repo
        self._submissions = submission_repo
        self._overrides = override_repo
        self._rubrics = rubric_repo
        self._roles = role_repo
        self._audit = audit_repo

    # ── Queries ────────────────────────────────────────────────────────

    def get_template(
        self,
        template_id: int,
        identity: IdentityContext,
    ) -> Template:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        template = self._templates.get_by_id(template_id)
        if template is None:
            raise NotFoundError(resource_type="Template", resource_id=template_id)

        # Tenant isolation: non-superadmin can only see own org or super-org content
        if not identity.is_superadmin():
            if template.organization_id not in (identity.organization_id, SUPER_ORG_ID):
                raise NotFoundError(resource_type="Template", resource_id=template_id)

        return template

    def get_effective_template(
        self,
        base_template_id: int,
        identity: IdentityContext,
    ) -> Tuple[Template, Optional[OverrideRecord]]:
        """
        Return the effective template for the caller's organisation.

        If an active override exists for the caller's org, the template
        fields are merged.  Returns (effective_template, override_or_none).
        """
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)

        base = self._templates.get_by_id(base_template_id)
        if base is None:
            raise NotFoundError(resource_type="Template", resource_id=base_template_id)

        if base.organization_id != SUPER_ORG_ID:
            # Not a super-org template — no override applicable
            return base, None

        override = self._overrides.get_override(org_id, base_template_id, ContentType.TEMPLATE)
        if override and override.is_active:
            merged = _merge_override(asdict(base), override.override_fields)
            effective = Template(**{k: merged[k] for k in Template.__dataclass_fields__})
            return effective, override

        return base, None

    def list_templates(
        self,
        identity: IdentityContext,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Template], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)

        templates = self._templates.list_for_organization(
            org_id, is_active=is_active, page=page, per_page=per_page,
        )
        total = self._templates.count_for_organization(org_id, is_active=is_active)
        return templates, total

    # ── Commands ───────────────────────────────────────────────────────

    def create_template(
        self,
        template: Template,
        identity: IdentityContext,
    ) -> Template:
        org_id = template.organization_id or _effective_org_id(identity)
        template.organization_id = org_id

        # Only superadmin can create base content
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        # Duplicate name check (within same org)
        if self._templates.exists_with_name(template.name, org_id):
            raise ConflictError(
                message=f"Template with name '{template.name}' already exists in organization {org_id}"
            )

        created = self._templates.create(template)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="template.created",
            entity_type="interview_templates",
            entity_id=created.id,
            new_value=asdict(created),
        )
        logger.info("Template created", extra={"template_id": created.id, "org_id": org_id})
        return created

    def update_template(
        self,
        template_id: int,
        changes: Dict[str, Any],
        identity: IdentityContext,
    ) -> Template:
        existing = self._templates.get_by_id(template_id)
        if existing is None:
            raise NotFoundError(resource_type="Template", resource_id=template_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        # ── Invariant #3: Immutability after use ──
        if self._submissions.template_is_in_use(template_id):
            # Create new version instead of mutating
            new_template = existing.create_new_version()
            for key, value in changes.items():
                if hasattr(new_template, key) and key not in ("id", "version", "created_at", "updated_at"):
                    setattr(new_template, key, value)

            # Resolve next version number from DB
            latest_ver = self._templates.get_latest_version(existing.name, existing.organization_id)
            new_template.version = (latest_ver or existing.version) + 1

            created = self._templates.create(new_template)
            self._audit.log(
                organization_id=org_id,
                actor_user_id=identity.user_id,
                action="template.versioned",
                entity_type="interview_templates",
                entity_id=created.id,
                old_value={"previous_version_id": template_id, "previous_version": existing.version},
                new_value=asdict(created),
            )
            logger.info(
                "Template versioned (immutability)",
                extra={"old_id": template_id, "new_id": created.id, "version": created.version},
            )
            return created

        # Not in use — safe to mutate in-place
        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "version", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._templates.update(existing)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="template.updated",
            entity_type="interview_templates",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    def activate_template(self, template_id: int, identity: IdentityContext) -> Template:
        return self._set_template_active(template_id, True, identity)

    def deactivate_template(self, template_id: int, identity: IdentityContext) -> Template:
        template = self._set_template_active(template_id, False, identity)
        # Cascade: mark all tenant overrides as stale
        stale_count = self._overrides.mark_overrides_stale(template_id, ContentType.TEMPLATE)
        if stale_count:
            logger.info(
                "Override cascade on template deactivation",
                extra={"template_id": template_id, "stale_overrides": stale_count},
            )
        return template

    def _set_template_active(self, template_id: int, active: bool, identity: IdentityContext) -> Template:
        existing = self._templates.get_by_id(template_id)
        if existing is None:
            raise NotFoundError(resource_type="Template", resource_id=template_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        if existing.is_active == active:
            return existing  # idempotent

        existing.is_active = active
        updated = self._templates.update(existing)

        action = "template.activated" if active else "template.deactivated"
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action=action,
            entity_type="interview_templates",
            entity_id=updated.id,
            new_value={"is_active": active},
        )
        return updated

    # ── Template-Role mappings ─────────────────────────────────────────

    def set_template_roles(
        self,
        template_id: int,
        role_ids: List[int],
        identity: IdentityContext,
    ) -> None:
        template = self._templates.get_by_id(template_id)
        if template is None:
            raise NotFoundError(resource_type="Template", resource_id=template_id)

        org_id = template.organization_id or _effective_org_id(identity)
        authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        # Validate that all referenced roles exist
        for rid in role_ids:
            if self._roles.get_by_id(rid) is None:
                raise ValidationError(
                    message=f"Role with ID {rid} not found",
                    field="role_ids",
                )

        self._templates.set_template_roles(template_id, role_ids)

    # ── Template-Rubric mappings ───────────────────────────────────────

    def set_template_rubrics(
        self,
        template_id: int,
        rubrics: List[TemplateRubric],
        identity: IdentityContext,
    ) -> None:
        template = self._templates.get_by_id(template_id)
        if template is None:
            raise NotFoundError(resource_type="Template", resource_id=template_id)

        org_id = template.organization_id or _effective_org_id(identity)
        authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        # Validate rubric references
        for tr in rubrics:
            if self._rubrics.get_by_id(tr.rubric_id) is None:
                raise ValidationError(
                    message=f"Rubric with ID {tr.rubric_id} not found",
                    field="rubrics",
                )

        self._templates.set_template_rubrics(template_id, rubrics)

    # ── Override Management ────────────────────────────────────────────

    def create_template_override(
        self,
        base_template_id: int,
        override_fields: Dict[str, Any],
        identity: IdentityContext,
    ) -> OverrideRecord:
        base = self._templates.get_by_id(base_template_id)
        if base is None:
            raise NotFoundError(resource_type="Template", resource_id=base_template_id)

        org_id = _effective_org_id(identity)
        authorize_override_operation(
            identity,
            base_content_org_id=base.organization_id or 0,
            override_org_id=org_id,
            operation="POST",
        )
        _validate_override_fields(override_fields)

        # Check for existing override
        existing = self._overrides.get_override(org_id, base_template_id, ContentType.TEMPLATE)
        if existing is not None:
            raise ConflictError(
                message=f"Override already exists for template {base_template_id} in org {org_id}"
            )

        override = OverrideRecord(
            id=None,
            organization_id=org_id,
            base_content_id=base_template_id,
            content_type=ContentType.TEMPLATE,
            override_fields=override_fields,
        )
        created = self._overrides.create_override(override)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="template_override.created",
            entity_type="template_overrides",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_template_override(
        self,
        base_template_id: int,
        override_fields: Dict[str, Any],
        identity: IdentityContext,
    ) -> OverrideRecord:
        org_id = _effective_org_id(identity)
        existing = self._overrides.get_override(org_id, base_template_id, ContentType.TEMPLATE)
        if existing is None:
            raise NotFoundError(resource_type="TemplateOverride", resource_id=base_template_id)

        authorize_override_operation(
            identity,
            base_content_org_id=SUPER_ORG_ID,
            override_org_id=org_id,
            operation="PUT",
        )
        _validate_override_fields(override_fields)

        old_snapshot = asdict(existing)
        existing.override_fields = override_fields
        updated = self._overrides.update_override(existing)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="template_override.updated",
            entity_type="template_overrides",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    def delete_template_override(
        self,
        base_template_id: int,
        identity: IdentityContext,
    ) -> None:
        org_id = _effective_org_id(identity)
        authorize_override_operation(
            identity,
            base_content_org_id=SUPER_ORG_ID,
            override_org_id=org_id,
            operation="DELETE",
        )

        deleted = self._overrides.delete_override(org_id, base_template_id, ContentType.TEMPLATE)
        if not deleted:
            raise NotFoundError(resource_type="TemplateOverride", resource_id=base_template_id)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="template_override.deleted",
            entity_type="template_overrides",
            entity_id=None,
            old_value={"base_template_id": base_template_id, "organization_id": org_id},
        )


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Service
# ═══════════════════════════════════════════════════════════════════════════

class RubricService:
    """
    Business logic for rubrics and rubric dimensions.

    Key invariant: dimension weights per rubric MUST sum to 1.0 (±0.001).
    """

    def __init__(
        self,
        rubric_repo: RubricRepository,
        submission_repo: SubmissionRepository,
        override_repo: OverrideRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._rubrics = rubric_repo
        self._submissions = submission_repo
        self._overrides = override_repo
        self._audit = audit_repo

    # ── Queries ────────────────────────────────────────────────────────

    def get_rubric(self, rubric_id: int, identity: IdentityContext) -> Rubric:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        rubric = self._rubrics.get_by_id(rubric_id)
        if rubric is None:
            raise NotFoundError(resource_type="Rubric", resource_id=rubric_id)

        if not identity.is_superadmin():
            if rubric.organization_id not in (identity.organization_id, SUPER_ORG_ID):
                raise NotFoundError(resource_type="Rubric", resource_id=rubric_id)

        return rubric

    def list_rubrics(
        self,
        identity: IdentityContext,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Rubric], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        rubrics = self._rubrics.list_for_organization(org_id, is_active=is_active, page=page, per_page=per_page)
        total = self._rubrics.count_for_organization(org_id, is_active=is_active)
        return rubrics, total

    def get_dimensions(self, rubric_id: int, identity: IdentityContext) -> List[RubricDimension]:
        self.get_rubric(rubric_id, identity)  # access check + existence
        return self._rubrics.get_dimensions(rubric_id)

    # ── Commands ───────────────────────────────────────────────────────

    def create_rubric(
        self,
        rubric: Rubric,
        dimensions: List[RubricDimension],
        identity: IdentityContext,
    ) -> Rubric:
        org_id = rubric.organization_id or _effective_org_id(identity)
        rubric.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        if self._rubrics.exists_with_name(rubric.name, org_id):
            raise ConflictError(
                message=f"Rubric with name '{rubric.name}' already exists in organization {org_id}"
            )

        self._validate_dimension_weights(dimensions)

        created = self._rubrics.create(rubric)
        if dimensions:
            for d in dimensions:
                d.rubric_id = created.id
            self._rubrics.set_dimensions(created.id, dimensions)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="rubric.created",
            entity_type="rubrics",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_rubric(
        self,
        rubric_id: int,
        changes: Dict[str, Any],
        dimensions: Optional[List[RubricDimension]],
        identity: IdentityContext,
    ) -> Rubric:
        existing = self._rubrics.get_by_id(rubric_id)
        if existing is None:
            raise NotFoundError(resource_type="Rubric", resource_id=rubric_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._rubrics.update(existing)

        if dimensions is not None:
            self._validate_dimension_weights(dimensions)
            for d in dimensions:
                d.rubric_id = rubric_id
            self._rubrics.set_dimensions(rubric_id, dimensions)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="rubric.updated",
            entity_type="rubrics",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    def deactivate_rubric(self, rubric_id: int, identity: IdentityContext) -> Rubric:
        existing = self._rubrics.get_by_id(rubric_id)
        if existing is None:
            raise NotFoundError(resource_type="Rubric", resource_id=rubric_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        if not existing.is_active:
            return existing  # idempotent

        existing.is_active = False
        updated = self._rubrics.update(existing)

        stale_count = self._overrides.mark_overrides_stale(rubric_id, ContentType.RUBRIC)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="rubric.deactivated",
            entity_type="rubrics",
            entity_id=updated.id,
            new_value={"is_active": False, "stale_overrides": stale_count},
        )
        return updated

    # ── Validation ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_dimension_weights(dimensions: List[RubricDimension]) -> None:
        """
        Enforce: sum of dimension weights == 1.0  (±tolerance).

        Raises ValidationError if violated.
        """
        if not dimensions:
            return  # No dimensions to validate

        total_weight = sum(d.weight for d in dimensions)
        if abs(total_weight - Decimal("1.0")) > Decimal(str(RUBRIC_WEIGHT_TOLERANCE)):
            raise ValidationError(
                message=f"Rubric dimension weights must sum to 1.0 (got {total_weight})",
                field="dimensions.weight",
            )

        # Enforce unique sequence_order
        orders = [d.sequence_order for d in dimensions]
        if len(orders) != len(set(orders)):
            raise ValidationError(
                message="Rubric dimension sequence_order values must be unique",
                field="dimensions.sequence_order",
            )


# ═══════════════════════════════════════════════════════════════════════════
# Role Service
# ═══════════════════════════════════════════════════════════════════════════

class RoleService:
    """Business logic for interview roles."""

    def __init__(
        self,
        role_repo: RoleRepository,
        submission_repo: SubmissionRepository,
        override_repo: OverrideRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._roles = role_repo
        self._submissions = submission_repo
        self._overrides = override_repo
        self._audit = audit_repo

    def get_role(self, role_id: int, identity: IdentityContext) -> Role:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise NotFoundError(resource_type="Role", resource_id=role_id)
        if not identity.is_superadmin():
            if role.organization_id not in (identity.organization_id, SUPER_ORG_ID, None):
                raise NotFoundError(resource_type="Role", resource_id=role_id)
        return role

    def list_roles(
        self, identity: IdentityContext, *, page: int = 1, per_page: int = 20
    ) -> Tuple[List[Role], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        roles = self._roles.list_for_organization(org_id, page=page, per_page=per_page)
        total = self._roles.count_for_organization(org_id)
        return roles, total

    def create_role(self, role: Role, identity: IdentityContext) -> Role:
        org_id = role.organization_id or _effective_org_id(identity)
        role.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        if self._roles.exists_with_name(role.name, org_id):
            raise ConflictError(message=f"Role '{role.name}' already exists in organization {org_id}")

        created = self._roles.create(role)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="role.created",
            entity_type="roles",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_role(self, role_id: int, changes: Dict[str, Any], identity: IdentityContext) -> Role:
        existing = self._roles.get_by_id(role_id)
        if existing is None:
            raise NotFoundError(resource_type="Role", resource_id=role_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        # Name uniqueness check
        new_name = changes.get("name", existing.name)
        if new_name != existing.name and self._roles.exists_with_name(new_name, org_id, exclude_id=role_id):
            raise ConflictError(message=f"Role '{new_name}' already exists in organization {org_id}")

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._roles.update(existing)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="role.updated",
            entity_type="roles",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated


# ═══════════════════════════════════════════════════════════════════════════
# Topic Service
# ═══════════════════════════════════════════════════════════════════════════

class TopicService:
    """
    Business logic for general topics and coding topics.

    Key invariant: no circular parent references in topic hierarchy.
    """

    def __init__(
        self,
        topic_repo: TopicRepository,
        override_repo: OverrideRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._topics = topic_repo
        self._overrides = override_repo
        self._audit = audit_repo

    # ── General Topics ─────────────────────────────────────────────────

    def get_topic(self, topic_id: int, identity: IdentityContext) -> Topic:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        topic = self._topics.get_topic_by_id(topic_id)
        if topic is None:
            raise NotFoundError(resource_type="Topic", resource_id=topic_id)
        if not identity.is_superadmin():
            if topic.organization_id not in (identity.organization_id, SUPER_ORG_ID, None):
                raise NotFoundError(resource_type="Topic", resource_id=topic_id)
        return topic

    def list_topics(
        self, identity: IdentityContext, *, page: int = 1, per_page: int = 20
    ) -> Tuple[List[Topic], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        topics = self._topics.list_topics_for_organization(org_id, page=page, per_page=per_page)
        total = self._topics.count_topics_for_organization(org_id)
        return topics, total

    def create_topic(self, topic: Topic, identity: IdentityContext) -> Topic:
        org_id = topic.organization_id or _effective_org_id(identity)
        topic.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        if topic.parent_topic_id is not None:
            self._check_topic_cycle(topic.parent_topic_id, topic.id)

        if self._topics.topic_exists_with_name(topic.name, org_id):
            raise ConflictError(message=f"Topic '{topic.name}' already exists in organization {org_id}")

        created = self._topics.create_topic(topic)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="topic.created",
            entity_type="topics",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_topic(self, topic_id: int, changes: Dict[str, Any], identity: IdentityContext) -> Topic:
        existing = self._topics.get_topic_by_id(topic_id)
        if existing is None:
            raise NotFoundError(resource_type="Topic", resource_id=topic_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        if "parent_topic_id" in changes and changes["parent_topic_id"] is not None:
            self._check_topic_cycle(changes["parent_topic_id"], topic_id)

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._topics.update_topic(existing)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="topic.updated",
            entity_type="topics",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    def _check_topic_cycle(self, parent_id: int, self_id: Optional[int]) -> None:
        """
        Raise ValidationError if setting parent_id would create a cycle.
        """
        if self_id is not None and parent_id == self_id:
            raise ValidationError(
                message="Topic cannot be its own parent",
                field="parent_topic_id",
            )
        ancestors = self._topics.get_topic_ancestors(parent_id)
        if self_id is not None and self_id in ancestors:
            raise ValidationError(
                message="Circular reference detected in topic hierarchy",
                field="parent_topic_id",
            )

    # ── Coding Topics ──────────────────────────────────────────────────

    def get_coding_topic(self, topic_id: int, identity: IdentityContext) -> CodingTopic:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        topic = self._topics.get_coding_topic_by_id(topic_id)
        if topic is None:
            raise NotFoundError(resource_type="CodingTopic", resource_id=topic_id)
        if not identity.is_superadmin():
            if topic.organization_id not in (identity.organization_id, SUPER_ORG_ID, None):
                raise NotFoundError(resource_type="CodingTopic", resource_id=topic_id)
        return topic

    def list_coding_topics(
        self, identity: IdentityContext, *, page: int = 1, per_page: int = 20
    ) -> Tuple[List[CodingTopic], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        topics = self._topics.list_coding_topics_for_organization(org_id, page=page, per_page=per_page)
        total = self._topics.count_coding_topics_for_organization(org_id)
        return topics, total

    def create_coding_topic(self, topic: CodingTopic, identity: IdentityContext) -> CodingTopic:
        org_id = topic.organization_id or _effective_org_id(identity)
        topic.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        if topic.parent_topic_id is not None:
            self._check_coding_topic_cycle(topic.parent_topic_id, topic.id)

        created = self._topics.create_coding_topic(topic)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="coding_topic.created",
            entity_type="coding_topics",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def _check_coding_topic_cycle(self, parent_id: int, self_id: Optional[int]) -> None:
        if self_id is not None and parent_id == self_id:
            raise ValidationError(
                message="Coding topic cannot be its own parent",
                field="parent_topic_id",
            )
        ancestors = self._topics.get_coding_topic_ancestors(parent_id)
        if self_id is not None and self_id in ancestors:
            raise ValidationError(
                message="Circular reference detected in coding topic hierarchy",
                field="parent_topic_id",
            )


# ═══════════════════════════════════════════════════════════════════════════
# Question Service
# ═══════════════════════════════════════════════════════════════════════════

class QuestionService:
    """Business logic for questions (behavioral / technical / situational)."""

    def __init__(
        self,
        question_repo: QuestionRepository,
        override_repo: OverrideRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._questions = question_repo
        self._overrides = override_repo
        self._audit = audit_repo

    def get_question(self, question_id: int, identity: IdentityContext) -> Question:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        question = self._questions.get_by_id(question_id)
        if question is None:
            raise NotFoundError(resource_type="Question", resource_id=question_id)
        if not identity.is_superadmin():
            if question.organization_id not in (identity.organization_id, SUPER_ORG_ID, None):
                raise NotFoundError(resource_type="Question", resource_id=question_id)
        return question

    def list_questions(
        self,
        identity: IdentityContext,
        *,
        is_active: Optional[bool] = None,
        question_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Question], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        questions = self._questions.list_for_organization(
            org_id, is_active=is_active, question_type=question_type, page=page, per_page=per_page,
        )
        total = self._questions.count_for_organization(
            org_id, is_active=is_active, question_type=question_type,
        )
        return questions, total

    def create_question(self, question: Question, identity: IdentityContext) -> Question:
        org_id = question.organization_id or _effective_org_id(identity)
        question.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        created = self._questions.create(question)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="question.created",
            entity_type="questions",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_question(
        self, question_id: int, changes: Dict[str, Any], identity: IdentityContext
    ) -> Question:
        existing = self._questions.get_by_id(question_id)
        if existing is None:
            raise NotFoundError(resource_type="Question", resource_id=question_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._questions.update(existing)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="question.updated",
            entity_type="questions",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    # ── Override ───────────────────────────────────────────────────────

    def create_question_override(
        self, base_question_id: int, override_fields: Dict[str, Any], identity: IdentityContext,
    ) -> OverrideRecord:
        base = self._questions.get_by_id(base_question_id)
        if base is None:
            raise NotFoundError(resource_type="Question", resource_id=base_question_id)

        org_id = _effective_org_id(identity)
        authorize_override_operation(
            identity,
            base_content_org_id=base.organization_id or 0,
            override_org_id=org_id,
            operation="POST",
        )
        _validate_override_fields(override_fields)

        existing = self._overrides.get_override(org_id, base_question_id, ContentType.QUESTION)
        if existing is not None:
            raise ConflictError(
                message=f"Override already exists for question {base_question_id} in org {org_id}"
            )

        override = OverrideRecord(
            id=None,
            organization_id=org_id,
            base_content_id=base_question_id,
            content_type=ContentType.QUESTION,
            override_fields=override_fields,
        )
        created = self._overrides.create_override(override)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="question_override.created",
            entity_type="question_overrides",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem Service
# ═══════════════════════════════════════════════════════════════════════════

class CodingProblemService:
    """Business logic for coding problems."""

    def __init__(
        self,
        problem_repo: CodingProblemRepository,
        override_repo: OverrideRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._problems = problem_repo
        self._overrides = override_repo
        self._audit = audit_repo

    def get_problem(self, problem_id: int, identity: IdentityContext) -> CodingProblem:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        problem = self._problems.get_by_id(problem_id)
        if problem is None:
            raise NotFoundError(resource_type="CodingProblem", resource_id=problem_id)
        if not identity.is_superadmin():
            if problem.organization_id not in (identity.organization_id, SUPER_ORG_ID, None):
                raise NotFoundError(resource_type="CodingProblem", resource_id=problem_id)
        return problem

    def list_problems(
        self,
        identity: IdentityContext,
        *,
        is_active: Optional[bool] = None,
        difficulty: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[CodingProblem], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        problems = self._problems.list_for_organization(
            org_id, is_active=is_active, difficulty=difficulty, page=page, per_page=per_page,
        )
        total = self._problems.count_for_organization(org_id, is_active=is_active, difficulty=difficulty)
        return problems, total

    def create_problem(self, problem: CodingProblem, identity: IdentityContext) -> CodingProblem:
        org_id = problem.organization_id or _effective_org_id(identity)
        problem.organization_id = org_id

        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        created = self._problems.create(problem)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="coding_problem.created",
            entity_type="coding_problems",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_problem(
        self, problem_id: int, changes: Dict[str, Any], identity: IdentityContext,
    ) -> CodingProblem:
        existing = self._problems.get_by_id(problem_id)
        if existing is None:
            raise NotFoundError(resource_type="CodingProblem", resource_id=problem_id)

        org_id = existing.organization_id or _effective_org_id(identity)
        if org_id == SUPER_ORG_ID:
            authorize_base_content_mutation(identity)
        else:
            authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        updated = self._problems.update(existing)
        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="coding_problem.updated",
            entity_type="coding_problems",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated


# ═══════════════════════════════════════════════════════════════════════════
# Window Service
# ═══════════════════════════════════════════════════════════════════════════

class WindowService:
    """
    Business logic for interview submission windows and window-role-template mappings.

    Key invariants:
      • end_time > start_time
      • Non-overlapping active windows for same role if allow_resubmission=false
      • Mappings reference existing active roles and templates
    """

    def __init__(
        self,
        window_repo: WindowRepository,
        role_repo: RoleRepository,
        template_repo: TemplateRepository,
        submission_repo: SubmissionRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._windows = window_repo
        self._roles = role_repo
        self._templates = template_repo
        self._submissions = submission_repo
        self._audit = audit_repo

    # ── Queries ────────────────────────────────────────────────────────

    def get_window(self, window_id: int, identity: IdentityContext) -> Window:
        authorize_admin_operation(identity, operation="GET", resource_org_id=identity.organization_id)
        window = self._windows.get_by_id(window_id)
        if window is None:
            raise NotFoundError(resource_type="Window", resource_id=window_id)
        if not identity.is_superadmin():
            if window.organization_id != identity.organization_id:
                raise NotFoundError(resource_type="Window", resource_id=window_id)
        return window

    def list_windows(
        self, identity: IdentityContext, *, page: int = 1, per_page: int = 20,
    ) -> Tuple[List[Window], int]:
        org_id = _effective_org_id(identity)
        authorize_admin_operation(identity, operation="GET", resource_org_id=org_id)
        windows = self._windows.list_for_organization(org_id, page=page, per_page=per_page)
        total = self._windows.count_for_organization(org_id)
        return windows, total

    # ── Commands ───────────────────────────────────────────────────────

    def create_window(
        self,
        window: Window,
        mappings: List[WindowRoleTemplate],
        identity: IdentityContext,
    ) -> Window:
        org_id = window.organization_id or _effective_org_id(identity)
        window.organization_id = org_id
        authorize_admin_operation(identity, operation="POST", resource_org_id=org_id)

        self._validate_window_times(window)

        if not mappings:
            raise ValidationError(
                message="Window must have at least one role-template mapping",
                field="mappings",
            )

        self._validate_mappings(mappings)
        self._check_overlap(window, mappings)

        created = self._windows.create(window)
        for m in mappings:
            m.window_id = created.id
        self._windows.set_mappings(created.id, mappings)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="window.created",
            entity_type="interview_submission_windows",
            entity_id=created.id,
            new_value=asdict(created),
        )
        return created

    def update_window(
        self,
        window_id: int,
        changes: Dict[str, Any],
        mappings: Optional[List[WindowRoleTemplate]],
        identity: IdentityContext,
    ) -> Window:
        existing = self._windows.get_by_id(window_id)
        if existing is None:
            raise NotFoundError(resource_type="Window", resource_id=window_id)

        org_id = existing.organization_id
        authorize_admin_operation(identity, operation="PUT", resource_org_id=org_id)

        old_snapshot = asdict(existing)
        for key, value in changes.items():
            if hasattr(existing, key) and key not in ("id", "created_at", "updated_at"):
                setattr(existing, key, value)

        self._validate_window_times(existing)

        if mappings is not None:
            if not mappings:
                raise ValidationError(
                    message="Window must have at least one role-template mapping",
                    field="mappings",
                )
            self._validate_mappings(mappings)
            self._check_overlap(existing, mappings, exclude_window_id=window_id)

        updated = self._windows.update(existing)

        if mappings is not None:
            for m in mappings:
                m.window_id = window_id
            self._windows.set_mappings(window_id, mappings)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="window.updated",
            entity_type="interview_submission_windows",
            entity_id=updated.id,
            old_value=old_snapshot,
            new_value=asdict(updated),
        )
        return updated

    def archive_window(self, window_id: int, identity: IdentityContext) -> None:
        existing = self._windows.get_by_id(window_id)
        if existing is None:
            raise NotFoundError(resource_type="Window", resource_id=window_id)

        org_id = existing.organization_id
        authorize_admin_operation(identity, operation="DELETE", resource_org_id=org_id)

        if self._submissions.window_has_submissions(window_id):
            raise ConflictError(
                message=(
                    "Cannot archive window because interview submissions already reference it. "
                    "Update the window schedule instead."
                )
            )

        self._windows.delete(window_id)

        self._audit.log(
            organization_id=org_id,
            actor_user_id=identity.user_id,
            action="window.archived",
            entity_type="interview_submission_windows",
            entity_id=window_id,
            old_value=asdict(existing),
            new_value={"archived": True},
        )

    # ── Validation ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_window_times(window: Window) -> None:
        if window.end_time <= window.start_time:
            raise ValidationError(
                message="Window end_time must be after start_time",
                field="end_time",
            )

    def _validate_mappings(self, mappings: List[WindowRoleTemplate]) -> None:
        for m in mappings:
            role = self._roles.get_by_id(m.role_id)
            if role is None:
                raise ValidationError(message=f"Role {m.role_id} not found", field="mappings.role_id")

            template = self._templates.get_by_id(m.template_id)
            if template is None:
                raise ValidationError(
                    message=f"Template {m.template_id} not found", field="mappings.template_id"
                )
            if not template.is_active:
                raise ValidationError(
                    message=f"Template {m.template_id} is not active", field="mappings.template_id"
                )

            if m.selection_weight < 1:
                raise ValidationError(
                    message="selection_weight must be a positive integer",
                    field="mappings.selection_weight",
                )

    def _check_overlap(
        self,
        window: Window,
        mappings: List[WindowRoleTemplate],
        *,
        exclude_window_id: Optional[int] = None,
    ) -> None:
        """
        If allow_resubmission is false, reject overlapping windows for same role.
        """
        if window.allow_resubmission:
            return

        for m in mappings:
            overlaps = self._windows.find_overlapping_windows(
                window.organization_id,
                m.role_id,
                window.start_time,
                window.end_time,
                exclude_window_id=exclude_window_id,
            )
            if overlaps:
                raise ConflictError(
                    message=(
                        f"Overlapping window exists for role {m.role_id} "
                        f"between {window.start_time} and {window.end_time}"
                    )
                )
