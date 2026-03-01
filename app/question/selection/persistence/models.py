"""
SQLAlchemy ORM Model for difficulty_adaptation_log table.

Maps to the table created by migration DEV-38_difficulty-adaptation-log.sql.
INSERT-ONLY audit table — no UPDATE/DELETE methods.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)

from app.persistence.postgres.base import Base


class DifficultyAdaptationLogModel(Base):
    """
    ORM mapping for public.difficulty_adaptation_log.

    Immutable audit log for difficulty adaptation decisions (FR-4.4).
    INSERT-ONLY — no updates or deletes.
    """

    __tablename__ = "difficulty_adaptation_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    submission_id = Column(BigInteger, nullable=False, index=True)
    exchange_sequence_order = Column(Integer, nullable=False)

    # Previous state
    previous_difficulty = Column(String(20), nullable=True)
    previous_score = Column(Numeric(5, 2), nullable=True)
    previous_question_id = Column(BigInteger, nullable=True)

    # Adaptation logic
    adaptation_rule = Column(String(50), nullable=False)
    threshold_up = Column(Numeric(5, 2), nullable=True)
    threshold_down = Column(Numeric(5, 2), nullable=True)
    max_difficulty_jump = Column(Integer, nullable=False, default=1)

    # Output
    next_difficulty = Column(String(20), nullable=False)
    adaptation_reason = Column(Text, nullable=False)
    difficulty_changed = Column(Boolean, nullable=False, default=False)

    # Audit
    decided_at = Column(DateTime(timezone=True), nullable=False)
    rule_version = Column(String(20), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<DifficultyAdaptationLog id={self.id} "
            f"submission_id={self.submission_id} "
            f"next_difficulty={self.next_difficulty}>"
        )
