"""
Prompt Template ORM Model

SQLAlchemy ORM model for the prompt_templates table.
Maps directly to PostgreSQL table defined in docs/schema.sql.

Convention (consistent with app.admin.persistence.models):
  - Uses shared Base from app.persistence.postgres.base
  - BigInteger primary keys (matching DB sequences)
  - TIMESTAMP(timezone=True) with server_default=text('now()')
  - JSONB for flexible structures
  - Data-access-only — NO business logic
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.persistence.postgres.base import Base


class PromptTemplateModel(Base):
    """
    Maps to: public.prompt_templates

    Columns mirror schema.sql exactly:
    - id: bigint PK (auto-increment via sequence)
    - name: text NOT NULL
    - prompt_type: text NOT NULL (e.g. 'question_generation', 'evaluation')
    - scope: template_scope ENUM ('public', 'organization', 'private')
    - organization_id: bigint FK → organizations (NULL = global)
    - system_prompt: text NOT NULL
    - user_prompt: text NOT NULL
    - model_id: bigint FK → models (ON DELETE SET NULL)
    - model_config: jsonb NOT NULL
    - version: integer NOT NULL DEFAULT 1
    - is_active: boolean DEFAULT true NOT NULL
    - created_at / updated_at: timestamps with timezone
    """

    __tablename__ = "prompt_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    prompt_type = Column(Text, nullable=False)
    scope = Column(String(20), nullable=False)  # template_scope enum
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    model_id = Column(
        BigInteger,
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    version = Column(Integer, nullable=False, server_default=text("1"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "name", "version", "organization_id",
            name="prompt_templates_name_version_organization_id_key",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PromptTemplateModel id={self.id} "
            f"name={self.name!r} type={self.prompt_type!r} "
            f"v{self.version} active={self.is_active}>"
        )
