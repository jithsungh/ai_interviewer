"""
Candidate API Contracts

Pydantic request/response schemas for candidate-facing endpoints:
- Window listing (Gap 1)
- Submission history (Gap 2)
- Performance statistics (Gap 3)
- Profile management (Gap 4)
- Practice question listing (Gap 5)
- Practice submission creation (Gap 6)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════════════════
# Shared
# ════════════════════════════════════════════════════════════════════════


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


# ════════════════════════════════════════════════════════════════════════
# Gap 1: Candidate Window Listing
# ════════════════════════════════════════════════════════════════════════


class WindowOrganizationDTO(BaseModel):
    id: int
    name: str


class WindowRoleDTO(BaseModel):
    id: int
    name: str


class CandidateWindowDTO(BaseModel):
    """A single interview window visible to the candidate."""
    id: int
    name: str
    scope: str
    start_time: datetime
    end_time: datetime
    organization: WindowOrganizationDTO
    role: WindowRoleDTO
    duration_minutes: Optional[int] = None
    max_allowed_submissions: Optional[int] = None
    allow_resubmission: bool = False
    candidate_submission_count: int = 0
    status: str  # "open", "closed", "upcoming"


class CandidateWindowListResponse(BaseModel):
    data: List[CandidateWindowDTO]
    pagination: PaginationMeta


# ════════════════════════════════════════════════════════════════════════
# Gap 2: Candidate Submission History
# ════════════════════════════════════════════════════════════════════════


class SubmissionWindowDTO(BaseModel):
    id: int
    name: str


class SubmissionOrganizationDTO(BaseModel):
    id: int
    name: str


class SubmissionRoleDTO(BaseModel):
    id: int
    name: str


class CandidateSubmissionDTO(BaseModel):
    """A single past submission for the candidate."""
    submission_id: int
    window: SubmissionWindowDTO
    organization: SubmissionOrganizationDTO
    role: SubmissionRoleDTO
    status: str
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    final_score: Optional[float] = None
    result_status: Optional[str] = None
    recommendation: Optional[str] = None


class CandidateSubmissionListResponse(BaseModel):
    data: List[CandidateSubmissionDTO]
    pagination: PaginationMeta


# ════════════════════════════════════════════════════════════════════════
# Gap 3: Candidate Performance Statistics
# ════════════════════════════════════════════════════════════════════════


class ScoreHistoryPoint(BaseModel):
    date: str
    score: Optional[float] = None


class SkillBreakdownItem(BaseModel):
    skill: str
    score: Optional[float] = None


class CandidateStatsResponse(BaseModel):
    total_interviews: int = 0
    average_score: Optional[float] = None
    pass_rate: Optional[float] = None
    total_practice_time_minutes: int = 0
    score_history: List[ScoreHistoryPoint] = Field(default_factory=list)
    skill_breakdown: List[SkillBreakdownItem] = Field(default_factory=list)


# ════════════════════════════════════════════════════════════════════════
# Gap 4: Candidate Profile
# ════════════════════════════════════════════════════════════════════════


class CandidateProfileResponse(BaseModel):
    """Full candidate profile."""
    candidate_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    cgpa: Optional[float] = None
    skills: List[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    education: List[Dict[str, Any]] = Field(default_factory=list)
    work_experience: List[Dict[str, Any]] = Field(default_factory=list)
    plan: str = "free"
    created_at: Optional[datetime] = None


class UpdateCandidateProfileRequest(BaseModel):
    """Fields that can be updated on a candidate's profile."""
    full_name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    location: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=2000)
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)
    skills: Optional[List[str]] = None
    linkedin_url: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None, max_length=500)
    education: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None


# ════════════════════════════════════════════════════════════════════════
# Gap 5: Practice Questions
# ════════════════════════════════════════════════════════════════════════


class PracticeSkillDTO(BaseModel):
    id: str
    name: str
    question_count: int = 0
    completed_count: int = 0


class PracticeQuestionDTO(BaseModel):
    id: int
    title: str
    skill: str
    difficulty: str
    type: str  # "behavioral", "technical", "situational", "coding"
    completed: bool = False


class PracticeQuestionListResponse(BaseModel):
    skills: List[PracticeSkillDTO] = Field(default_factory=list)
    questions: List[PracticeQuestionDTO]
    pagination: PaginationMeta


# ════════════════════════════════════════════════════════════════════════
# Gap 6: Start Practice Session
# ════════════════════════════════════════════════════════════════════════


class StartPracticeRequest(BaseModel):
    interview_type: str = Field(
        ...,
        description="Type of practice interview (e.g. 'dsa', 'behavioral', 'system_design')",
        max_length=50,
    )
    difficulty: str = Field(
        default="medium",
        description="Difficulty level: easy, medium, hard",
        max_length=10,
    )
    consent_accepted: bool = Field(
        ...,
        description="Candidate consent for practice session",
    )


class StartPracticeResponse(BaseModel):
    submission_id: int
    status: str
    started_at: datetime
