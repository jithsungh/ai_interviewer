"""
Admin Domain Layer

Pure business logic for admin operations. No database calls, no HTTP concerns.

Public API:
- Services: TemplateService, RubricService, WindowService, RoleService,
            TopicService, QuestionService, CodingProblemService
- Entities: Template, Rubric, RubricDimension, Role, Topic, CodingTopic,
            Question, CodingProblem, Window, WindowRoleTemplate
- Protocols: Repository interfaces for dependency injection

Dependencies:
- app.shared.errors — Exception types
- app.shared.auth_context — IdentityContext, AdminRole
- app.shared.observability — Logging
"""

from .entities import (
    Template,
    Rubric,
    RubricDimension,
    Role,
    Topic,
    CodingTopic,
    Question,
    CodingProblem,
    Window,
    WindowRoleTemplate,
    TemplateRubric,
    TemplateRole,
    OverrideRecord,
    ContentType,
)

from .services import (
    TemplateService,
    RubricService,
    WindowService,
    RoleService,
    TopicService,
    QuestionService,
    CodingProblemService,
)

from .protocols import (
    TemplateRepository,
    RubricRepository,
    WindowRepository,
    RoleRepository,
    TopicRepository,
    QuestionRepository,
    CodingProblemRepository,
    SubmissionRepository,
    AuditLogRepository,
)

from .authorization import authorize_admin_operation

__all__ = [
    # Entities
    "Template",
    "Rubric",
    "RubricDimension",
    "Role",
    "Topic",
    "CodingTopic",
    "Question",
    "CodingProblem",
    "Window",
    "WindowRoleTemplate",
    "TemplateRubric",
    "TemplateRole",
    "OverrideRecord",
    "ContentType",
    # Services
    "TemplateService",
    "RubricService",
    "WindowService",
    "RoleService",
    "TopicService",
    "QuestionService",
    "CodingProblemService",
    # Protocols
    "TemplateRepository",
    "RubricRepository",
    "WindowRepository",
    "RoleRepository",
    "TopicRepository",
    "QuestionRepository",
    "CodingProblemRepository",
    "SubmissionRepository",
    "AuditLogRepository",
    # Authorization
    "authorize_admin_operation",
]
