"""
Admin API Contracts

Pydantic request/response models for all admin API endpoints.
Single source of truth for admin API data transfer objects.

Reuses domain enums from app.admin.domain.entities to prevent duplication.
Reuses shared error types from app.shared.errors.

No business logic — validation of format and types only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums — reuse from domain entities (no duplication)
# ---------------------------------------------------------------------------

from app.admin.domain.entities import (
    ContentType,
    CodingTopicType,
    DifficultyLevel,
    InterviewScope,
    QuestionType,
    TemplateScope,
)


# ═══════════════════════════════════════════════════════════════════════════
# Shared Response Wrappers
# ═══════════════════════════════════════════════════════════════════════════


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    page: int
    per_page: int
    total: int
    total_pages: int


class MetaInfo(BaseModel):
    """Response metadata."""
    request_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Template Contracts
# ═══════════════════════════════════════════════════════════════════════════


class TemplateCreateRequest(BaseModel):
    """Request body for POST /templates."""
    name: str = Field(..., max_length=255, description="Template name")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    scope: TemplateScope = Field(..., description="Template scope")
    template_structure: Dict[str, Any] = Field(..., description="Template JSON structure")
    rules: Optional[Dict[str, Any]] = Field(None, description="Template rules")
    total_estimated_time_minutes: Optional[int] = Field(None, gt=0, description="Estimated time in minutes")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "name": "Senior Engineer Template",
                "description": "Full technical interview template",
                "scope": "organization",
                "template_structure": {"sections": [{"name": "intro", "duration_minutes": 5}]},
                "total_estimated_time_minutes": 60,
            }]
        }
    }


class TemplateUpdateRequest(BaseModel):
    """Request body for PUT /templates/{id}."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scope: Optional[TemplateScope] = None
    template_structure: Optional[Dict[str, Any]] = None
    rules: Optional[Dict[str, Any]] = None
    total_estimated_time_minutes: Optional[int] = Field(None, gt=0)


