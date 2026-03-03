"""
ORM Model — Proctoring Events

Maps the ``proctoring_events`` table. Events are immutable once created.
No UPDATE operations allowed (audit trail integrity).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence.postgres.base import Base


class ProctoringEventModel(Base):
    """ORM model for ``proctoring_events``."""

    __tablename__ = "proctoring_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_submission_id = Column(
        BigInteger,
        ForeignKey("interview_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(Text, nullable=False)
    severity = Column(
        Enum("low", "medium", "high", "critical", name="proctoring_severity", create_type=False),
        nullable=False,
    )
    risk_weight = Column(Numeric, nullable=False, server_default=text("1.0"))
    evidence = Column(JSONB, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = ({"extend_existing": True},)

    def __repr__(self) -> str:
        return (
            f"<ProctoringEvent id={self.id} type={self.event_type!r} "
            f"severity={self.severity!r}>"
        )
