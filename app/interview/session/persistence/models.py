"""
ORM Models — Interview Submissions & Exchanges

Maps the ``interview_submissions`` and ``interview_exchanges`` tables so the
repository can run typed queries and the model registration in ``base.py``
picks them up automatically.
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
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.persistence.postgres.base import Base


class InterviewSubmissionModel(Base):
    """ORM model for ``interview_submissions``."""

    __tablename__ = "interview_submissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id = Column(BigInteger, ForeignKey("candidates.id"), nullable=False, index=True)
    window_id = Column(BigInteger, ForeignKey("interview_submission_windows.id"), nullable=False)
    role_id = Column(BigInteger, ForeignKey("roles.id"), nullable=False)
    template_id = Column(BigInteger, ForeignKey("interview_templates.id"), nullable=False)
    mode = Column(String(20), nullable=False, server_default=text("'async'"))
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    final_score = Column(Numeric, nullable=True)
    consent_captured = Column(Boolean, nullable=False, server_default=text("false"))
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Orchestration columns (DEV-43)
    current_exchange_sequence = Column(Integer, nullable=False, server_default=text("0"))
    template_structure_snapshot = Column(JSONB, nullable=True)

    # Relationships
    exchanges = relationship(
        "InterviewExchangeModel",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="InterviewExchangeModel.sequence_order",
        lazy="selectin",
    )

    __table_args__ = (
        # Uniqueness enforced via partial index uq_candidate_window_role_non_practice
        # (allows multiple practice submissions per candidate)
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return f"<InterviewSubmission id={self.id} status={self.status!r}>"


class InterviewExchangeModel(Base):
    """ORM model for ``interview_exchanges``."""

    __tablename__ = "interview_exchanges"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_submission_id = Column(
        BigInteger,
        ForeignKey("interview_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_order = Column(Integer, nullable=False)
    question_id = Column(BigInteger, nullable=True)
    coding_problem_id = Column(BigInteger, nullable=True)
    question_text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)
    difficulty_at_time = Column(String(20), nullable=False)
    response_text = Column(Text, nullable=True)
    response_code = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    ai_followup_message = Column(Text, nullable=True)
    content_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Back-reference
    submission = relationship("InterviewSubmissionModel", back_populates="exchanges")

    __table_args__ = (
        CheckConstraint(
            "(question_id IS NOT NULL) OR (coding_problem_id IS NOT NULL)",
            name="ck_exchange_has_question_or_problem",
        ),
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return f"<InterviewExchange id={self.id} seq={self.sequence_order}>"
