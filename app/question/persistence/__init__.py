"""
Question Persistence — Read-Only Repositories

Provides read-only data access for questions, topics, and coding problems.
Multi-tenant filtering enforced on every query.

Public API:
- Entities: QuestionEntity, TopicEntity, CodingProblemEntity, CodingTestCaseEntity
- Repositories: QuestionRepository, TopicRepository, CodingProblemRepository
- Mappers: question_model_to_entity, topic_model_to_entity, etc.

Architectural Invariants:
- ALL repositories are READ-ONLY (admin module owns mutations)
- ALL queries enforce multi-tenant filtering (organization_id + scope)
- NO business logic — pure data access
"""

from app.question.persistence.entities import (
    QuestionEntity,
    TopicEntity,
    CodingProblemEntity,
    CodingTestCaseEntity,
)
from app.question.persistence.repositories import (
    QuestionRepository,
    TopicRepository,
    CodingProblemRepository,
)
from app.question.persistence.mappers import (
    question_model_to_entity,
    topic_model_to_entity,
    coding_problem_model_to_entity,
)

__all__ = [
    # Entities
    "QuestionEntity",
    "TopicEntity",
    "CodingProblemEntity",
    "CodingTestCaseEntity",
    # Repositories
    "QuestionRepository",
    "TopicRepository",
    "CodingProblemRepository",
    # Mappers
    "question_model_to_entity",
    "topic_model_to_entity",
    "coding_problem_model_to_entity",
]
