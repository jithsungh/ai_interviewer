"""
Auth ORM Models

SQLAlchemy ORM models for auth module tables.
These map directly to database tables.
"""

from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime, Integer,
    ForeignKey, CheckConstraint, TIMESTAMP, text
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()


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
    event_metadata = Column(JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text('now()')
    )
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
