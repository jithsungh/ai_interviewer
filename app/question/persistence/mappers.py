"""
Question Persistence Mappers — ORM → entity conversion (read-only)

Keeps the question selection / generation layers free of SQLAlchemy dependencies.
Only ORM → entity direction is needed (persistence is read-only; admin handles writes).

Follows the pattern established by:
- app.coding.persistence.mappers
- app.ai.prompts.mappers

References:
- persistence/REQUIREMENTS.md §5.3 (test case output filtering)
"""

from __future__ import annotations

from typing import List, Optional

from app.admin.persistence.models import (
    CodingProblemModel,
    QuestionModel,
    TopicModel,
)
from app.question.persistence.entities import (
    CodingProblemEntity,
    CodingTestCaseEntity,
    QuestionEntity,
    TopicEntity,
)
from app.question.persistence.models import CodingTestCaseModel


def question_model_to_entity(
    m: QuestionModel,
    topic_ids: Optional[List[int]] = None,
) -> QuestionEntity:
    """
    Convert ORM ``QuestionModel`` → frozen ``QuestionEntity``.

    Args:
        m: SQLAlchemy QuestionModel row.
        topic_ids: Pre-loaded topic IDs from the ``question_topics`` junction table.
                   If None, defaults to empty list.
    """
    return QuestionEntity(
        id=m.id,
        question_text=m.question_text,
        answer_text=m.answer_text,
        question_type=m.question_type,
        difficulty=m.difficulty,
        scope=m.scope,
        organization_id=m.organization_id,
        source_type=m.source_type,
        estimated_time_minutes=m.estimated_time_minutes,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
        topic_ids=topic_ids or [],
    )


def topic_model_to_entity(m: TopicModel) -> TopicEntity:
    """Convert ORM ``TopicModel`` → frozen ``TopicEntity``."""
    return TopicEntity(
        id=m.id,
        name=m.name,
        description=m.description,
        parent_topic_id=m.parent_topic_id,
        scope=m.scope,
        organization_id=m.organization_id,
        estimated_time_minutes=m.estimated_time_minutes,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def coding_test_case_model_to_entity(
    m: CodingTestCaseModel,
    *,
    include_hidden_output: bool = False,
) -> CodingTestCaseEntity:
    """
    Convert ORM ``CodingTestCaseModel`` → ``CodingTestCaseEntity``.

    If ``include_hidden_output`` is False (default) and the test case
    is hidden, the ``expected_output`` field is set to None.
    This prevents candidate-facing code from leaking hidden answers.
    """
    expected_output: Optional[str] = m.expected_output
    if m.is_hidden and not include_hidden_output:
        expected_output = None

    return CodingTestCaseEntity(
        id=m.id,
        coding_problem_id=m.coding_problem_id,
        input_data=m.input_data,
        expected_output=expected_output,
        is_hidden=m.is_hidden,
        weight=float(m.weight),
    )


def coding_problem_model_to_entity(
    m: CodingProblemModel,
    test_cases: Optional[List[CodingTestCaseModel]] = None,
    *,
    include_hidden_output: bool = False,
) -> CodingProblemEntity:
    """
    Convert ORM ``CodingProblemModel`` → frozen ``CodingProblemEntity``.

    Args:
        m: SQLAlchemy CodingProblemModel row.
        test_cases: Pre-loaded test case models. If None, test_cases list is empty.
        include_hidden_output: If False, hidden test case expected_outputs are masked.
    """
    tc_entities: List[CodingTestCaseEntity] = []
    if test_cases:
        tc_entities = [
            coding_test_case_model_to_entity(
                tc, include_hidden_output=include_hidden_output
            )
            for tc in test_cases
        ]

    return CodingProblemEntity(
        id=m.id,
        title=m.title,
        body=m.body,
        difficulty=m.difficulty,
        scope=m.scope,
        organization_id=m.organization_id,
        description=m.description,
        constraints=m.constraints,
        estimated_time_minutes=m.estimated_time_minutes,
        is_active=m.is_active,
        source_name=m.source_name,
        source_id=m.source_id,
        source_slug=m.source_slug,
        raw_content=m.raw_content,
        examples=m.examples or [],
        constraints_structured=m.constraints_structured or [],
        hints=m.hints or [],
        stats=m.stats,
        code_snippets=m.code_snippets or {},
        test_cases=tc_entities,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
