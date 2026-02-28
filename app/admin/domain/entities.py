"""
Admin Domain Entities

Pure data classes representing admin domain objects.
No database coupling — these are transport-neutral business objects.

Maps 1:1 with schema.sql tables owned by admin module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums (mirror PostgreSQL ENUM types from schema.sql)
# ---------------------------------------------------------------------------

class TemplateScope(str, Enum):
    """Maps to template_scope PostgreSQL ENUM."""
    PUBLIC = "public"
    ORGANIZATION = "organization"
    PRIVATE = "private"


class InterviewScope(str, Enum):
    """Maps to interview_scope PostgreSQL ENUM."""
    GLOBAL = "global"
    LOCAL = "local"
    ONLY_INVITED = "only_invited"


class DifficultyLevel(str, Enum):
    """Maps to difficulty_level PostgreSQL ENUM."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    """Maps to question_type PostgreSQL ENUM."""
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SITUATIONAL = "situational"
    CODING = "coding"


class CodingTopicType(str, Enum):
    """Maps to coding_topic_type PostgreSQL ENUM."""
    DATA_STRUCTURE = "data_structure"
    ALGORITHM = "algorithm"
    PATTERN = "pattern"
    SYSTEM_DESIGN = "system_design"
    LANGUAGE_SPECIFIC = "language_specific"
    TRAVERSAL = "traversal"


class ContentType(str, Enum):
    """Content types that support the override pattern."""
    TEMPLATE = "template"
    RUBRIC = "rubric"
    ROLE = "role"
    TOPIC = "topic"
    QUESTION = "question"
    CODING_PROBLEM = "coding_problem"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPER_ORG_ID = 1
"""Organization ID for the super/project-owner organization."""

RUBRIC_WEIGHT_TOLERANCE = 0.001
"""Tolerance for rubric dimension weight sum validation (±0.001)."""

IMMUTABLE_OVERRIDE_FIELDS = frozenset({
    "id", "organization_id", "scope", "created_at", "updated_at",
})
"""Fields that CANNOT be overridden via tenant override tables."""


# ---------------------------------------------------------------------------
# Domain Entities
# ---------------------------------------------------------------------------

@dataclass
class Template:
    """
    Interview template definition.

    Maps to: interview_templates table.
    Invariant: Immutable after referenced by any interview_submissions row.
    """
    id: Optional[int]
    name: str
    description: Optional[str]
    scope: TemplateScope
    organization_id: Optional[int]
    template_structure: Dict[str, Any]
    rules: Optional[Dict[str, Any]] = None
    total_estimated_time_minutes: Optional[int] = None
    version: int = 1
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def create_new_version(self) -> "Template":
        """
        Create a new version of this template for immutability-safe editing.

        Returns a *new* Template entity with version incremented and id=None
        so the persistence layer will INSERT rather than UPDATE.
        Deep copies mutable nested structures to prevent aliasing.
        """
        import copy
        return Template(
            id=None,
            name=self.name,
            description=self.description,
            scope=self.scope,
            organization_id=self.organization_id,
            template_structure=copy.deepcopy(self.template_structure),
            rules=copy.deepcopy(self.rules) if self.rules else None,
            total_estimated_time_minutes=self.total_estimated_time_minutes,
            version=self.version + 1,
            is_active=self.is_active,
            created_at=None,
            updated_at=None,
        )


@dataclass
class TemplateRole:
    """
    Template-to-Role mapping.

    Maps to: interview_template_roles table.
    """
    interview_template_id: int
    role_id: int


@dataclass
class TemplateRubric:
    """
    Template-to-Rubric-to-Section mapping.

    Maps to: interview_template_rubrics table.
    """
    id: Optional[int]
    interview_template_id: int
    rubric_id: int
    section_name: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Rubric:
    """
    Evaluation rubric definition.

    Maps to: rubrics table.
    """
    id: Optional[int]
    organization_id: Optional[int]
    name: str
    description: Optional[str]
    scope: TemplateScope
    schema: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class RubricDimension:
    """
    Scoring dimension within a rubric.

    Maps to: rubric_dimensions table.
    Invariant: Dimension weights per rubric MUST sum to 1.0 (±0.001 tolerance).
    """
    id: Optional[int]
    rubric_id: int
    dimension_name: str
    description: Optional[str]
    max_score: Decimal
    weight: Decimal = Decimal("1.0")
    criteria: Optional[Dict[str, Any]] = None
    sequence_order: int = 0
    created_at: Optional[datetime] = None


@dataclass
class Role:
    """
    Interview role definition.

    Maps to: roles table.
    """
    id: Optional[int]
    name: str
    description: Optional[str]
    scope: TemplateScope
    organization_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Topic:
    """
    General interview topic (behavioral / technical / situational).

    Maps to: topics table.
    Invariant: Circular parent references forbidden.
    """
    id: Optional[int]
    name: str
    description: Optional[str]
    parent_topic_id: Optional[int] = None
    scope: TemplateScope = TemplateScope.PUBLIC
    organization_id: Optional[int] = None
    estimated_time_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CodingTopic:
    """
    Specialised coding topic.

    Maps to: coding_topics table.
    """
    id: Optional[int]
    name: str
    description: Optional[str]
    topic_type: CodingTopicType
    parent_topic_id: Optional[int] = None
    scope: TemplateScope = TemplateScope.PUBLIC
    organization_id: Optional[int] = None
    display_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Question:
    """
    Behavioral / technical / situational question.

    Maps to: questions table.
    """
    id: Optional[int]
    question_text: str
    answer_text: Optional[str]
    question_type: QuestionType
    difficulty: DifficultyLevel
    scope: TemplateScope
    organization_id: Optional[int] = None
    source_type: Optional[str] = None
    estimated_time_minutes: int = 5
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CodingProblem:
    """
    Coding assessment problem.

    Maps to: coding_problems table.
    """
    id: Optional[int]
    title: str
    body: str
    difficulty: DifficultyLevel
    scope: TemplateScope
    organization_id: Optional[int] = None
    description: Optional[str] = None
    constraints: Optional[str] = None
    estimated_time_minutes: int = 30
    is_active: bool = True
    source_name: Optional[str] = None
    source_id: Optional[str] = None
    source_slug: Optional[str] = None
    raw_content: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    constraints_structured: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    hints: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    stats: Optional[Dict[str, Any]] = None
    code_snippets: Optional[Dict[str, Any]] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Window:
    """
    Interview submission window.

    Maps to: interview_submission_windows table.
    Invariant: end_time > start_time (enforced in DB CHECK constraint too).
    """
    id: Optional[int]
    organization_id: int
    admin_id: int
    name: str
    scope: InterviewScope
    start_time: datetime
    end_time: datetime
    timezone: str
    max_allowed_submissions: Optional[int] = None
    allow_after_end_time: bool = False
    allow_resubmission: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class WindowRoleTemplate:
    """
    Window-role-template mapping.

    Maps to: window_role_templates table.
    """
    id: Optional[int]
    window_id: int
    role_id: int
    template_id: int
    selection_weight: int = 1
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Override Record (generic across all content types)
# ---------------------------------------------------------------------------

@dataclass
class OverrideRecord:
    """
    Tenant-specific override for a piece of super-org base content.

    Maps to: *_overrides tables (template_overrides, rubric_overrides, etc.).
    These tables do NOT yet exist in schema.sql — managed by persistence layer.

    The override_fields dict contains ONLY the fields being overridden.
    At query time, these are merged onto the base content to produce
    the effective entity (base + override).
    """
    id: Optional[int]
    organization_id: int
    base_content_id: int
    content_type: ContentType
    override_fields: Dict[str, Any]
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