class TemplateResponse(BaseModel):
    """Single template in response payload."""
    id: int
    name: str
    description: Optional[str] = None
    scope: str
    organization_id: Optional[int] = None
    template_structure: Dict[str, Any]
    rules: Optional[Dict[str, Any]] = None
    total_estimated_time_minutes: Optional[int] = None
    version: int = 1
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TemplateDetailResponse(BaseModel):
    """Response for GET /templates/{id}."""
    data: TemplateResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class TemplateListResponse(BaseModel):
    """Response for GET /templates."""
    data: List[TemplateResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Contracts
# ═══════════════════════════════════════════════════════════════════════════


class DimensionRequest(BaseModel):
    """A single rubric dimension in request payload."""
    dimension_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    max_score: Decimal = Field(..., gt=0)
    weight: Decimal = Field(..., gt=0, le=1)
    criteria: Optional[Dict[str, Any]] = None
    sequence_order: int = Field(0, ge=0)


class RubricCreateRequest(BaseModel):
    """Request body for POST /rubrics."""
    name: str = Field(..., max_length=255, description="Rubric name")
    description: Optional[str] = Field(None, max_length=1000)
    scope: TemplateScope = Field(..., description="Rubric scope")
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema", description="Rubric schema JSON")
    dimensions: List[DimensionRequest] = Field(default_factory=list, description="Rubric dimensions")

    model_config = {"populate_by_name": True}


class RubricUpdateRequest(BaseModel):
    """Request body for PUT /rubrics/{id}."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scope: Optional[TemplateScope] = None
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    dimensions: Optional[List[DimensionRequest]] = None

    model_config = {"populate_by_name": True}


class DimensionResponse(BaseModel):
    """A single rubric dimension in response payload."""
    id: Optional[int] = None
    rubric_id: int
    dimension_name: str
    description: Optional[str] = None
    max_score: Decimal
    weight: Decimal
    criteria: Optional[Dict[str, Any]] = None
    sequence_order: int = 0
    created_at: Optional[datetime] = None


class RubricResponse(BaseModel):
    """Single rubric in response payload."""
    id: int
    organization_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    scope: str
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class RubricDetailResponse(BaseModel):
    """Response for GET /rubrics/{id}."""
    data: RubricResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class RubricListResponse(BaseModel):
    """Response for GET /rubrics."""
    data: List[RubricResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


class DimensionListResponse(BaseModel):
    """Response for GET /rubrics/{id}/dimensions."""
    data: List[DimensionResponse]
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Role Contracts
# ═══════════════════════════════════════════════════════════════════════════


class RoleCreateRequest(BaseModel):
    """Request body for POST /roles."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scope: TemplateScope = Field(...)


class RoleUpdateRequest(BaseModel):
    """Request body for PUT /roles/{id}."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scope: Optional[TemplateScope] = None


class RoleResponse(BaseModel):
    """Single role in response payload."""
    id: int
    name: str
    description: Optional[str] = None
    scope: str
    organization_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RoleDetailResponse(BaseModel):
    """Response for GET /roles/{id}."""
    data: RoleResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class RoleListResponse(BaseModel):
    """Response for GET /roles."""
    data: List[RoleResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Topic Contracts
# ═══════════════════════════════════════════════════════════════════════════


class TopicCreateRequest(BaseModel):
    """Request body for POST /topics."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    parent_topic_id: Optional[int] = None
    scope: TemplateScope = Field(default=TemplateScope.PUBLIC)
    estimated_time_minutes: Optional[int] = Field(None, gt=0)


class TopicUpdateRequest(BaseModel):
    """Request body for PUT /topics/{id}."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    parent_topic_id: Optional[int] = None
    scope: Optional[TemplateScope] = None
    estimated_time_minutes: Optional[int] = Field(None, gt=0)


class TopicResponse(BaseModel):
    """Single topic in response payload."""
    id: int
    name: str
    description: Optional[str] = None
    parent_topic_id: Optional[int] = None
    scope: str
    organization_id: Optional[int] = None
    estimated_time_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TopicDetailResponse(BaseModel):
    """Response for GET /topics/{id}."""
    data: TopicResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class TopicListResponse(BaseModel):
    """Response for GET /topics."""
    data: List[TopicResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Question Contracts
# ═══════════════════════════════════════════════════════════════════════════


class QuestionCreateRequest(BaseModel):
    """Request body for POST /questions."""
    question_text: str = Field(..., description="Question text")
    answer_text: Optional[str] = None
    question_type: QuestionType = Field(...)
    difficulty: DifficultyLevel = Field(...)
    scope: TemplateScope = Field(...)
    source_type: Optional[str] = None
    estimated_time_minutes: int = Field(5, gt=0)
    is_active: bool = True


class QuestionUpdateRequest(BaseModel):
    """Request body for PUT /questions/{id}."""
    question_text: Optional[str] = None
    answer_text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    difficulty: Optional[DifficultyLevel] = None
    scope: Optional[TemplateScope] = None
    source_type: Optional[str] = None
    estimated_time_minutes: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class QuestionResponse(BaseModel):
    """Single question in response payload."""
    id: int
    question_text: str
    answer_text: Optional[str] = None
    question_type: str
    difficulty: str
    scope: str
    organization_id: Optional[int] = None
    source_type: Optional[str] = None
    estimated_time_minutes: int = 5
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QuestionDetailResponse(BaseModel):
    """Response for GET /questions/{id}."""
    data: QuestionResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class QuestionListResponse(BaseModel):
    """Response for GET /questions."""
    data: List[QuestionResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem Contracts
# ═══════════════════════════════════════════════════════════════════════════


class CodingProblemCreateRequest(BaseModel):
    """Request body for POST /coding-problems."""
    title: str = Field(..., max_length=500)
    body: str = Field(...)
    difficulty: DifficultyLevel = Field(...)
    scope: TemplateScope = Field(...)
    description: Optional[str] = None
    constraints: Optional[str] = None
    estimated_time_minutes: int = Field(30, gt=0)
    is_active: bool = True
    examples: Optional[List[Dict[str, Any]]] = None
    hints: Optional[List[Dict[str, Any]]] = None
    code_snippets: Optional[Dict[str, Any]] = None


class CodingProblemUpdateRequest(BaseModel):
    """Request body for PUT /coding-problems/{id}."""
    title: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    scope: Optional[TemplateScope] = None
    description: Optional[str] = None
    constraints: Optional[str] = None
    estimated_time_minutes: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    examples: Optional[List[Dict[str, Any]]] = None
    hints: Optional[List[Dict[str, Any]]] = None
    code_snippets: Optional[Dict[str, Any]] = None


class CodingProblemResponse(BaseModel):
    """Single coding problem in response payload."""
    id: int
    title: str
    body: str
    difficulty: str
    scope: str
    organization_id: Optional[int] = None
    description: Optional[str] = None
    constraints: Optional[str] = None
    estimated_time_minutes: int = 30
    is_active: bool = True
    examples: Optional[List[Dict[str, Any]]] = None
    hints: Optional[List[Dict[str, Any]]] = None
    code_snippets: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CodingProblemDetailResponse(BaseModel):
    """Response for GET /coding-problems/{id}."""
    data: CodingProblemResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class CodingProblemListResponse(BaseModel):
    """Response for GET /coding-problems."""
    data: List[CodingProblemResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Window Contracts
# ═══════════════════════════════════════════════════════════════════════════


class WindowMappingRequest(BaseModel):
    """A single window-role-template mapping in request payload."""
    role_id: int = Field(..., gt=0)
    template_id: int = Field(..., gt=0)
    selection_weight: int = Field(1, ge=1)


class WindowCreateRequest(BaseModel):
    """Request body for POST /windows."""
    name: str = Field(..., max_length=255)
    scope: InterviewScope = Field(...)
    start_time: datetime = Field(...)
    end_time: datetime = Field(...)
    timezone: str = Field(..., max_length=50)
    max_allowed_submissions: Optional[int] = Field(None, gt=0)
    allow_after_end_time: bool = False
    allow_resubmission: bool = False
    mappings: List[WindowMappingRequest] = Field(..., min_length=1, description="Must include >= 1 mapping")


class WindowUpdateRequest(BaseModel):
    """Request body for PUT /windows/{id}."""
    name: Optional[str] = Field(None, max_length=255)
    scope: Optional[InterviewScope] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: Optional[str] = Field(None, max_length=50)
    max_allowed_submissions: Optional[int] = Field(None, gt=0)
    allow_after_end_time: Optional[bool] = None
    allow_resubmission: Optional[bool] = None
    mappings: Optional[List[WindowMappingRequest]] = None


class WindowMappingResponse(BaseModel):
    """A single window-role-template mapping in response payload."""
    id: Optional[int] = None
    window_id: int
    role_id: int
    template_id: int
    selection_weight: int = 1
    created_at: Optional[datetime] = None


class WindowResponse(BaseModel):
    """Single window in response payload."""
    id: int
    organization_id: int
    admin_id: int
    name: str
    scope: str
    start_time: datetime
    end_time: datetime
    timezone: str
    max_allowed_submissions: Optional[int] = None
    allow_after_end_time: bool = False
    allow_resubmission: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WindowDetailResponse(BaseModel):
    """Response for GET /windows/{id}."""
    data: WindowResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


class WindowListResponse(BaseModel):
    """Response for GET /windows."""
    data: List[WindowResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Audit Log Contracts
# ═══════════════════════════════════════════════════════════════════════════


class AuditLogResponse(BaseModel):
    """Single audit log entry in response payload."""
    id: int
    user_id: Optional[int] = None
    event_type: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class AuditLogListResponse(BaseModel):
    """Response for GET /audit-logs."""
    data: List[AuditLogResponse]
    pagination: PaginationMeta
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Override Contracts (generic across all content types)
# ═══════════════════════════════════════════════════════════════════════════


class OverrideCreateRequest(BaseModel):
    """Request body for POST /{resource}/{id}/overrides."""
    override_fields: Dict[str, Any] = Field(
        ..., description="Fields to override on base content"
    )


class OverrideUpdateRequest(BaseModel):
    """Request body for PUT /{resource}/{id}/overrides."""
    override_fields: Dict[str, Any] = Field(
        ..., description="Updated override fields"
    )


class OverrideResponse(BaseModel):
    """Single override record in response payload."""
    id: int
    organization_id: int
    base_content_id: int
    content_type: str
    override_fields: Dict[str, Any]
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OverrideDetailResponse(BaseModel):
    """Response for GET /{resource}/{id}/overrides."""
    data: OverrideResponse
    meta: MetaInfo = Field(default_factory=MetaInfo)


# ═══════════════════════════════════════════════════════════════════════════
# Generic Success Response
# ═══════════════════════════════════════════════════════════════════════════


class SuccessResponse(BaseModel):
    """Generic success response for operations that return no body."""
    message: str = "Operation successful"
    meta: MetaInfo = Field(default_factory=MetaInfo)
