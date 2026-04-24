"""
Candidate API Contracts

Pydantic request/response schemas for candidate-facing endpoints:
- Window listing (Gap 1)
- Submission history (Gap 2)
- Submission detail
- Performance statistics (Gap 3)
- Profile management (Gap 4)
- Practice question listing (Gap 5)
- Practice submission creation (Gap 6)
- Resume listing
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
    organization_type: Optional[str] = None


class WindowRoleDTO(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    scope: Optional[str] = None


class WindowTemplateDTO(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    scope: Optional[str] = None
    total_estimated_time_minutes: Optional[int] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None


class WindowRoleTemplateDTO(BaseModel):
    id: int
    window_id: int
    role_id: int
    template_id: int
    selection_weight: int = 1
    role: WindowRoleDTO
    template: WindowTemplateDTO


class CandidateWindowDTO(BaseModel):
    """A single interview window visible to the candidate."""
    id: int
    name: str
    scope: str
    start_time: datetime
    end_time: datetime
    timezone: Optional[str] = None
    organization: WindowOrganizationDTO
    role_templates: List[WindowRoleTemplateDTO] = Field(default_factory=list)
    max_allowed_submissions: Optional[int] = None
    allow_after_end_time: bool = False
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


class SubmissionTemplateDTO(BaseModel):
    id: int
    name: str


class CandidateSubmissionDTO(BaseModel):
    """A single past submission for the candidate."""
    submission_id: int
    window: SubmissionWindowDTO
    organization: SubmissionOrganizationDTO
    role: SubmissionRoleDTO
    template: Optional[SubmissionTemplateDTO] = None
    status: str
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    final_score: Optional[float] = None
    result_status: Optional[str] = None
    recommendation: Optional[str] = None
    mode: Optional[str] = None


class CandidateSubmissionListResponse(BaseModel):
    data: List[CandidateSubmissionDTO]
    pagination: PaginationMeta


# ════════════════════════════════════════════════════════════════════════
# Submission Detail (nested structures for full view)
# ════════════════════════════════════════════════════════════════════════


class DetailDimensionScoreDTO(BaseModel):
    id: int
    evaluation_id: int
    rubric_dimension_id: int
    score: float
    dimension_name: str
    created_at: Optional[str] = None


class DetailEvaluationDTO(BaseModel):
    id: int
    interview_exchange_id: int
    evaluator_type: str
    total_score: Optional[float] = None
    is_final: bool = True
    evaluated_at: Optional[str] = None
    created_at: Optional[str] = None
    dimension_scores: List[DetailDimensionScoreDTO] = Field(default_factory=list)


class DetailAudioAnalyticsDTO(BaseModel):
    id: int
    interview_exchange_id: int
    transcript: Optional[str] = None
    confidence_score: Optional[float] = None
    speech_rate_wpm: Optional[int] = None
    filler_word_count: Optional[int] = None
    sentiment_score: Optional[float] = None
    created_at: Optional[str] = None


class DetailCodeExecutionResultDTO(BaseModel):
    id: int
    code_submission_id: int
    test_case_id: int
    passed: bool
    actual_output: Optional[str] = None
    runtime_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    exit_code: Optional[int] = None
    created_at: Optional[str] = None


class DetailCodeSubmissionDTO(BaseModel):
    id: int
    interview_exchange_id: int
    coding_problem_id: int
    language: str
    source_code: Optional[str] = None
    execution_status: Optional[str] = None
    score: Optional[float] = None
    execution_time_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    submitted_at: Optional[str] = None
    created_at: Optional[str] = None
    execution_results: List[DetailCodeExecutionResultDTO] = Field(default_factory=list)


class DetailExchangeDTO(BaseModel):
    id: int
    interview_submission_id: int
    sequence_order: int
    question_text: Optional[str] = None
    difficulty_at_time: Optional[str] = None
    coding_problem_id: Optional[int] = None
    response_text: Optional[str] = None
    response_code: Optional[str] = None
    response_time_ms: Optional[int] = None
    created_at: Optional[str] = None
    evaluation: Optional[DetailEvaluationDTO] = None
    audio_analytics: Optional[DetailAudioAnalyticsDTO] = None
    code_submission: Optional[DetailCodeSubmissionDTO] = None


class DetailResultDTO(BaseModel):
    id: int
    interview_submission_id: int
    final_score: Optional[float] = None
    normalized_score: Optional[float] = None
    result_status: Optional[str] = None
    recommendation: Optional[str] = None
    section_scores: Optional[Dict[str, Any]] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    summary_notes: Optional[str] = None
    generated_by: Optional[str] = None
    is_current: bool = True
    computed_at: Optional[str] = None
    created_at: Optional[str] = None


class DetailWindowOrganizationDTO(BaseModel):
    id: int
    name: str
    organization_type: Optional[str] = None
    plan: Optional[str] = None
    domain: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DetailWindowDTO(BaseModel):
    id: int
    organization_id: int
    admin_id: Optional[int] = None
    name: str
    scope: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    max_allowed_submissions: Optional[int] = None
    allow_after_end_time: bool = False
    allow_resubmission: bool = False
    organization: Optional[DetailWindowOrganizationDTO] = None


class DetailRoleDTO(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    scope: Optional[str] = None


class DetailTemplateDTO(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    scope: Optional[str] = None
    total_estimated_time_minutes: Optional[int] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None


class DetailProctoringEventDTO(BaseModel):
    id: int
    interview_submission_id: int
    event_type: str
    severity: Optional[str] = None
    risk_weight: Optional[float] = None
    occurred_at: Optional[str] = None
    created_at: Optional[str] = None


class CandidateSubmissionDetailResponse(BaseModel):
    """Full nested submission detail."""
    id: int
    candidate_id: int
    window_id: int
    role_id: int
    template_id: int
    mode: Optional[str] = None
    status: str
    final_score: Optional[float] = None
    consent_captured: bool = False
    started_at: Optional[str] = None
    submitted_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    window: Optional[DetailWindowDTO] = None
    role: Optional[DetailRoleDTO] = None
    template: Optional[DetailTemplateDTO] = None
    result: Optional[DetailResultDTO] = None
    exchanges: List[DetailExchangeDTO] = Field(default_factory=list)
    proctoring_events: List[DetailProctoringEventDTO] = Field(default_factory=list)


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
    total_practice_time: Optional[str] = None
    strong_areas: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)
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
    status: Optional[str] = None
    user_type: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
# Gap 4b: Candidate Settings
# ════════════════════════════════════════════════════════════════════════


class CandidateNotificationPreferences(BaseModel):
    email: bool = True
    interview: bool = True
    reports: bool = True
    marketing: bool = False


class CandidatePrivacyPreferences(BaseModel):
    profileVisible: bool = True
    shareResults: bool = False
    allowAnalytics: bool = True


class CandidateUiPreferences(BaseModel):
    theme: str = "system"


class CandidateSettingsResponse(BaseModel):
    candidate_id: int
    notification_preferences: CandidateNotificationPreferences
    privacy_preferences: CandidatePrivacyPreferences
    ui_preferences: CandidateUiPreferences = Field(default_factory=CandidateUiPreferences)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateCandidateSettingsRequest(BaseModel):
    notification_preferences: Optional[CandidateNotificationPreferences] = None
    privacy_preferences: Optional[CandidatePrivacyPreferences] = None
    ui_preferences: Optional[CandidateUiPreferences] = None


# ════════════════════════════════════════════════════════════════════════
# Career Path
# ════════════════════════════════════════════════════════════════════════


class CareerMarketInsightDTO(BaseModel):
    role: str
    industryTag: str
    icon: str
    skills: List[str] = Field(default_factory=list)
    minPackage: int
    maxPackage: int
    growth: int
    trend: str


class GenerateCareerInsightsRequest(BaseModel):
    industry: str = Field(..., min_length=2, max_length=120)
    seniority: str = Field(..., min_length=2, max_length=30)
    use_cached: bool = Field(default=True)


class GenerateCareerInsightsResponse(BaseModel):
    run_id: int
    industry: str
    seniority: str
    generation_source: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    insights: List[CareerMarketInsightDTO] = Field(default_factory=list)
    created_at: datetime


class CareerRoadmapStepDTO(BaseModel):
    level: int
    levelLabel: str
    roleTitle: str
    requiredCourses: List[str] = Field(default_factory=list)
    keyLearning: str
    certification: str


class GenerateCareerRoadmapRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=200)
    industry: str = Field(..., min_length=2, max_length=120)
    insight_run_id: Optional[int] = Field(default=None, gt=0)
    selected_insight: Optional[CareerMarketInsightDTO] = None


class CareerRoadmapResponse(BaseModel):
    roadmap_id: int
    candidate_id: int
    insight_run_id: Optional[int] = None
    industry: str
    target_role: str
    selected_insight: Optional[CareerMarketInsightDTO] = None
    steps: List[CareerRoadmapStepDTO] = Field(default_factory=list)
    completed_levels: List[int] = Field(default_factory=list)
    current_level: int = 1
    is_active: bool = True
    generation_source: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UpdateCareerRoadmapProgressRequest(BaseModel):
    completed_levels: List[int] = Field(default_factory=list)
    current_level: Optional[int] = Field(default=None, ge=1, le=4)


class CareerRoadmapHistoryResponse(BaseModel):
    data: List[CareerRoadmapResponse] = Field(default_factory=list)
    pagination: PaginationMeta


class CareerRoadmapActiveResponse(BaseModel):
    roadmap: Optional[CareerRoadmapResponse] = None


# ════════════════════════════════════════════════════════════════════════
# Gap 5: Practice Questions
# ════════════════════════════════════════════════════════════════════════


class PracticeSkillDTO(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    question_count: int = 0
    completed_count: int = 0
    color: Optional[str] = None


class PracticeQuestionDTO(BaseModel):
    id: int
    title: str
    skill: str
    difficulty: str
    type: str  # "behavioral", "technical", "situational", "coding"
    estimated_time_minutes: Optional[int] = None
    completed: bool = False


class PracticeQuestionListResponse(BaseModel):
    skills: List[PracticeSkillDTO] = Field(default_factory=list)
    questions: List[PracticeQuestionDTO]
    pagination: PaginationMeta


# ════════════════════════════════════════════════════════════════════════
# Interview Prep Flashcards
# ════════════════════════════════════════════════════════════════════════


class PracticeFlashcardDTO(BaseModel):
    source_question_id: int
    topic: str
    difficulty: str
    question: str
    answer: str
    tags: List[str] = Field(default_factory=list)
    hint: Optional[str] = None


class GeneratePracticeFlashcardsRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=120)
    industry: str = Field(..., min_length=2, max_length=120)
    question_type: Optional[str] = Field(None, max_length=30)
    difficulty: Optional[str] = Field(None, max_length=20)
    card_count: int = Field(10, ge=1, le=20)
    use_cached: bool = Field(default=True)


class PracticeFlashcardDeckResponse(BaseModel):
    deck_id: int
    candidate_id: int
    role: str
    industry: str
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    card_count: int
    source_question_ids: List[int] = Field(default_factory=list)
    flashcards: List[PracticeFlashcardDTO] = Field(default_factory=list)
    bookmarked_indices: List[int] = Field(default_factory=list)
    mastered_indices: List[int] = Field(default_factory=list)
    current_card_index: int = 0
    progress_percent: int = 0
    is_active: bool = True
    generation_source: str = "db"
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PracticeFlashcardDeckSummaryDTO(BaseModel):
    deck_id: int
    role: str
    industry: str
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    card_count: int
    current_card_index: int = 0
    progress_percent: int = 0
    is_active: bool = True
    generation_source: str = "db"
    created_at: datetime
    updated_at: datetime


class PracticeFlashcardDeckHistoryResponse(BaseModel):
    data: List[PracticeFlashcardDeckSummaryDTO] = Field(default_factory=list)
    pagination: PaginationMeta


class PracticeFlashcardDeckActiveResponse(BaseModel):
    deck: Optional[PracticeFlashcardDeckResponse] = None


class UpdatePracticeFlashcardDeckProgressRequest(BaseModel):
    current_card_index: int = Field(0, ge=0)
    mastered_indices: List[int] = Field(default_factory=list)
    bookmarked_indices: List[int] = Field(default_factory=list)


# ════════════════════════════════════════════════════════════════════════
# Gap 6: Start Practice Session
# ════════════════════════════════════════════════════════════════════════


class PracticeTemplateSectionDTO(BaseModel):
    """Which sections are enabled in a template."""
    resume_analysis: bool = False
    self_introduction: bool = False
    topics_assessment: bool = False
    coding_round: bool = False
    complexity_analysis: bool = False
    behavioral: bool = False


class PracticeTemplateTopicDTO(BaseModel):
    topic_id: int
    topic_name: str
    weight: Optional[int] = None


class PracticeTemplateDTO(BaseModel):
    """A template card shown on the Interview Setup page."""
    id: int
    name: str
    description: Optional[str] = None
    category: str  # short label: DSA, SYSTEM DESIGN, BACKEND, etc.
    total_estimated_time_minutes: Optional[int] = None
    total_questions: Optional[int] = None
    target_level: Optional[str] = None
    topics: List[PracticeTemplateTopicDTO] = Field(default_factory=list)
    sections: Optional[PracticeTemplateSectionDTO] = None
    difficulty_distribution: Optional[Dict[str, int]] = None
    is_active: bool = True


class PracticeTemplateListResponse(BaseModel):
    templates: List[PracticeTemplateDTO] = Field(default_factory=list)


class StartPracticeRequest(BaseModel):
    template_id: int = Field(..., gt=0, description="ID of the interview template to use")
    experience_level: str = Field(
        default="mid_level",
        description="Experience level: fresher, junior, mid_level, senior, lead",
        max_length=20,
    )
    target_company: Optional[str] = Field(
        None,
        description="Optional target company style (e.g. 'FAANG Style', 'Startup')",
        max_length=100,
    )
    voice_interview: bool = Field(default=True, description="Enable voice interview")
    video_recording: bool = Field(default=False, description="Enable video recording")
    ai_proctoring: bool = Field(default=False, description="Enable AI proctoring")
    consent_accepted: bool = Field(..., description="Candidate consent for practice session")


class DifficultyDistributionDTO(BaseModel):
    easy: int = 0
    medium: int = 0
    hard: int = 0


class SessionSummaryDTO(BaseModel):
    """Session summary shown on the right side of Interview Setup."""
    interview_type: str
    duration_minutes: Optional[int] = None
    total_questions: Optional[int] = None
    experience_level: str
    difficulty_distribution: Optional[DifficultyDistributionDTO] = None
    topics: List[str] = Field(default_factory=list)
    adaptive: bool = True


class StartPracticeResponse(BaseModel):
    submission_id: int
    status: str
    started_at: datetime
    session_summary: Optional[SessionSummaryDTO] = None


# ════════════════════════════════════════════════════════════════════════
# Resume Listing
# ════════════════════════════════════════════════════════════════════════


class ResumeDTO(BaseModel):
    id: int
    candidate_id: int
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    parsed_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    
    # LLM Analysis Results
    structured_json: Optional[Dict[str, Any]] = None
    llm_feedback: Optional[Dict[str, Any]] = None
    ats_score: Optional[int] = None
    ats_feedback: Optional[str] = None
    
    # Processing Status
    parse_status: Optional[str] = None
    llm_analysis_status: Optional[str] = None
    
    # Timestamps
    uploaded_at: Optional[str] = None
    analyzed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None



class ResumeListResponse(BaseModel):
    data: List[ResumeDTO] = Field(default_factory=list)


class ResumeUploadResponse(BaseModel):
    id: int
    candidate_id: int
    file_url: str
    file_name: Optional[str] = None
    parsed_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    
    # LLM Analysis Results
    structured_json: Optional[Dict[str, Any]] = None
    llm_feedback: Optional[Dict[str, Any]] = None
    ats_score: Optional[int] = None
    ats_feedback: Optional[str] = None
    
    # Processing Status
    parse_status: Optional[str] = None
    llm_analysis_status: Optional[str] = None
    
    # Timestamps
    uploaded_at: Optional[str] = None
    analyzed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

