"""
Question Persistence ORM Models — Supplementary tables

Provides ORM models for tables that the question persistence layer
needs to *read* but which are not already modelled elsewhere.

The admin module's ``models.py`` owns the primary ``questions``,
``topics``, and ``coding_problems`` models.  This file adds:

- ``QuestionTopicModel``  — ``question_topics`` junction table
- ``CodingTestCaseModel``  — ``coding_test_cases`` table
- ``CodingProblemTopicModel`` — ``coding_problem_topics`` junction table

Conventions (matching admin/persistence/models.py):
- Uses shared ``Base`` from ``app.persistence.postgres.base``
- ``BigInteger`` primary keys where applicable
- Read-only usage — repositories never INSERT/UPDATE/DELETE these rows

References:
- docs/schema.sql: question_topics, coding_test_cases, coding_problem_topics
- persistence/REQUIREMENTS.md §4 (Topic hierarchy), §5 (Coding problems)
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    text,
)

from app.persistence.postgres.base import Base


class QuestionTopicModel(Base):
    """
    ORM model for the ``question_topics`` junction table.

    Maps questions → topics (many-to-many).
    Composite primary key: (question_id, topic_id).
    """

    __tablename__ = "question_topics"

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id = Column(
        BigInteger,
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )


class CodingTestCaseModel(Base):
    """
    ORM model for the ``coding_test_cases`` table.

    Contains test inputs and expected outputs for coding problems.
    ``is_hidden`` flag controls whether expected_output is exposed to candidates.
    """

    __tablename__ = "coding_test_cases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    coding_problem_id = Column(
        BigInteger,
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_hidden = Column(Boolean, nullable=False, server_default=text("true"))
    weight = Column(Numeric, nullable=False, server_default=text("1.0"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class CodingProblemTopicModel(Base):
    """
    ORM model for the ``coding_problem_topics`` junction table.

    Maps coding_problems → coding_topics (many-to-many).
    Composite primary key: (coding_problem_id, coding_topic_id).
    """

    __tablename__ = "coding_problem_topics"

    coding_problem_id = Column(
        BigInteger,
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        primary_key=True,
    )
    coding_topic_id = Column(
        BigInteger,
        ForeignKey("coding_topics.id", ondelete="CASCADE"),
        primary_key=True,
    )
