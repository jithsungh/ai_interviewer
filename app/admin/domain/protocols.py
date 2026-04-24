"""
Admin Repository Protocols

Abstract interfaces that the persistence layer MUST implement.
Domain services depend on these protocols — never on concrete DB classes.

Uses typing.Protocol for structural subtyping (duck typing check at type-check time).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .entities import (
    CodingProblem,
    CodingTopic,
    ContentType,
    OverrideRecord,
    Question,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRole,
    TemplateRubric,
    Topic,
    Window,
    WindowRoleTemplate,
)


# ---------------------------------------------------------------------------
# Template Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class TemplateRepository(Protocol):
    """CRUD operations for interview_templates."""

    def get_by_id(self, template_id: int) -> Optional[Template]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Template]: ...

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
    ) -> int: ...

    def create(self, template: Template) -> Template: ...

    def update(self, template: Template) -> Template: ...

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool: ...

    def get_latest_version(self, name: str, organization_id: Optional[int]) -> Optional[int]: ...

    # Template-Role mappings
    def set_template_roles(self, template_id: int, role_ids: List[int]) -> None: ...
    def get_template_roles(self, template_id: int) -> List[TemplateRole]: ...

    # Template-Rubric mappings
    def set_template_rubrics(self, template_id: int, rubrics: List[TemplateRubric]) -> None: ...
    def get_template_rubrics(self, template_id: int) -> List[TemplateRubric]: ...


# ---------------------------------------------------------------------------
# Rubric Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class RubricRepository(Protocol):
    """CRUD operations for rubrics and rubric_dimensions."""

    def get_by_id(self, rubric_id: int) -> Optional[Rubric]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Rubric]: ...

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
    ) -> int: ...

    def create(self, rubric: Rubric) -> Rubric: ...

    def update(self, rubric: Rubric) -> Rubric: ...

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool: ...

    # Dimensions
    def get_dimensions(self, rubric_id: int) -> List[RubricDimension]: ...
    def set_dimensions(self, rubric_id: int, dimensions: List[RubricDimension]) -> None: ...


# ---------------------------------------------------------------------------
# Role Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class RoleRepository(Protocol):
    """CRUD operations for roles."""

    def get_by_id(self, role_id: int) -> Optional[Role]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Role]: ...

    def count_for_organization(self, organization_id: int) -> int: ...

    def create(self, role: Role) -> Role: ...

    def update(self, role: Role) -> Role: ...

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Topic Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class TopicRepository(Protocol):
    """CRUD operations for topics and coding_topics."""

    # General topics
    def get_topic_by_id(self, topic_id: int) -> Optional[Topic]: ...

    def list_topics_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Topic]: ...

    def count_topics_for_organization(self, organization_id: int) -> int: ...

    def create_topic(self, topic: Topic) -> Topic: ...

    def update_topic(self, topic: Topic) -> Topic: ...

    def topic_exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool: ...

    def get_topic_ancestors(self, topic_id: int) -> List[int]:
        """Return list of ancestor topic IDs (for cycle detection)."""
        ...

    # Coding topics
    def get_coding_topic_by_id(self, topic_id: int) -> Optional[CodingTopic]: ...

    def list_coding_topics_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[CodingTopic]: ...

    def count_coding_topics_for_organization(self, organization_id: int) -> int: ...

    def create_coding_topic(self, topic: CodingTopic) -> CodingTopic: ...

    def update_coding_topic(self, topic: CodingTopic) -> CodingTopic: ...

    def get_coding_topic_ancestors(self, topic_id: int) -> List[int]:
        """Return list of ancestor coding-topic IDs (for cycle detection)."""
        ...


# ---------------------------------------------------------------------------
# Question Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class QuestionRepository(Protocol):
    """CRUD operations for questions."""

    def get_by_id(self, question_id: int) -> Optional[Question]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        question_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Question]: ...

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        question_type: Optional[str] = None,
    ) -> int: ...

    def create(self, question: Question) -> Question: ...

    def update(self, question: Question) -> Question: ...


# ---------------------------------------------------------------------------
# Coding Problem Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class CodingProblemRepository(Protocol):
    """CRUD operations for coding_problems."""

    def get_by_id(self, problem_id: int) -> Optional[CodingProblem]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        difficulty: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[CodingProblem]: ...

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        difficulty: Optional[str] = None,
    ) -> int: ...

    def create(self, problem: CodingProblem) -> CodingProblem: ...

    def update(self, problem: CodingProblem) -> CodingProblem: ...


# ---------------------------------------------------------------------------
# Window Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class WindowRepository(Protocol):
    """CRUD operations for interview_submission_windows and window_role_templates."""

    def get_by_id(self, window_id: int) -> Optional[Window]: ...

    def list_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Window]: ...

    def count_for_organization(self, organization_id: int) -> int: ...

    def create(self, window: Window) -> Window: ...

    def update(self, window: Window) -> Window: ...

    def delete(self, window_id: int) -> None: ...

    def find_overlapping_windows(
        self,
        organization_id: int,
        role_id: int,
        start_time: Any,
        end_time: Any,
        *,
        exclude_window_id: Optional[int] = None,
    ) -> List[Window]: ...

    # Window-Role-Template mappings
    def get_mappings(self, window_id: int) -> List[WindowRoleTemplate]: ...
    def set_mappings(self, window_id: int, mappings: List[WindowRoleTemplate]) -> None: ...


# ---------------------------------------------------------------------------
# Submission Repository  (read-only for admin domain — immutability checks)
# ---------------------------------------------------------------------------

@runtime_checkable
class SubmissionRepository(Protocol):
    """Read-only access to interview_submissions for immutability enforcement."""

    def template_is_in_use(self, template_id: int) -> bool:
        """Return True if any submission references this template."""
        ...

    def rubric_is_in_use(self, rubric_id: int) -> bool:
        """Return True if any template referencing this rubric has submissions."""
        ...

    def role_is_in_use(self, role_id: int) -> bool:
        """Return True if any submission references this role."""
        ...

    def window_has_submissions(self, window_id: int) -> bool:
        """Return True if any submission references this window."""
        ...


# ---------------------------------------------------------------------------
# Override Repository (generic for all content types)
# ---------------------------------------------------------------------------

@runtime_checkable
class OverrideRepository(Protocol):
    """
    CRUD operations for *_overrides tables.

    A single protocol handles all override tables because the override pattern
    is uniform across content types.
    """

    def get_override(
        self,
        organization_id: int,
        base_content_id: int,
        content_type: ContentType,
    ) -> Optional[OverrideRecord]: ...

    def create_override(self, override: OverrideRecord) -> OverrideRecord: ...

    def update_override(self, override: OverrideRecord) -> OverrideRecord: ...

    def delete_override(
        self,
        organization_id: int,
        base_content_id: int,
        content_type: ContentType,
    ) -> bool: ...

    def list_overrides_for_organization(
        self,
        organization_id: int,
        content_type: ContentType,
    ) -> List[OverrideRecord]: ...

    def mark_overrides_stale(
        self,
        base_content_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Deactivate all tenant overrides for a base content item.
        Called when base content is deactivated.
        Returns count of overrides marked stale.
        """
        ...


# ---------------------------------------------------------------------------
# Audit Log Repository
# ---------------------------------------------------------------------------

@runtime_checkable
class AuditLogRepository(Protocol):
    """Insert-only access to audit_logs for domain event recording."""

    def log(
        self,
        *,
        organization_id: Optional[int],
        actor_user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None: ...
