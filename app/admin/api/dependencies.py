"""
Admin API Dependency Factories

Constructs domain service instances with injected repository dependencies.
Follows the same pattern as auth/api/routes.py::_build_auth_service().

Each factory accepts a SQLAlchemy Session and returns a fully wired service.
No business logic — pure wiring.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.admin.domain.services import (
    CodingProblemService,
    QuestionService,
    RoleService,
    RubricService,
    TemplateService,
    TopicService,
    WindowService,
)
from app.admin.persistence import (
    SqlAuditLogRepository,
    SqlCodingProblemRepository,
    SqlOverrideRepository,
    SqlQuestionRepository,
    SqlRoleRepository,
    SqlRubricRepository,
    SqlSubmissionRepository,
    SqlTemplateRepository,
    SqlTopicRepository,
    SqlWindowRepository,
)


def build_template_service(session: Session) -> TemplateService:
    """Construct TemplateService with all repository dependencies."""
    return TemplateService(
        template_repo=SqlTemplateRepository(session),
        submission_repo=SqlSubmissionRepository(session),
        override_repo=SqlOverrideRepository(session),
        rubric_repo=SqlRubricRepository(session),
        role_repo=SqlRoleRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_rubric_service(session: Session) -> RubricService:
    """Construct RubricService with all repository dependencies."""
    return RubricService(
        rubric_repo=SqlRubricRepository(session),
        submission_repo=SqlSubmissionRepository(session),
        override_repo=SqlOverrideRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_role_service(session: Session) -> RoleService:
    """Construct RoleService with all repository dependencies."""
    return RoleService(
        role_repo=SqlRoleRepository(session),
        submission_repo=SqlSubmissionRepository(session),
        override_repo=SqlOverrideRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_topic_service(session: Session) -> TopicService:
    """Construct TopicService with all repository dependencies."""
    return TopicService(
        topic_repo=SqlTopicRepository(session),
        override_repo=SqlOverrideRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_question_service(session: Session) -> QuestionService:
    """Construct QuestionService with all repository dependencies."""
    return QuestionService(
        question_repo=SqlQuestionRepository(session),
        override_repo=SqlOverrideRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_coding_problem_service(session: Session) -> CodingProblemService:
    """Construct CodingProblemService with all repository dependencies."""
    return CodingProblemService(
        problem_repo=SqlCodingProblemRepository(session),
        override_repo=SqlOverrideRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def build_window_service(session: Session) -> WindowService:
    """Construct WindowService with all repository dependencies."""
    return WindowService(
        window_repo=SqlWindowRepository(session),
        role_repo=SqlRoleRepository(session),
        template_repo=SqlTemplateRepository(session),
        submission_repo=SqlSubmissionRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )
