"""
SQLAlchemy ORM Model for generic_fallback_questions table.

Inherits from the shared declarative Base in app.persistence.postgres.base.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence.postgres.base import Base


class GenericFallbackQuestion(Base):
    """
    ORM mapping for public.generic_fallback_questions.

    Stores pre-seeded generic questions used as last-resort fallback
    when LLM generation fails after max retries.
    """

    __tablename__ = "generic_fallback_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_type = Column(String(50), nullable=False, index=True)
    difficulty = Column(String(20), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    estimated_time_seconds = Column(Integer, nullable=False, default=120)
    is_active = Column(Boolean, nullable=False, default=True)
    usage_count = Column(Integer, nullable=False, default=0)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<GenericFallbackQuestion id={self.id} "
            f"difficulty={self.difficulty} topic={self.topic}>"
        )
