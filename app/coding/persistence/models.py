"""
Coding ORM Models — SQLAlchemy models for code submission tables

Maps directly to PostgreSQL tables defined in ``docs/schema.sql``
and the ``main-coding-execution-schema.sql`` migration.

Conventions (matching admin/persistence/models.py):
- Uses shared ``Base`` from ``app.persistence.postgres.base``
- ``BigInteger`` primary keys (matching DB sequences)
- ``DateTime(timezone=True)`` with ``server_default=text('now()')``
- All models are data-access-only — NO business logic

References:
- persistence/REQUIREMENTS.md §4 (ORM Models)
- schema.sql: code_submissions, code_execution_results tables
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.persistence.postgres.base import Base


class CodeSubmissionModel(Base):
    """ORM model for the ``code_submissions`` table."""

    __tablename__ = "code_submissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_exchange_id = Column(
        BigInteger,
        ForeignKey("interview_exchanges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    coding_problem_id = Column(
        BigInteger,
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    language = Column(Text, nullable=False)
    source_code = Column(Text, nullable=False)
    execution_status = Column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    score = Column(Numeric, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    memory_kb = Column(Integer, nullable=True)
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    execution_results = relationship(
        "CodeExecutionResultModel",
        back_populates="code_submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CodeExecutionResultModel(Base):
    """ORM model for the ``code_execution_results`` table."""

    __tablename__ = "code_execution_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code_submission_id = Column(
        BigInteger,
        ForeignKey("code_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_case_id = Column(
        BigInteger,
        ForeignKey("coding_test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    passed = Column(Boolean, nullable=False)
    actual_output = Column(Text, nullable=True)
    runtime_ms = Column(Integer, nullable=True)
    memory_kb = Column(Integer, nullable=True)
    exit_code = Column(Integer, nullable=True)
    compiler_output = Column(Text, nullable=True)
    runtime_output = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    code_submission = relationship(
        "CodeSubmissionModel",
        back_populates="execution_results",
    )

    __table_args__ = (
        UniqueConstraint(
            "code_submission_id",
            "test_case_id",
            name="uq_submission_test_case",
        ),
    )
