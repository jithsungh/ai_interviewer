"""
Audio Persistence ORM Models — SQLAlchemy model for audio_analytics

Maps directly to the ``audio_analytics`` PostgreSQL table.

Conventions (matching ``app/coding/persistence/models.py``):
- Uses shared ``Base`` from ``app.persistence.postgres.base``
- ``BigInteger`` primary keys
- ``DateTime(timezone=True)`` with ``server_default=text('now()')``
- Data-access-only — NO business logic

References:
- audio/persistence/REQUIREMENTS.md §4 (ORM Model)
- docs/schema.sql: audio_analytics table
- DEV-49_audio-persistence-schema-additions.sql migration
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.persistence.postgres.base import Base


class AudioAnalyticsModel(Base):
    """ORM model for the ``audio_analytics`` table."""

    __tablename__ = "audio_analytics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_exchange_id = Column(
        BigInteger,
        ForeignKey("interview_exchanges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Transcript data
    transcript = Column(Text, nullable=True)
    transcript_finalized = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    confidence_score = Column(Numeric, nullable=True)
    language_detected = Column(String(10), nullable=True)

    # Speech characteristics
    speech_state = Column(
        String(20),
        nullable=False,
        server_default=text("'complete'"),
    )
    speech_rate_wpm = Column(Integer, nullable=True)
    pause_duration_ms = Column(Integer, nullable=True)
    long_pause_count = Column(Integer, nullable=False, server_default=text("0"))

    # Behavioral signals
    filler_word_count = Column(Integer, nullable=True)
    filler_rate = Column(Numeric, nullable=False, server_default=text("0.0"))
    sentiment_score = Column(Numeric, nullable=True)
    hesitation_detected = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    frustration_detected = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # Audio quality
    audio_quality_score = Column(Numeric, nullable=True)
    background_noise_detected = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    # Metadata (JSONB for extensible analytics data)
    analysis_metadata = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        server_default=text("now()"),
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "speech_state IN ('complete', 'incomplete', 'continuing')",
            name="audio_analytics_speech_state_check",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="audio_analytics_confidence_range",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR "
            "(sentiment_score >= -1.0 AND sentiment_score <= 1.0)",
            name="audio_analytics_sentiment_range",
        ),
        {"extend_existing": True},
    )
