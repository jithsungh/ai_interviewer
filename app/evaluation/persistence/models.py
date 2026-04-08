"""
Evaluation Persistence — ORM Models

Canonical SQLAlchemy ORM models for the evaluation module's database tables.
These map directly to the schema defined in docs/schema.sql plus the
DEV-49 migration additions.

Tables owned:
    - evaluations
    - evaluation_dimension_scores
    - interview_results
    - supplementary_reports

Design decisions:
    - BigInteger primary keys (consistent with rest of repo)
    - DateTime(timezone=True) with server_default=text("now()")
    - ForeignKey with explicit ondelete
    - extend_existing=True to prevent redefinition errors
    - No business logic — pure data mapping
    - JSONB for flexible structured data
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.persistence.postgres.base import Base


class EvaluationModel(Base):
    """
    ORM model for the ``evaluations`` table.

    One evaluation per exchange when ``is_final = true`` (enforced by
    partial unique index ``uq_evaluations_exchange_final``).

    Schema columns (from schema.sql + DEV-49 migration):
        id, interview_exchange_id, rubric_id, model_id, evaluator_type,
        total_score, explanation, is_final, evaluated_at, created_at,
        evaluated_by (DEV-49), scoring_version (DEV-49)
    """

    __tablename__ = "evaluations"
    __table_args__ = ({"extend_existing": True},)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_exchange_id = Column(
        BigInteger,
        ForeignKey("interview_exchanges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rubric_id = Column(
        BigInteger,
        ForeignKey("rubrics.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_id = Column(
        BigInteger,
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluator_type = Column(
        Enum(
            "ai", "human", "hybrid",
            name="evaluator_type",
            create_type=False,
        ),
        nullable=False,
    )
    total_score = Column(Numeric, nullable=True)
    explanation = Column(JSONB, nullable=True)
    is_final = Column(Boolean, default=False, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # DEV-49 migration additions
    evaluated_by = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scoring_version = Column(Text, nullable=True)

    # Relationships
    dimension_scores = relationship(
        "EvaluationDimensionScoreModel",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<EvaluationModel id={self.id} "
            f"exchange={self.interview_exchange_id} "
            f"type={self.evaluator_type} "
            f"final={self.is_final}>"
        )


class EvaluationDimensionScoreModel(Base):
    """
    ORM model for the ``evaluation_dimension_scores`` table.

    Per-dimension score for an evaluation (unique per evaluation×dimension).

    Schema columns (from schema.sql + DEV-49 migration):
        id, evaluation_id, rubric_dimension_id, score, justification,
        created_at, max_score (DEV-49)
    """

    __tablename__ = "evaluation_dimension_scores"
    __table_args__ = ({"extend_existing": True},)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id = Column(
        BigInteger,
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rubric_dimension_id = Column(
        BigInteger,
        ForeignKey("rubric_dimensions.id", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Numeric, nullable=False)
    justification = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # DEV-49 migration addition
    max_score = Column(Numeric, nullable=True)

    # Relationships
    evaluation = relationship(
        "EvaluationModel",
        back_populates="dimension_scores",
    )

    def __repr__(self) -> str:
        return (
            f"<EvaluationDimensionScoreModel id={self.id} "
            f"eval={self.evaluation_id} "
            f"dim={self.rubric_dimension_id} "
            f"score={self.score}>"
        )


class InterviewResultModel(Base):
    """
    ORM model for the ``interview_results`` table.

    Aggregated final result per interview submission. Only one row with
    ``is_current = true`` per submission (enforced by partial unique index
    ``uq_interview_results_submission_current``).

    Schema columns (from schema.sql):
        id, interview_submission_id, final_score, normalized_score,
        result_status, recommendation, scoring_version, rubric_snapshot,
        template_weight_snapshot, section_scores, strengths, weaknesses,
        summary_notes, generated_by, model_id, is_current, computed_at,
        created_at
    """

    __tablename__ = "interview_results"
    __table_args__ = ({"extend_existing": True},)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_submission_id = Column(
        BigInteger,
        ForeignKey("interview_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    final_score = Column(Numeric, nullable=True)
    normalized_score = Column(Numeric, nullable=True)
    result_status = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    scoring_version = Column(Text, nullable=False)
    rubric_snapshot = Column(JSONB, nullable=True)
    template_weight_snapshot = Column(JSONB, nullable=True)
    section_scores = Column(JSONB, nullable=True)
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    summary_notes = Column(Text, nullable=True)
    generated_by = Column(Text, nullable=False)
    model_id = Column(
        BigInteger,
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_current = Column(Boolean, default=True, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewResultModel id={self.id} "
            f"submission={self.interview_submission_id} "
            f"current={self.is_current}>"
        )


class SupplementaryReportModel(Base):
    """
    ORM model for the ``supplementary_reports`` table.

    Additional reports attached to an interview submission
    (technical breakdown, proctoring risk, behavioral analysis, etc.).

    Schema columns (from schema.sql):
        id, interview_submission_id, report_type, content, generated_by,
        model_id, created_at
    """

    __tablename__ = "supplementary_reports"
    __table_args__ = ({"extend_existing": True},)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_submission_id = Column(
        BigInteger,
        ForeignKey("interview_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type = Column(
        Enum(
            "candidate_summary",
            "technical_breakdown",
            "behavioral_analysis",
            "proctoring_risk",
            name="report_type",
            create_type=False,
        ),
        nullable=False,
    )
    content = Column(JSONB, nullable=False)
    generated_by = Column(Text, nullable=False)
    model_id = Column(
        BigInteger,
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SupplementaryReportModel id={self.id} "
            f"submission={self.interview_submission_id} "
            f"type={self.report_type}>"
        )


class AIModel(Base):
    """
    Minimal ORM model for the global ``models`` table to satisfy
    SQLAlchemy's foreign key metadata dependencies during flush.
    """
    __tablename__ = "models"
    __table_args__ = ({"extend_existing": True},)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    model_type = Column(Text, nullable=False)
    version = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
