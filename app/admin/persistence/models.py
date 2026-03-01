"""
Admin ORM Models

SQLAlchemy ORM models for all admin-owned tables.
Maps directly to PostgreSQL tables defined in docs/schema.sql
and DEV-25_admin_override_tables.sql migration.

Convention:
  • Uses shared Base from app.persistence.postgres.base
  • BigInteger primary keys (matching DB sequences)
  • TIMESTAMP(timezone=True) with server_default=text('now()')
  • JSONB for flexible structures
  • All models are data-access-only — NO business logic
"""

from __future__ import annotations

from datetime import datetime, timezone

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


# ═══════════════════════════════════════════════════════════════════════════
# interview_templates
# ═══════════════════════════════════════════════════════════════════════════

class InterviewTemplateModel(Base):
    """Maps to: public.interview_templates"""

    __tablename__ = "interview_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(20), nullable=False)  # template_scope enum
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    template_structure = Column(JSONB, nullable=False)
    rules = Column(JSONB, nullable=True)
    total_estimated_time_minutes = Column(Integer, nullable=True)
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
            name="interview_templates_name_version_organization_id_key",
        ),
    )

    # Relationships
    template_roles = relationship(
        "InterviewTemplateRoleModel",
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    template_rubrics = relationship(
        "InterviewTemplateRubricModel",
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# interview_template_roles  (composite PK — no id column)
# ═══════════════════════════════════════════════════════════════════════════

class InterviewTemplateRoleModel(Base):
    """Maps to: public.interview_template_roles"""

    __tablename__ = "interview_template_roles"

    interview_template_id = Column(
        BigInteger,
        ForeignKey("interview_templates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )

    template = relationship("InterviewTemplateModel", back_populates="template_roles")
    role = relationship("RoleModel")


# ═══════════════════════════════════════════════════════════════════════════
# interview_template_rubrics
# ═══════════════════════════════════════════════════════════════════════════

class InterviewTemplateRubricModel(Base):
    """Maps to: public.interview_template_rubrics"""

    __tablename__ = "interview_template_rubrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    interview_template_id = Column(
        BigInteger,
        ForeignKey("interview_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    rubric_id = Column(
        BigInteger,
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_name = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "interview_template_id", "rubric_id", "section_name",
            name="interview_template_rubrics_interview_template_id_rubric_id__key",
        ),
    )

    template = relationship("InterviewTemplateModel", back_populates="template_rubrics")
    rubric = relationship("RubricModel")


# ═══════════════════════════════════════════════════════════════════════════
# rubrics
# ═══════════════════════════════════════════════════════════════════════════

class RubricModel(Base):
    """Maps to: public.rubrics"""

    __tablename__ = "rubrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(20), nullable=False)
    schema = Column("schema", JSONB, nullable=True)
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
        UniqueConstraint("name", "organization_id", name="rubrics_name_organization_id_key"),
    )

    dimensions = relationship(
        "RubricDimensionModel",
        back_populates="rubric",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RubricDimensionModel.sequence_order",
    )


# ═══════════════════════════════════════════════════════════════════════════
# rubric_dimensions
# ═══════════════════════════════════════════════════════════════════════════

class RubricDimensionModel(Base):
    """Maps to: public.rubric_dimensions"""

    __tablename__ = "rubric_dimensions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rubric_id = Column(
        BigInteger,
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    max_score = Column(Numeric, nullable=False)
    weight = Column(Numeric, nullable=False, server_default=text("1.0"))
    criteria = Column(JSONB, nullable=True)
    sequence_order = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    rubric = relationship("RubricModel", back_populates="dimensions")


# ═══════════════════════════════════════════════════════════════════════════
# roles
# ═══════════════════════════════════════════════════════════════════════════

class RoleModel(Base):
    """Maps to: public.roles"""

    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(20), nullable=False)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
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
        UniqueConstraint("name", "organization_id", name="roles_name_organization_id_key"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# topics
# ═══════════════════════════════════════════════════════════════════════════

class TopicModel(Base):
    """Maps to: public.topics"""

    __tablename__ = "topics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    parent_topic_id = Column(
        BigInteger,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope = Column(String(20), nullable=False)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    estimated_time_minutes = Column(Integer, nullable=True)
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
        UniqueConstraint("name", "organization_id", name="topics_name_organization_id_key"),
    )

    parent = relationship("TopicModel", remote_side="TopicModel.id", lazy="select")


# ═══════════════════════════════════════════════════════════════════════════
# coding_topics
# ═══════════════════════════════════════════════════════════════════════════

class CodingTopicModel(Base):
    """Maps to: public.coding_topics"""

    __tablename__ = "coding_topics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    topic_type = Column(String(30), nullable=False)  # coding_topic_type enum
    parent_topic_id = Column(
        BigInteger,
        ForeignKey("coding_topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope = Column(String(20), nullable=False)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    display_order = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    parent = relationship("CodingTopicModel", remote_side="CodingTopicModel.id", lazy="select")


# ═══════════════════════════════════════════════════════════════════════════
# questions
# ═══════════════════════════════════════════════════════════════════════════

class QuestionModel(Base):
    """Maps to: public.questions"""

    __tablename__ = "questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    question_type = Column(String(20), nullable=False)  # question_type enum
    difficulty = Column(String(20), nullable=False)  # difficulty_level enum
    scope = Column(String(20), nullable=False)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_type = Column(Text, nullable=True)
    estimated_time_minutes = Column(Integer, nullable=False, server_default=text("5"))
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


# ═══════════════════════════════════════════════════════════════════════════
# coding_problems
# ═══════════════════════════════════════════════════════════════════════════

class CodingProblemModel(Base):
    """Maps to: public.coding_problems"""

    __tablename__ = "coding_problems"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    body = Column(Text, nullable=False)
    difficulty = Column(String(20), nullable=False)
    scope = Column(String(20), nullable=False)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    constraints = Column(Text, nullable=True)
    estimated_time_minutes = Column(Integer, nullable=False, server_default=text("30"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    source_name = Column(String(50), nullable=False)
    source_id = Column(Text, nullable=False)
    source_slug = Column(Text, nullable=True)
    title = Column(Text, nullable=False, server_default=text("''"))
    description = Column(Text, nullable=True)
    raw_content = Column(JSONB, nullable=True)
    content_overridden = Column(Boolean, nullable=False, server_default=text("false"))
    overridden_content = Column(Text, nullable=True)
    examples = Column(JSONB, server_default=text("'[]'::jsonb"))
    constraints_structured = Column(JSONB, server_default=text("'[]'::jsonb"))
    hints = Column(JSONB, server_default=text("'[]'::jsonb"))
    stats = Column(JSONB, nullable=True)
    code_snippets = Column(JSONB, server_default=text("'{}'::jsonb"))
    likes = Column(Integer, nullable=True)
    dislikes = Column(Integer, nullable=True)
    acceptance_rate = Column(Numeric(5, 2), nullable=True)
    pipeline_status = Column(
        String(30), nullable=False, server_default=text("'pending'")
    )
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
        UniqueConstraint("source_name", "source_id", name="uq_source_problem"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# interview_submission_windows
# ═══════════════════════════════════════════════════════════════════════════

class InterviewSubmissionWindowModel(Base):
    """Maps to: public.interview_submission_windows"""

    __tablename__ = "interview_submission_windows"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_id = Column(
        BigInteger,
        ForeignKey("admins.id"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    scope = Column(String(20), nullable=False)  # interview_scope enum
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(Text, nullable=False)
    max_allowed_submissions = Column(Integer, nullable=True)
    allow_after_end_time = Column(Boolean, nullable=False, server_default=text("false"))
    allow_resubmission = Column(Boolean, nullable=False, server_default=text("false"))
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
        CheckConstraint("end_time > start_time", name="interview_submission_windows_check"),
    )

    mappings = relationship(
        "WindowRoleTemplateModel",
        back_populates="window",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# window_role_templates
# ═══════════════════════════════════════════════════════════════════════════

class WindowRoleTemplateModel(Base):
    """Maps to: public.window_role_templates"""

    __tablename__ = "window_role_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    window_id = Column(
        BigInteger,
        ForeignKey("interview_submission_windows.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = Column(
        BigInteger,
        ForeignKey("interview_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    selection_weight = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "window_id", "role_id", "template_id",
            name="window_role_templates_window_id_role_id_template_id_key",
        ),
    )

    window = relationship("InterviewSubmissionWindowModel", back_populates="mappings")
    role = relationship("RoleModel")
    template = relationship("InterviewTemplateModel")


# ═══════════════════════════════════════════════════════════════════════════
# interview_submissions  (canonical model lives in session module)
# ═══════════════════════════════════════════════════════════════════════════
# Re-exported so admin code can keep importing from this file.
from app.interview.session.persistence.models import InterviewSubmissionModel  # noqa: F401


# ═══════════════════════════════════════════════════════════════════════════
# audit_logs
# ═══════════════════════════════════════════════════════════════════════════

class AuditLogModel(Base):
    """Maps to: public.audit_logs (insert-only for admin module)."""

    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(BigInteger, nullable=True)
    actor_user_id = Column(BigInteger, nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(BigInteger, nullable=True)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


# ═══════════════════════════════════════════════════════════════════════════
# Override Tables (created by DEV-25 migration)
# All 6 override tables share identical structure.
# ═══════════════════════════════════════════════════════════════════════════

class TemplateOverrideModel(Base):
    """Maps to: public.template_overrides"""

    __tablename__ = "template_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("interview_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="template_overrides_org_base_uq",
        ),
    )


class RubricOverrideModel(Base):
    """Maps to: public.rubric_overrides"""

    __tablename__ = "rubric_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="rubric_overrides_org_base_uq",
        ),
    )


class RoleOverrideModel(Base):
    """Maps to: public.role_overrides"""

    __tablename__ = "role_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="role_overrides_org_base_uq",
        ),
    )


class TopicOverrideModel(Base):
    """Maps to: public.topic_overrides"""

    __tablename__ = "topic_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="topic_overrides_org_base_uq",
        ),
    )


class QuestionOverrideModel(Base):
    """Maps to: public.question_overrides"""

    __tablename__ = "question_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="question_overrides_org_base_uq",
        ),
    )


class CodingProblemOverrideModel(Base):
    """Maps to: public.coding_problem_overrides"""

    __tablename__ = "coding_problem_overrides"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_content_id = Column(
        BigInteger,
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_fields = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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
            "organization_id", "base_content_id",
            name="coding_problem_overrides_org_base_uq",
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# OVERRIDE_MODEL_MAP — Used by the generic OverrideRepository
# ═══════════════════════════════════════════════════════════════════════════

OVERRIDE_MODEL_MAP = {
    "template": TemplateOverrideModel,
    "rubric": RubricOverrideModel,
    "role": RoleOverrideModel,
    "topic": TopicOverrideModel,
    "question": QuestionOverrideModel,
    "coding_problem": CodingProblemOverrideModel,
}
