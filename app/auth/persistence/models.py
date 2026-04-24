"""
Auth ORM Models

SQLAlchemy ORM models for auth module tables.
These map directly to database tables.
"""

from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime, Integer, Boolean,
    ForeignKey, CheckConstraint, TIMESTAMP, text
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from pydantic import ConfigDict

from app.persistence.postgres.base import Base


class User(Base):
    """
    User table - base identity for all users (admins and candidates).
    
    Maps to: public.users
    """
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    user_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='active')
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    token_version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        CheckConstraint(
            "user_type IN ('admin', 'candidate')",
            name='users_user_type_check'
        ),
    )
    
    # Relationships
    admins = relationship("Admin", back_populates="user", cascade="all, delete-orphan")
    candidates = relationship("Candidate", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuthAuditLog", back_populates="user")


class Organization(Base):
    """
    Organization table — minimal model so SQLAlchemy can resolve
    the ForeignKey('organizations.id') declared on Admin.

    Maps to: public.organizations
    """
    __tablename__ = 'organizations'

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    organization_type = Column(String(20), nullable=False)
    plan = Column(String(20), nullable=False, default='free')
    domain = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default='active')
    policy_config = Column(JSONB, nullable=True)
    metadata_ = Column('metadata', JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc)
    )

    # Relationships
    admins = relationship("Admin", back_populates="organization")


class Admin(Base):
    """
    Admin table - extended data for admin users.
    
    Maps to: public.admins
    """
    __tablename__ = 'admins'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    organization_id = Column(BigInteger, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(50), nullable=False)  # admin_role enum
    status = Column(String(20), nullable=False, default='active')  # admin_status enum
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc)
    )
    
    # Relationships
    user = relationship("User", back_populates="admins")
    organization = relationship("Organization", back_populates="admins")


class Candidate(Base):
    """
    Candidate table - extended data for candidate users.
    
    Maps to: public.candidates
    """
    __tablename__ = 'candidates'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    plan = Column(String(20), nullable=False, default='free')  # candidate_plan enum
    status = Column(String(20), nullable=False, default='active')  # user_status enum
    profile_metadata = Column(JSONB, nullable=True)  # {full_name, phone, etc.}
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc)
    )
    
    # Relationships
    user = relationship("User", back_populates="candidates")
    settings = relationship(
        "CandidateSettings",
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
    )
    career_insight_runs = relationship(
        "CandidateCareerInsightRun",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    career_roadmaps = relationship(
        "CandidateCareerRoadmap",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    practice_deck_runs = relationship(
        "CandidatePracticeDeckRun",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    resumes = relationship(
        "ResumeModel",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class CandidateSettings(Base):
    """
    Candidate settings table - persistent notification/privacy/UI preferences.

    Maps to: public.candidate_settings
    """
    __tablename__ = 'candidate_settings'

    candidate_id = Column(
        BigInteger,
        ForeignKey('candidates.id', ondelete='CASCADE'),
        primary_key=True,
    )
    notification_preferences = Column(JSONB, nullable=False, default=dict)
    privacy_preferences = Column(JSONB, nullable=False, default=dict)
    ui_preferences = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc),
    )

    candidate = relationship("Candidate", back_populates="settings")


class CandidateCareerInsightRun(Base):
    """
    Persisted market insight generations for candidate career path planning.

    Maps to: public.candidate_career_insight_runs
    """

    __tablename__ = 'candidate_career_insight_runs'
    model_config = ConfigDict(protected_namespaces=())

    id = Column(BigInteger, primary_key=True)
    candidate_id = Column(
        BigInteger,
        ForeignKey('candidates.id', ondelete='CASCADE'),
        nullable=False,
    )
    industry = Column(Text, nullable=False)
    seniority = Column(String(30), nullable=False)
    insights = Column(JSONB, nullable=False, default=list)
    generation_source = Column(String(20), nullable=False, default='fallback')
    model_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc),
    )

    candidate = relationship("Candidate", back_populates="career_insight_runs")


