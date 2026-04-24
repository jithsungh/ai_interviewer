"""
Admin API Routes

FastAPI router for all administrative CRUD endpoints.
Delegates all business logic to domain services.

URL prefix: /api/v1/admin (set in router_registry.py)

Endpoints organised by resource:
    Templates     — CRUD + activate + overrides
    Rubrics       — CRUD + dimensions + overrides
    Roles         — CRUD + overrides
    Topics        — CRUD + overrides
    Questions     — CRUD + overrides
    Coding Problems — CRUD + overrides
    Windows       — CRUD + mappings

Auth: All endpoints require admin JWT (via require_admin dependency).
RBAC: Domain services enforce superadmin / admin / read_only rules.
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import get_db_session_with_commit, require_admin
from app.shared.auth_context import IdentityContext
from app.shared.errors import NotFoundError
from app.shared.observability import get_context_logger

from app.admin.domain.entities import (
    CodingProblem,
    Question,
    Role,
    Rubric,
    RubricDimension,
    Template,
    Topic,
    Window,
    WindowRoleTemplate,
)
from app.auth.persistence import Admin as AuthAdmin, AuthAuditLog

from .contracts import (
    CodingProblemCreateRequest,
    CodingProblemDetailResponse,
    CodingProblemListResponse,
    CodingProblemResponse,
    CodingProblemUpdateRequest,
    DimensionListResponse,
    DimensionResponse,
    MetaInfo,
    OverrideCreateRequest,
    OverrideDetailResponse,
    OverrideResponse,
    OverrideUpdateRequest,
    PaginationMeta,
    QuestionCreateRequest,
    QuestionDetailResponse,
    QuestionListResponse,
    QuestionResponse,
    QuestionUpdateRequest,
    RoleCreateRequest,
    RoleDetailResponse,
    RoleListResponse,
    RoleResponse,
    RoleUpdateRequest,
    RubricCreateRequest,
    RubricDetailResponse,
    RubricListResponse,
    RubricResponse,
    RubricUpdateRequest,
    AuditLogListResponse,
    AuditLogResponse,
    TemplateCreateRequest,
    TemplateDetailResponse,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdateRequest,
    TopicCreateRequest,
    TopicDetailResponse,
    TopicListResponse,
    TopicResponse,
    TopicUpdateRequest,
    WindowCreateRequest,
    WindowDetailResponse,
    WindowListResponse,
    WindowResponse,
    WindowUpdateRequest,
)
from .dependencies import (
    build_coding_problem_service,
    build_question_service,
    build_role_service,
    build_rubric_service,
    build_template_service,
    build_topic_service,
    build_window_service,
)

logger = get_context_logger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _request_id(request: Request) -> Optional[str]:
    """Extract request_id from request state (set by middleware)."""
    return getattr(request.state, "request_id", None)


def _meta(request: Request) -> MetaInfo:
    return MetaInfo(request_id=_request_id(request))


def _pagination(page: int, per_page: int, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=max(1, math.ceil(total / per_page)),
    )


def _template_to_response(t: Template) -> TemplateResponse:
    return TemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        scope=t.scope.value if hasattr(t.scope, "value") else str(t.scope),
        organization_id=t.organization_id,
        template_structure=t.template_structure,
        rules=t.rules,
        total_estimated_time_minutes=t.total_estimated_time_minutes,
        version=t.version,
        is_active=t.is_active,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _rubric_to_response(r: Rubric) -> RubricResponse:
    return RubricResponse(
        id=r.id,
        organization_id=r.organization_id,
        name=r.name,
        description=r.description,
        scope=r.scope.value if hasattr(r.scope, "value") else str(r.scope),
        schema_=r.schema,
        is_active=r.is_active,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _dimension_to_response(d: RubricDimension) -> DimensionResponse:
    return DimensionResponse(
        id=d.id,
        rubric_id=d.rubric_id,
        dimension_name=d.dimension_name,
        description=d.description,
        max_score=d.max_score,
        weight=d.weight,
        criteria=d.criteria,
        sequence_order=d.sequence_order,
        created_at=d.created_at,
    )


def _role_to_response(r: Role) -> RoleResponse:
    return RoleResponse(
        id=r.id,
        name=r.name,
        description=r.description,
        scope=r.scope.value if hasattr(r.scope, "value") else str(r.scope),
        organization_id=r.organization_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _topic_to_response(t: Topic) -> TopicResponse:
    return TopicResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        parent_topic_id=t.parent_topic_id,
        scope=t.scope.value if hasattr(t.scope, "value") else str(t.scope),
        organization_id=t.organization_id,
        estimated_time_minutes=t.estimated_time_minutes,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _question_to_response(q: Question) -> QuestionResponse:
    return QuestionResponse(
        id=q.id,
        question_text=q.question_text,
        answer_text=q.answer_text,
        question_type=q.question_type.value if hasattr(q.question_type, "value") else str(q.question_type),
        difficulty=q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty),
        scope=q.scope.value if hasattr(q.scope, "value") else str(q.scope),
        organization_id=q.organization_id,
        source_type=q.source_type,
        estimated_time_minutes=q.estimated_time_minutes,
        is_active=q.is_active,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


def _coding_problem_to_response(p: CodingProblem) -> CodingProblemResponse:
    return CodingProblemResponse(
        id=p.id,
        title=p.title,
        body=p.body,
        difficulty=p.difficulty.value if hasattr(p.difficulty, "value") else str(p.difficulty),
        scope=p.scope.value if hasattr(p.scope, "value") else str(p.scope),
        organization_id=p.organization_id,
        description=p.description,
        constraints=p.constraints,
        estimated_time_minutes=p.estimated_time_minutes,
        is_active=p.is_active,
        examples=p.examples,
        hints=p.hints,
        code_snippets=p.code_snippets,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _window_to_response(w: Window) -> WindowResponse:
    return WindowResponse(
        id=w.id,
        organization_id=w.organization_id,
        admin_id=w.admin_id,
        name=w.name,
        scope=w.scope.value if hasattr(w.scope, "value") else str(w.scope),
        start_time=w.start_time,
        end_time=w.end_time,
        timezone=w.timezone,
        max_allowed_submissions=w.max_allowed_submissions,
        allow_after_end_time=w.allow_after_end_time,
        allow_resubmission=w.allow_resubmission,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def _audit_log_to_response(entry: AuthAuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=entry.id,
        user_id=entry.user_id,
        event_type=entry.event_type,
        ip_address=str(entry.ip_address) if entry.ip_address else None,
        user_agent=entry.user_agent,
        event_metadata=entry.event_metadata,
        created_at=entry.created_at,
    )


def _override_to_response(o) -> OverrideResponse:
    return OverrideResponse(
        id=o.id,
        organization_id=o.organization_id,
        base_content_id=o.base_content_id,
        content_type=o.content_type.value if hasattr(o.content_type, "value") else str(o.content_type),
        override_fields=o.override_fields,
        is_active=o.is_active,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List templates (paginated)",
)
def list_templates(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TemplateListResponse:
    svc = build_template_service(db)
    templates, total = svc.list_templates(identity, is_active=is_active, page=page, per_page=per_page)
    return TemplateListResponse(
        data=[_template_to_response(t) for t in templates],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/templates",
    response_model=TemplateDetailResponse,
    status_code=201,
    summary="Create template",
)
def create_template(
    request: Request,
    body: TemplateCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TemplateDetailResponse:
    svc = build_template_service(db)
    template = Template(
        id=None,
        name=body.name,
        description=body.description,
        scope=body.scope,
        organization_id=None,  # set by service
        template_structure=body.template_structure,
        rules=body.rules,
        total_estimated_time_minutes=body.total_estimated_time_minutes,
    )
    created = svc.create_template(template, identity)
    logger.info(
        "Template created via API",
        event_type="admin.api.template.created",
        metadata={"template_id": created.id},
    )
    return TemplateDetailResponse(data=_template_to_response(created), meta=_meta(request))


@router.get(
    "/templates/{template_id}",
    response_model=TemplateDetailResponse,
    summary="Get template by ID",
)
def get_template(
    request: Request,
    template_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TemplateDetailResponse:
    svc = build_template_service(db)
    template = svc.get_template(template_id, identity)
    return TemplateDetailResponse(data=_template_to_response(template), meta=_meta(request))


@router.put(
    "/templates/{template_id}",
    response_model=TemplateDetailResponse,
    summary="Update template",
)
def update_template(
    request: Request,
    template_id: int,
    body: TemplateUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TemplateDetailResponse:
    svc = build_template_service(db)
    changes = body.model_dump(exclude_unset=True)
    updated = svc.update_template(template_id, changes, identity)
    return TemplateDetailResponse(data=_template_to_response(updated), meta=_meta(request))


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    summary="Deactivate (soft-delete) template",
)
def delete_template(
    template_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_template_service(db)
    svc.deactivate_template(template_id, identity)
    return Response(status_code=204)


@router.put(
    "/templates/{template_id}/activate",
    response_model=TemplateDetailResponse,
    summary="Activate template",
)
def activate_template(
    request: Request,
    template_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TemplateDetailResponse:
    svc = build_template_service(db)
    activated = svc.activate_template(template_id, identity)
    return TemplateDetailResponse(data=_template_to_response(activated), meta=_meta(request))


# ── Template Overrides ─────────────────────────────────────────────────


@router.post(
    "/templates/{template_id}/overrides",
    response_model=OverrideDetailResponse,
    status_code=201,
    summary="Create override for base template",
)
def create_template_override(
    request: Request,
    template_id: int,
    body: OverrideCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> OverrideDetailResponse:
    svc = build_template_service(db)
    override = svc.create_template_override(template_id, body.override_fields, identity)
    return OverrideDetailResponse(data=_override_to_response(override), meta=_meta(request))


@router.get(
    "/templates/{template_id}/overrides",
    response_model=OverrideDetailResponse,
    summary="Get current org's template override",
)
def get_template_override(
    request: Request,
    template_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> OverrideDetailResponse:
    svc = build_template_service(db)
    _, override = svc.get_effective_template(template_id, identity)
    if override is None:

        raise NotFoundError(resource_type="TemplateOverride", resource_id=template_id)
    return OverrideDetailResponse(data=_override_to_response(override), meta=_meta(request))


@router.put(
    "/templates/{template_id}/overrides",
    response_model=OverrideDetailResponse,
    summary="Update template override",
)
def update_template_override(
    request: Request,
    template_id: int,
    body: OverrideUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> OverrideDetailResponse:
    svc = build_template_service(db)
    updated = svc.update_template_override(template_id, body.override_fields, identity)
    return OverrideDetailResponse(data=_override_to_response(updated), meta=_meta(request))


@router.delete(
    "/templates/{template_id}/overrides",
    status_code=204,
    summary="Delete template override (revert to base)",
)
def delete_template_override(
    template_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_template_service(db)
    svc.delete_template_override(template_id, identity)
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# RUBRIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/rubrics",
    response_model=RubricListResponse,
    summary="List rubrics (paginated)",
)
def list_rubrics(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RubricListResponse:
    svc = build_rubric_service(db)
    rubrics, total = svc.list_rubrics(identity, is_active=is_active, page=page, per_page=per_page)
    return RubricListResponse(
        data=[_rubric_to_response(r) for r in rubrics],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/rubrics",
    response_model=RubricDetailResponse,
    status_code=201,
    summary="Create rubric with dimensions",
)
def create_rubric(
    request: Request,
    body: RubricCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RubricDetailResponse:
    svc = build_rubric_service(db)
    rubric = Rubric(
        id=None,
        organization_id=None,
        name=body.name,
        description=body.description,
        scope=body.scope,
        schema=body.schema_,
    )
    dimensions = [
        RubricDimension(
            id=None,
            rubric_id=0,  # set by service
            dimension_name=d.dimension_name,
            description=d.description,
            max_score=d.max_score,
            weight=d.weight,
            criteria=d.criteria,
            sequence_order=d.sequence_order,
        )
        for d in body.dimensions
    ]
    created = svc.create_rubric(rubric, dimensions, identity)
    return RubricDetailResponse(data=_rubric_to_response(created), meta=_meta(request))


@router.get(
    "/rubrics/{rubric_id}",
    response_model=RubricDetailResponse,
    summary="Get rubric by ID",
)
def get_rubric(
    request: Request,
    rubric_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RubricDetailResponse:
    svc = build_rubric_service(db)
    rubric = svc.get_rubric(rubric_id, identity)
    return RubricDetailResponse(data=_rubric_to_response(rubric), meta=_meta(request))


@router.put(
    "/rubrics/{rubric_id}",
    response_model=RubricDetailResponse,
    summary="Update rubric",
)
def update_rubric(
    request: Request,
    rubric_id: int,
    body: RubricUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RubricDetailResponse:
    svc = build_rubric_service(db)
    changes = body.model_dump(exclude_unset=True, by_alias=False)
    # Remap schema_ → schema for domain entity
    if "schema_" in changes:
        changes["schema"] = changes.pop("schema_")
    dimensions_data = changes.pop("dimensions", None)
    dimensions = None
    if dimensions_data is not None:
        dimensions = [
            RubricDimension(
                id=None,
                rubric_id=rubric_id,
                dimension_name=d["dimension_name"],
                description=d.get("description"),
                max_score=d["max_score"],
                weight=d["weight"],
                criteria=d.get("criteria"),
                sequence_order=d.get("sequence_order", 0),
            )
            for d in dimensions_data
        ]
    updated = svc.update_rubric(rubric_id, changes, dimensions, identity)
    return RubricDetailResponse(data=_rubric_to_response(updated), meta=_meta(request))


@router.delete(
    "/rubrics/{rubric_id}",
    status_code=204,
    summary="Deactivate (soft-delete) rubric",
)
def delete_rubric(
    rubric_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_rubric_service(db)
    svc.deactivate_rubric(rubric_id, identity)
    return Response(status_code=204)


@router.get(
    "/rubrics/{rubric_id}/dimensions",
    response_model=DimensionListResponse,
    summary="Get rubric dimensions",
)
def get_rubric_dimensions(
    request: Request,
    rubric_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> DimensionListResponse:
    svc = build_rubric_service(db)
    dimensions = svc.get_dimensions(rubric_id, identity)
    return DimensionListResponse(
        data=[_dimension_to_response(d) for d in dimensions],
        meta=_meta(request),
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROLE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="List roles (paginated)",
)
def list_roles(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RoleListResponse:
    svc = build_role_service(db)
    roles, total = svc.list_roles(identity, page=page, per_page=per_page)
    return RoleListResponse(
        data=[_role_to_response(r) for r in roles],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/roles",
    response_model=RoleDetailResponse,
    status_code=201,
    summary="Create role",
)
def create_role(
    request: Request,
    body: RoleCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RoleDetailResponse:
    svc = build_role_service(db)
    role = Role(
        id=None,
        name=body.name,
        description=body.description,
        scope=body.scope,
        organization_id=None,
    )
    created = svc.create_role(role, identity)
    return RoleDetailResponse(data=_role_to_response(created), meta=_meta(request))


@router.get(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    summary="Get role by ID",
)
def get_role(
    request: Request,
    role_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RoleDetailResponse:
    svc = build_role_service(db)
    role = svc.get_role(role_id, identity)
    return RoleDetailResponse(data=_role_to_response(role), meta=_meta(request))


@router.put(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    summary="Update role",
)
def update_role(
    request: Request,
    role_id: int,
    body: RoleUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> RoleDetailResponse:
    svc = build_role_service(db)
    changes = body.model_dump(exclude_unset=True)
    updated = svc.update_role(role_id, changes, identity)
    return RoleDetailResponse(data=_role_to_response(updated), meta=_meta(request))


# ═══════════════════════════════════════════════════════════════════════════
# TOPIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/topics",
    response_model=TopicListResponse,
    summary="List topics (paginated)",
)
def list_topics(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TopicListResponse:
    svc = build_topic_service(db)
    topics, total = svc.list_topics(identity, page=page, per_page=per_page)
    return TopicListResponse(
        data=[_topic_to_response(t) for t in topics],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/topics",
    response_model=TopicDetailResponse,
    status_code=201,
    summary="Create topic",
)
def create_topic(
    request: Request,
    body: TopicCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TopicDetailResponse:
    svc = build_topic_service(db)
    topic = Topic(
        id=None,
        name=body.name,
        description=body.description,
        parent_topic_id=body.parent_topic_id,
        scope=body.scope,
        organization_id=None,
        estimated_time_minutes=body.estimated_time_minutes,
    )
    created = svc.create_topic(topic, identity)
    return TopicDetailResponse(data=_topic_to_response(created), meta=_meta(request))


@router.get(
    "/topics/{topic_id}",
    response_model=TopicDetailResponse,
    summary="Get topic by ID",
)
def get_topic(
    request: Request,
    topic_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TopicDetailResponse:
    svc = build_topic_service(db)
    topic = svc.get_topic(topic_id, identity)
    return TopicDetailResponse(data=_topic_to_response(topic), meta=_meta(request))


@router.put(
    "/topics/{topic_id}",
    response_model=TopicDetailResponse,
    summary="Update topic",
)
def update_topic(
    request: Request,
    topic_id: int,
    body: TopicUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> TopicDetailResponse:
    svc = build_topic_service(db)
    changes = body.model_dump(exclude_unset=True)
    updated = svc.update_topic(topic_id, changes, identity)
    return TopicDetailResponse(data=_topic_to_response(updated), meta=_meta(request))


# ═══════════════════════════════════════════════════════════════════════════
# QUESTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    summary="List questions (paginated)",
)
def list_questions(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    question_type: Optional[str] = Query(None),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> QuestionListResponse:
    # Treat "undefined" string from frontend as None
    if question_type in ("undefined", "null", ""):
        question_type = None
    svc = build_question_service(db)
    questions, total = svc.list_questions(
        identity, is_active=is_active, question_type=question_type, page=page, per_page=per_page,
    )
    return QuestionListResponse(
        data=[_question_to_response(q) for q in questions],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/questions",
    response_model=QuestionDetailResponse,
    status_code=201,
    summary="Create question",
)
def create_question(
    request: Request,
    body: QuestionCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> QuestionDetailResponse:
    svc = build_question_service(db)
    question = Question(
        id=None,
        question_text=body.question_text,
        answer_text=body.answer_text,
        question_type=body.question_type,
        difficulty=body.difficulty,
        scope=body.scope,
        organization_id=None,
        source_type=body.source_type,
        estimated_time_minutes=body.estimated_time_minutes,
        is_active=body.is_active,
    )
    created = svc.create_question(question, identity)
    return QuestionDetailResponse(data=_question_to_response(created), meta=_meta(request))


@router.get(
    "/questions/{question_id}",
    response_model=QuestionDetailResponse,
    summary="Get question by ID",
)
def get_question(
    request: Request,
    question_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> QuestionDetailResponse:
    svc = build_question_service(db)
    question = svc.get_question(question_id, identity)
    return QuestionDetailResponse(data=_question_to_response(question), meta=_meta(request))


@router.put(
    "/questions/{question_id}",
    response_model=QuestionDetailResponse,
    summary="Update question",
)
def update_question(
    request: Request,
    question_id: int,
    body: QuestionUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> QuestionDetailResponse:
    svc = build_question_service(db)
    changes = body.model_dump(exclude_unset=True)
    updated = svc.update_question(question_id, changes, identity)
    return QuestionDetailResponse(data=_question_to_response(updated), meta=_meta(request))


@router.delete(
    "/questions/{question_id}",
    status_code=204,
    summary="Deactivate (soft-delete) question",
)
def delete_question(
    question_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_question_service(db)
    # Deactivate via update
    svc.update_question(question_id, {"is_active": False}, identity)
    return Response(status_code=204)


# ── Question Overrides ─────────────────────────────────────────────────


@router.post(
    "/questions/{question_id}/overrides",
    response_model=OverrideDetailResponse,
    status_code=201,
    summary="Create override for base question",
)
def create_question_override(
    request: Request,
    question_id: int,
    body: OverrideCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> OverrideDetailResponse:
    svc = build_question_service(db)
    override = svc.create_question_override(question_id, body.override_fields, identity)
    return OverrideDetailResponse(data=_override_to_response(override), meta=_meta(request))


# ═══════════════════════════════════════════════════════════════════════════
# CODING PROBLEM ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/coding-problems",
    response_model=CodingProblemListResponse,
    summary="List coding problems (paginated)",
)
def list_coding_problems(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    difficulty: Optional[str] = Query(None),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> CodingProblemListResponse:
    svc = build_coding_problem_service(db)
    problems, total = svc.list_problems(
        identity, is_active=is_active, difficulty=difficulty, page=page, per_page=per_page,
    )
    return CodingProblemListResponse(
        data=[_coding_problem_to_response(p) for p in problems],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/coding-problems",
    response_model=CodingProblemDetailResponse,
    status_code=201,
    summary="Create coding problem",
)
def create_coding_problem(
    request: Request,
    body: CodingProblemCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> CodingProblemDetailResponse:
    svc = build_coding_problem_service(db)
    problem = CodingProblem(
        id=None,
        title=body.title,
        body=body.body,
        difficulty=body.difficulty,
        scope=body.scope,
        organization_id=None,
        description=body.description,
        constraints=body.constraints,
        estimated_time_minutes=body.estimated_time_minutes,
        is_active=body.is_active,
        examples=body.examples or [],
        hints=body.hints or [],
        code_snippets=body.code_snippets or {},
    )
    created = svc.create_problem(problem, identity)
    return CodingProblemDetailResponse(data=_coding_problem_to_response(created), meta=_meta(request))


@router.get(
    "/coding-problems/{problem_id}",
    response_model=CodingProblemDetailResponse,
    summary="Get coding problem by ID",
)
def get_coding_problem(
    request: Request,
    problem_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> CodingProblemDetailResponse:
    svc = build_coding_problem_service(db)
    problem = svc.get_problem(problem_id, identity)
    return CodingProblemDetailResponse(data=_coding_problem_to_response(problem), meta=_meta(request))


@router.put(
    "/coding-problems/{problem_id}",
    response_model=CodingProblemDetailResponse,
    summary="Update coding problem",
)
def update_coding_problem(
    request: Request,
    problem_id: int,
    body: CodingProblemUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> CodingProblemDetailResponse:
    svc = build_coding_problem_service(db)
    changes = body.model_dump(exclude_unset=True)
    updated = svc.update_problem(problem_id, changes, identity)
    return CodingProblemDetailResponse(data=_coding_problem_to_response(updated), meta=_meta(request))


@router.delete(
    "/coding-problems/{problem_id}",
    status_code=204,
    summary="Deactivate (soft-delete) coding problem",
)
def delete_coding_problem(
    problem_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_coding_problem_service(db)
    svc.update_problem(problem_id, {"is_active": False}, identity)
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# WINDOW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/windows",
    response_model=WindowListResponse,
    summary="List windows (paginated)",
)
def list_windows(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> WindowListResponse:
    svc = build_window_service(db)
    windows, total = svc.list_windows(identity, page=page, per_page=per_page)
    return WindowListResponse(
        data=[_window_to_response(w) for w in windows],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )


@router.post(
    "/windows",
    response_model=WindowDetailResponse,
    status_code=201,
    summary="Create window with role-template mappings",
)
def create_window(
    request: Request,
    body: WindowCreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> WindowDetailResponse:
    svc = build_window_service(db)
    window = Window(
        id=None,
        organization_id=0,  # set by service
        admin_id=identity.user_id,
        name=body.name,
        scope=body.scope,
        start_time=body.start_time,
        end_time=body.end_time,
        timezone=body.timezone,
        max_allowed_submissions=body.max_allowed_submissions,
        allow_after_end_time=body.allow_after_end_time,
        allow_resubmission=body.allow_resubmission,
    )
    mappings = [
        WindowRoleTemplate(
            id=None,
            window_id=0,  # set by service
            role_id=m.role_id,
            template_id=m.template_id,
            selection_weight=m.selection_weight,
        )
        for m in body.mappings
    ]
    created = svc.create_window(window, mappings, identity)
    return WindowDetailResponse(data=_window_to_response(created), meta=_meta(request))


@router.get(
    "/windows/{window_id}",
    response_model=WindowDetailResponse,
    summary="Get window by ID",
)
def get_window(
    request: Request,
    window_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> WindowDetailResponse:
    svc = build_window_service(db)
    window = svc.get_window(window_id, identity)
    return WindowDetailResponse(data=_window_to_response(window), meta=_meta(request))


@router.put(
    "/windows/{window_id}",
    response_model=WindowDetailResponse,
    summary="Update window",
)
def update_window(
    request: Request,
    window_id: int,
    body: WindowUpdateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> WindowDetailResponse:
    svc = build_window_service(db)
    changes = body.model_dump(exclude_unset=True)
    mappings_data = changes.pop("mappings", None)
    mappings = None
    if mappings_data is not None:
        mappings = [
            WindowRoleTemplate(
                id=None,
                window_id=window_id,
                role_id=m["role_id"],
                template_id=m["template_id"],
                selection_weight=m.get("selection_weight", 1),
            )
            for m in mappings_data
        ]
    updated = svc.update_window(window_id, changes, mappings, identity)
    return WindowDetailResponse(data=_window_to_response(updated), meta=_meta(request))


@router.delete(
    "/windows/{window_id}",
    status_code=204,
    summary="Archive window",
)
def delete_window(
    window_id: int,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    svc = build_window_service(db)
    svc.archive_window(window_id, identity)
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="List auth audit logs (paginated)",
)
def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None, ge=1),
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
) -> AuditLogListResponse:
    query = db.query(AuthAuditLog)

    if not identity.is_superadmin():
        query = query.join(AuthAdmin, AuthAdmin.user_id == AuthAuditLog.user_id).filter(
            AuthAdmin.organization_id == identity.organization_id
        )

    if event_type:
        query = query.filter(AuthAuditLog.event_type == event_type)
    if user_id is not None:
        query = query.filter(AuthAuditLog.user_id == user_id)

    total = query.count()
    offset = (page - 1) * per_page
    rows = (
        query.order_by(AuthAuditLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return AuditLogListResponse(
        data=[_audit_log_to_response(entry) for entry in rows],
        pagination=_pagination(page, per_page, total),
        meta=_meta(request),
    )
