"""
Question Persistence Entities — Domain data classes

Plain dataclasses representing rows from ``questions``, ``topics``,
``coding_problems``, and ``coding_test_cases`` tables.

Returned by repository methods and consumed by the selection / generation layers.
Contains ZERO business logic and ZERO ORM dependencies.

References:
- persistence/REQUIREMENTS.md §3–5 (Repository interfaces)
- docs/schema.sql (table definitions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class QuestionEntity:
    """
    Read-only domain entity for a question row.

    Maps 1:1 to the ``questions`` table.
    Frozen because the persistence layer is read-only.
    """

    id: int
    question_text: str
    answer_text: Optional[str]
    question_type: str  # behavioral | technical | situational | coding
    difficulty: str  # easy | medium | hard
    scope: str  # public | organization | private
    organization_id: Optional[int]
    source_type: Optional[str]
    estimated_time_minutes: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    topic_ids: List[int] = field(default_factory=list)


@dataclass(frozen=True)
class TopicEntity:
    """
    Read-only domain entity for a topic row.

    Maps 1:1 to the ``topics`` table.
    """

    id: int
    name: str
    description: Optional[str]
    parent_topic_id: Optional[int]
    scope: str
    organization_id: Optional[int]
    estimated_time_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class CodingTestCaseEntity:
    """
    Read-only domain entity for a coding test case.

    Maps 1:1 to the ``coding_test_cases`` table.
    ``expected_output`` may be None for hidden test cases (security measure).
    """

    id: int
    coding_problem_id: int
    input_data: str
    expected_output: Optional[str]  # None when is_hidden=True and not include_hidden
    is_hidden: bool
    weight: float


@dataclass(frozen=True)
class CodingProblemEntity:
    """
    Read-only domain entity for a coding problem.

    Maps 1:1 to the ``coding_problems`` table.
    ``test_cases`` are eagerly loaded with hidden-output filtering.
    """

    id: int
    title: str
    body: str
    difficulty: str
    scope: str
    organization_id: Optional[int]
    description: Optional[str]
    constraints: Optional[str]
    estimated_time_minutes: int
    is_active: bool
    source_name: str
    source_id: str
    source_slug: Optional[str] = None
    raw_content: Optional[Dict[str, Any]] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    constraints_structured: List[Dict[str, Any]] = field(default_factory=list)
    hints: List[Dict[str, Any]] = field(default_factory=list)
    stats: Optional[Dict[str, Any]] = None
    code_snippets: Optional[Dict[str, Any]] = field(default_factory=dict)
    test_cases: List[CodingTestCaseEntity] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