class CandidateCareerRoadmap(Base):
    """
    Persisted career roadmaps generated for a candidate.

    Maps to: public.candidate_career_roadmaps
    """

    __tablename__ = 'candidate_career_roadmaps'
    model_config = ConfigDict(protected_namespaces=())

    id = Column(BigInteger, primary_key=True)
    candidate_id = Column(
        BigInteger,
        ForeignKey('candidates.id', ondelete='CASCADE'),
        nullable=False,
    )
    insight_run_id = Column(
        BigInteger,
        ForeignKey('candidate_career_insight_runs.id', ondelete='SET NULL'),
        nullable=True,
    )
    industry = Column(Text, nullable=False)
    target_role = Column(Text, nullable=False)
    selected_insight = Column(JSONB, nullable=True)
    steps = Column(JSONB, nullable=False, default=list)
    completed_levels = Column(JSONB, nullable=False, default=list)
    current_level = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    generation_source = Column(String(20), nullable=False, default='fallback')
    model_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc),
    )

    candidate = relationship("Candidate", back_populates="career_roadmaps")


class CandidatePracticeDeckRun(Base):
    """
    Persisted interview prep flashcard decks generated for a candidate.

    Maps to: public.candidate_practice_deck_runs
    """

    __tablename__ = 'candidate_practice_deck_runs'
    model_config = ConfigDict(protected_namespaces=())

    id = Column(BigInteger, primary_key=True)
    candidate_id = Column(
        BigInteger,
        ForeignKey('candidates.id', ondelete='CASCADE'),
        nullable=False,
    )
    role = Column(Text, nullable=False)
    industry = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=True)
    difficulty = Column(String(20), nullable=True)
    source_question_ids = Column(JSONB, nullable=False, default=list)
    flashcards = Column(JSONB, nullable=False, default=list)
    bookmarked_indices = Column(JSONB, nullable=False, default=list)
    mastered_indices = Column(JSONB, nullable=False, default=list)
    current_card_index = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    generation_source = Column(String(20), nullable=False, default='db')
    model_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc),
    )

    candidate = relationship("Candidate", back_populates="practice_deck_runs")


class RefreshToken(Base):
    """
    Refresh tokens table - stores hashed refresh tokens.
    
    Maps to: public.refresh_tokens
    """
    __tablename__ = 'refresh_tokens'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    device_info = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    issued_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    revoked_reason = Column(String(100), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class AuthAuditLog(Base):
    """
    Auth audit log table - immutable audit trail.
    
    Maps to: public.auth_audit_log
    INSERT-ONLY table (no updates or deletes).
    """
    __tablename__ = 'auth_audit_log'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    event_type = Column(String(50), nullable=False)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    # Column named 'metadata' in DB, mapped as 'event_metadata' to avoid
    # shadowing Python built-in; uses explicit column name mapping.
    event_metadata = Column('metadata', JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class ResumeModel(Base):
    """
    Resume table - stores candidate resumes with parsing and analysis results.

    Maps to: public.resumes
    """
    __tablename__ = 'resumes'

    id = Column(BigInteger, primary_key=True)
    candidate_id = Column(
        BigInteger,
        ForeignKey('candidates.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    file_url = Column(Text, nullable=True)
    file_name = Column(Text, nullable=True)
    
    # Raw parsing results
    parsed_text = Column(Text, nullable=True)
    extracted_data = Column(JSONB, nullable=True)
    
    # Comprehensive structured JSON from LLM analysis
    structured_json = Column(JSONB, nullable=True)
    
    # LLM analysis results
    llm_feedback = Column(JSONB, nullable=True)  # {strengths, weaknesses, suggestions, overall_assessment}
    ats_score = Column(Integer, nullable=True)  # 0-100
    ats_feedback = Column(Text, nullable=True)
    
    # Embeddings for vector search
    embeddings = Column(JSONB, nullable=True)  # {full_resume: [float], sections: {education: [float], ...}}
    
    # Processing status
    parse_status = Column(String(20), nullable=False, default='pending')  # pending, success, failed
    llm_analysis_status = Column(String(20), nullable=False, default='pending')  # pending, success, failed
    embeddings_status = Column(String(20), nullable=False, default='pending')  # pending, success, failed
    
    parse_error = Column(Text, nullable=True)
    llm_error = Column(Text, nullable=True)
    embeddings_error = Column(Text, nullable=True)
    
    # Metadata
    uploaded_at = Column(TIMESTAMP(timezone=True), nullable=True)
    analyzed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()'),
        onupdate=datetime.now(timezone.utc)
    )

    # Relationships
    candidate = relationship("Candidate", back_populates="resumes")
