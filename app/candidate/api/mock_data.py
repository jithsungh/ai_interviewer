"""
Mock Data Fallback Module

Produces mock responses matching the exact frontend UI format
(sourced from data/frontend_mock_data). Used when no real candidate
data exists in the database.

This module is intentionally isolated so it can be removed once
real data flows through the system.
"""

from __future__ import annotations

from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
# Reusable fragments
# ═══════════════════════════════════════════════════════════════════

_ORG_TECHCORP = {
    "id": 1,
    "name": "TechCorp Inc.",
    "organization_type": "company",
    "plan": "enterprise",
    "domain": "techcorp.com",
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
}

_ORG_STANFORD = {
    "id": 2,
    "name": "Stanford University - CS Department",
    "organization_type": "educational",
    "plan": "pro",
    "domain": "stanford.edu",
    "status": "active",
    "created_at": "2024-06-01T00:00:00Z",
    "updated_at": "2025-01-15T00:00:00Z",
}

_ROLES = [
    {"id": 1, "name": "Backend Engineer", "description": "Server-side development with APIs and databases", "scope": "public"},
    {"id": 2, "name": "Frontend Engineer", "description": "Client-side development with React, Angular, Vue", "scope": "public"},
    {"id": 3, "name": "Full Stack Engineer", "description": "End-to-end web development", "scope": "public"},
    {"id": 4, "name": "DevOps Engineer", "description": "CI/CD, containerization, cloud infrastructure", "scope": "public"},
    {"id": 5, "name": "ML Engineer", "description": "Machine learning model development and deployment", "scope": "public"},
    {"id": 6, "name": "Data Scientist", "description": "Data analysis, statistics, and predictive modeling", "scope": "public"},
]

_TEMPLATES = [
    {"id": 1, "name": "DSA Fundamentals", "description": "Data Structures & Algorithms covering arrays, trees, graphs, and dynamic programming", "scope": "public", "total_estimated_time_minutes": 60, "version": 1, "is_active": True},
    {"id": 2, "name": "System Design", "description": "Design scalable distributed systems with architecture trade-offs", "scope": "public", "total_estimated_time_minutes": 90, "version": 1, "is_active": True},
    {"id": 3, "name": "Backend Engineering", "description": "Server-side development covering APIs, databases, and patterns", "scope": "public", "total_estimated_time_minutes": 75, "version": 1, "is_active": True},
    {"id": 4, "name": "Frontend Development", "description": "Modern frontend with React, state management, and performance", "scope": "public", "total_estimated_time_minutes": 60, "version": 1, "is_active": True},
    {"id": 5, "name": "Behavioral Interview", "description": "Leadership, communication, and problem-solving assessment", "scope": "public", "total_estimated_time_minutes": 45, "version": 1, "is_active": True},
]


# ═══════════════════════════════════════════════════════════════════
# Mock: candidate profile
# ═══════════════════════════════════════════════════════════════════

def mock_profile() -> dict:
    return {
        "candidate_id": 1,
        "full_name": "Alex Johnson",
        "email": "alex.johnson@university.edu",
        "phone": "+1 (555) 123-4567",
        "location": "San Francisco, CA",
        "bio": "Passionate software engineer with 3 years of experience in building scalable backend systems and modern web applications.",
        "experience_years": 3,
        "cgpa": 8.7,
        "skills": ["Python", "Java", "React", "Node.js", "PostgreSQL", "Docker", "Kubernetes", "System Design", "REST APIs", "Git"],
        "linkedin_url": "https://linkedin.com/in/alexjohnson",
        "github_url": "https://github.com/alexjohnson",
        "portfolio_url": "https://alexjohnson.dev",
        "education": [
            {"institution": "Stanford University", "degree": "M.S.", "field": "Computer Science", "start_year": 2020, "end_year": 2022, "gpa": 3.85},
            {"institution": "UC Berkeley", "degree": "B.S.", "field": "Computer Science", "start_year": 2016, "end_year": 2020, "gpa": 3.72},
        ],
        "work_experience": [
            {"company": "TechCorp Inc.", "title": "Software Engineer", "start_date": "2022-06-01", "end_date": None, "description": "Building microservices architecture for e-commerce platform serving 5M+ users.", "is_current": True},
            {"company": "StartupXYZ", "title": "Backend Developer Intern", "start_date": "2021-06-01", "end_date": "2021-09-01", "description": "Developed REST APIs and implemented caching strategies reducing latency by 40%.", "is_current": False},
        ],
        "plan": "pro",
        "status": "active",
        "user_type": "candidate",
        "last_login_at": "2025-02-28T14:30:00Z",
        "created_at": "2024-09-15T10:00:00Z",
        "updated_at": "2025-02-28T14:30:00Z",
    }


# ═══════════════════════════════════════════════════════════════════
# Mock: submission windows
# ═══════════════════════════════════════════════════════════════════

def mock_windows() -> list[dict]:
    return [
        {
            "id": 1,
            "name": "TechCorp Spring 2025 Hiring",
            "scope": "only_invited",
            "start_time": "2026-03-01T09:00:00Z",
            "end_time": "2026-03-20T23:59:00Z",
            "timezone": "America/Los_Angeles",
            "max_allowed_submissions": 1,
            "allow_after_end_time": False,
            "allow_resubmission": False,
            "candidate_submission_count": 0,
            "status": "open",
            "organization": {"id": 1, "name": "TechCorp Inc.", "organization_type": "company"},
            "role_templates": [
                {
                    "id": 1, "window_id": 1, "role_id": 1, "template_id": 3, "selection_weight": 1,
                    "role": _ROLES[0],
                    "template": _TEMPLATES[2],
                },
            ],
        },
        {
            "id": 2,
            "name": "Stanford CS Mock Interview - March 2025",
            "scope": "global",
            "start_time": "2026-03-05T08:00:00Z",
            "end_time": "2026-03-25T23:59:00Z",
            "timezone": "America/Los_Angeles",
            "max_allowed_submissions": 3,
            "allow_after_end_time": False,
            "allow_resubmission": True,
            "candidate_submission_count": 0,
            "status": "open",
            "organization": {"id": 2, "name": "Stanford University - CS Department", "organization_type": "educational"},
            "role_templates": [
                {
                    "id": 2, "window_id": 2, "role_id": 3, "template_id": 1, "selection_weight": 1,
                    "role": _ROLES[2],
                    "template": _TEMPLATES[0],
                },
            ],
        },
        {
            "id": 3,
            "name": "TechCorp DevOps Assessment",
            "scope": "only_invited",
            "start_time": "2026-03-10T09:00:00Z",
            "end_time": "2026-03-30T23:59:00Z",
            "timezone": "America/Los_Angeles",
            "max_allowed_submissions": 1,
            "allow_after_end_time": False,
            "allow_resubmission": False,
            "candidate_submission_count": 0,
            "status": "open",
            "organization": {"id": 1, "name": "TechCorp Inc.", "organization_type": "company"},
            "role_templates": [
                {
                    "id": 3, "window_id": 3, "role_id": 4, "template_id": 2, "selection_weight": 1,
                    "role": _ROLES[3],
                    "template": _TEMPLATES[1],
                },
            ],
        },
    ]


# ═══════════════════════════════════════════════════════════════════
# Mock: past submissions (flat list)
# ═══════════════════════════════════════════════════════════════════

def mock_submissions_list() -> list[dict]:
    """Flat list for GET /submissions."""
    return [
        {
            "submission_id": 1,
            "window": {"id": 100, "name": "TechCorp Winter Hiring Round"},
            "organization": {"id": 1, "name": "TechCorp Inc."},
            "role": {"id": 1, "name": "Backend Engineer"},
            "template": {"id": 1, "name": "DSA Fundamentals"},
            "status": "reviewed",
            "submitted_at": "2025-02-10T11:05:00Z",
            "started_at": "2025-02-10T10:02:00Z",
            "final_score": 85.0,
            "result_status": "pass",
            "recommendation": "hire",
            "mode": "live",
        },
        {
            "submission_id": 2,
            "window": {"id": 101, "name": "Stanford Mock Interviews - Jan 2025"},
            "organization": {"id": 2, "name": "Stanford University - CS Department"},
            "role": {"id": 3, "name": "Full Stack Engineer"},
            "template": {"id": 2, "name": "System Design"},
            "status": "completed",
            "submitted_at": "2025-01-20T15:35:00Z",
            "started_at": "2025-01-20T14:05:00Z",
            "final_score": 72.0,
            "result_status": "borderline",
            "recommendation": "review",
            "mode": "live",
        },
        {
            "submission_id": 3,
            "window": {"id": 102, "name": "TechCorp Frontend Hiring"},
            "organization": {"id": 1, "name": "TechCorp Inc."},
            "role": {"id": 2, "name": "Frontend Engineer"},
            "template": {"id": 4, "name": "Frontend Development"},
            "status": "reviewed",
            "submitted_at": "2024-12-15T10:00:00Z",
            "started_at": "2024-12-15T09:02:00Z",
            "final_score": 91.0,
            "result_status": "pass",
            "recommendation": "strong_hire",
            "mode": "live",
        },
    ]


# ═══════════════════════════════════════════════════════════════════
# Mock: detailed submission (for single-submission view)
# ═══════════════════════════════════════════════════════════════════

def mock_submission_detail(submission_id: int) -> dict | None:
    """Full nested submission for GET /submissions/{id}."""
    _details = {
        1: {
            "id": 1, "candidate_id": 1, "window_id": 100, "role_id": 1, "template_id": 1,
            "mode": "live", "status": "reviewed", "final_score": 85.0, "consent_captured": True,
            "started_at": "2025-02-10T10:02:00Z", "submitted_at": "2025-02-10T11:05:00Z",
            "created_at": "2025-02-10T10:00:00Z", "updated_at": "2025-02-10T12:00:00Z",
            "window": {
                "id": 100, "organization_id": 1, "admin_id": 1, "name": "TechCorp Winter Hiring Round",
                "scope": "only_invited", "start_time": "2025-02-01T09:00:00Z", "end_time": "2025-02-28T23:59:00Z",
                "timezone": "America/Los_Angeles", "max_allowed_submissions": 1,
                "allow_after_end_time": False, "allow_resubmission": False,
                "organization": _ORG_TECHCORP,
            },
            "role": _ROLES[0],
            "template": _TEMPLATES[0],
            "result": {
                "id": 1, "interview_submission_id": 1, "final_score": 85.0, "normalized_score": 85.0,
                "result_status": "pass", "recommendation": "hire",
                "section_scores": {"Self Introduction": 8.0, "Technical": 8.5, "Coding": 9.0, "Complexity Analysis": 8.0},
                "strengths": "Strong problem-solving skills with excellent understanding of data structures. Clean, well-structured code with optimal time complexity.",
                "weaknesses": "Could improve on explaining trade-offs in system design scenarios. Communication during complexity analysis could be more structured.",
                "summary_notes": "Excellent candidate with strong technical fundamentals. Recommended for next round.",
                "generated_by": "ai_evaluator_v2", "is_current": True,
                "computed_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
            },
            "exchanges": [
                {
                    "id": 1, "interview_submission_id": 1, "sequence_order": 1,
                    "question_text": "Tell me about yourself and your background in software engineering.",
                    "difficulty_at_time": "easy",
                    "response_text": "I am a software engineer with 3 years of experience...",
                    "response_time_ms": 120000, "created_at": "2025-02-10T10:02:00Z",
                    "evaluation": {
                        "id": 1, "interview_exchange_id": 1, "evaluator_type": "ai", "total_score": 80.0, "is_final": True,
                        "evaluated_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
                        "dimension_scores": [
                            {"id": 1, "evaluation_id": 1, "rubric_dimension_id": 1, "score": 8.0, "dimension_name": "Communication", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 2, "evaluation_id": 1, "rubric_dimension_id": 2, "score": 7.5, "dimension_name": "Structure", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 3, "evaluation_id": 1, "rubric_dimension_id": 3, "score": 8.5, "dimension_name": "Confidence", "created_at": "2025-02-10T12:00:00Z"},
                        ],
                    },
                    "audio_analytics": {
                        "id": 1, "interview_exchange_id": 1,
                        "transcript": "I am a software engineer with 3 years of experience building scalable backend systems...",
                        "confidence_score": 0.85, "speech_rate_wpm": 145, "filler_word_count": 3, "sentiment_score": 0.72,
                        "created_at": "2025-02-10T12:00:00Z",
                    },
                    "code_submission": None,
                },
                {
                    "id": 2, "interview_submission_id": 1, "sequence_order": 2,
                    "question_text": "Explain the difference between SQL and NoSQL databases. When would you use each?",
                    "difficulty_at_time": "medium",
                    "response_text": "SQL databases are relational databases that use structured query language...",
                    "response_time_ms": 180000, "created_at": "2025-02-10T10:05:00Z",
                    "evaluation": {
                        "id": 2, "interview_exchange_id": 2, "evaluator_type": "ai", "total_score": 88.0, "is_final": True,
                        "evaluated_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
                        "dimension_scores": [
                            {"id": 4, "evaluation_id": 2, "rubric_dimension_id": 1, "score": 9.0, "dimension_name": "Technical Accuracy", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 5, "evaluation_id": 2, "rubric_dimension_id": 2, "score": 8.5, "dimension_name": "Depth of Knowledge", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 6, "evaluation_id": 2, "rubric_dimension_id": 3, "score": 8.0, "dimension_name": "Communication", "created_at": "2025-02-10T12:00:00Z"},
                        ],
                    },
                    "audio_analytics": None,
                    "code_submission": None,
                },
                {
                    "id": 3, "interview_submission_id": 1, "sequence_order": 3,
                    "question_text": "How would you design a rate limiter for an API gateway?",
                    "difficulty_at_time": "hard",
                    "response_text": "A rate limiter can be implemented using several algorithms like token bucket or sliding window...",
                    "response_time_ms": 300000, "created_at": "2025-02-10T10:10:00Z",
                    "evaluation": {
                        "id": 3, "interview_exchange_id": 3, "evaluator_type": "ai", "total_score": 82.0, "is_final": True,
                        "evaluated_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
                        "dimension_scores": [
                            {"id": 7, "evaluation_id": 3, "rubric_dimension_id": 1, "score": 8.5, "dimension_name": "Technical Accuracy", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 8, "evaluation_id": 3, "rubric_dimension_id": 2, "score": 7.5, "dimension_name": "System Thinking", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 9, "evaluation_id": 3, "rubric_dimension_id": 3, "score": 8.5, "dimension_name": "Trade-off Analysis", "created_at": "2025-02-10T12:00:00Z"},
                        ],
                    },
                    "audio_analytics": None,
                    "code_submission": None,
                },
                {
                    "id": 4, "interview_submission_id": 1, "sequence_order": 4,
                    "question_text": "Two Sum: Given an array of integers and a target, return indices of two numbers that add up to target.",
                    "difficulty_at_time": "easy", "coding_problem_id": 1,
                    "response_text": None,
                    "response_code": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target-n], i]\n        seen[n] = i",
                    "response_time_ms": 480000, "created_at": "2025-02-10T10:20:00Z",
                    "evaluation": {
                        "id": 4, "interview_exchange_id": 4, "evaluator_type": "ai", "total_score": 92.0, "is_final": True,
                        "evaluated_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
                        "dimension_scores": [
                            {"id": 10, "evaluation_id": 4, "rubric_dimension_id": 1, "score": 9.5, "dimension_name": "Correctness", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 11, "evaluation_id": 4, "rubric_dimension_id": 2, "score": 9.0, "dimension_name": "Code Quality", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 12, "evaluation_id": 4, "rubric_dimension_id": 3, "score": 9.0, "dimension_name": "Efficiency", "created_at": "2025-02-10T12:00:00Z"},
                        ],
                    },
                    "audio_analytics": None,
                    "code_submission": {
                        "id": 1, "interview_exchange_id": 4, "coding_problem_id": 1, "language": "python",
                        "source_code": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target-n], i]\n        seen[n] = i",
                        "execution_status": "passed", "score": 100, "execution_time_ms": 12, "memory_kb": 14200,
                        "submitted_at": "2025-02-10T10:28:00Z", "created_at": "2025-02-10T10:28:00Z",
                        "execution_results": [
                            {"id": 1, "code_submission_id": 1, "test_case_id": 1, "passed": True, "actual_output": "[0, 1]", "runtime_ms": 4, "memory_kb": 14200, "exit_code": 0, "created_at": "2025-02-10T10:28:00Z"},
                            {"id": 2, "code_submission_id": 1, "test_case_id": 2, "passed": True, "actual_output": "[1, 2]", "runtime_ms": 3, "memory_kb": 14100, "exit_code": 0, "created_at": "2025-02-10T10:28:00Z"},
                            {"id": 3, "code_submission_id": 1, "test_case_id": 3, "passed": True, "actual_output": "[0, 1]", "runtime_ms": 5, "memory_kb": 14300, "exit_code": 0, "created_at": "2025-02-10T10:28:00Z"},
                        ],
                    },
                },
                {
                    "id": 5, "interview_submission_id": 1, "sequence_order": 5,
                    "question_text": "What is the time and space complexity of your Two Sum solution? Can you explain why?",
                    "difficulty_at_time": "medium",
                    "response_text": "The time complexity is O(n) because we iterate through the array once...",
                    "response_time_ms": 90000, "created_at": "2025-02-10T10:30:00Z",
                    "evaluation": {
                        "id": 5, "interview_exchange_id": 5, "evaluator_type": "ai", "total_score": 85.0, "is_final": True,
                        "evaluated_at": "2025-02-10T12:00:00Z", "created_at": "2025-02-10T12:00:00Z",
                        "dimension_scores": [
                            {"id": 13, "evaluation_id": 5, "rubric_dimension_id": 1, "score": 9.0, "dimension_name": "Accuracy", "created_at": "2025-02-10T12:00:00Z"},
                            {"id": 14, "evaluation_id": 5, "rubric_dimension_id": 2, "score": 8.0, "dimension_name": "Explanation Clarity", "created_at": "2025-02-10T12:00:00Z"},
                        ],
                    },
                    "audio_analytics": None,
                    "code_submission": None,
                },
            ],
            "proctoring_events": [
                {"id": 1, "interview_submission_id": 1, "event_type": "tab_switch", "severity": "low", "risk_weight": 0.1, "occurred_at": "2025-02-10T10:15:00Z", "created_at": "2025-02-10T10:15:00Z"},
            ],
        },
        2: {
            "id": 2, "candidate_id": 1, "window_id": 101, "role_id": 3, "template_id": 2,
            "mode": "live", "status": "completed", "final_score": 72.0, "consent_captured": True,
            "started_at": "2025-01-20T14:05:00Z", "submitted_at": "2025-01-20T15:35:00Z",
            "created_at": "2025-01-20T14:00:00Z", "updated_at": "2025-01-20T16:00:00Z",
            "window": {
                "id": 101, "organization_id": 2, "admin_id": 2, "name": "Stanford Mock Interviews - Jan 2025",
                "scope": "global", "start_time": "2025-01-15T08:00:00Z", "end_time": "2025-01-31T23:59:00Z",
                "timezone": "America/Los_Angeles", "max_allowed_submissions": 3,
                "allow_after_end_time": False, "allow_resubmission": True,
                "organization": _ORG_STANFORD,
            },
            "role": _ROLES[2],
            "template": _TEMPLATES[1],
            "result": {
                "id": 2, "interview_submission_id": 2, "final_score": 72.0, "normalized_score": 72.0,
                "result_status": "borderline", "recommendation": "review",
                "section_scores": {"Self Introduction": 7.5, "Technical": 7.0, "Coding": 7.5, "Complexity Analysis": 7.0},
                "strengths": "Good understanding of distributed systems basics. Clear communication style.",
                "weaknesses": "Needs deeper knowledge of caching strategies and database sharding. Should practice more system design problems.",
                "summary_notes": "Shows potential but needs more preparation in advanced system design topics.",
                "generated_by": "ai_evaluator_v2", "is_current": True,
                "computed_at": "2025-01-20T16:00:00Z", "created_at": "2025-01-20T16:00:00Z",
            },
            "exchanges": [],
            "proctoring_events": [],
        },
        3: {
            "id": 3, "candidate_id": 1, "window_id": 102, "role_id": 2, "template_id": 4,
            "mode": "live", "status": "reviewed", "final_score": 91.0, "consent_captured": True,
            "started_at": "2024-12-15T09:02:00Z", "submitted_at": "2024-12-15T10:00:00Z",
            "created_at": "2024-12-15T09:00:00Z", "updated_at": "2024-12-15T11:00:00Z",
            "window": {
                "id": 102, "organization_id": 1, "admin_id": 1, "name": "TechCorp Frontend Hiring",
                "scope": "only_invited", "start_time": "2024-12-10T09:00:00Z", "end_time": "2024-12-20T23:59:00Z",
                "timezone": "America/Los_Angeles", "max_allowed_submissions": 1,
                "allow_after_end_time": False, "allow_resubmission": False,
                "organization": _ORG_TECHCORP,
            },
            "role": _ROLES[1],
            "template": _TEMPLATES[3],
            "result": {
                "id": 3, "interview_submission_id": 3, "final_score": 91.0, "normalized_score": 91.0,
                "result_status": "pass", "recommendation": "strong_hire",
                "section_scores": {"Self Introduction": 9.0, "Technical": 9.5, "Coding": 9.0, "Complexity Analysis": 8.5},
                "strengths": "Exceptional React knowledge. Clean component architecture. Excellent understanding of performance optimization.",
                "weaknesses": "Minor gaps in accessibility best practices.",
                "summary_notes": "Outstanding candidate. Strong hire recommendation for frontend role.",
                "generated_by": "ai_evaluator_v2", "is_current": True,
                "computed_at": "2024-12-15T11:00:00Z", "created_at": "2024-12-15T11:00:00Z",
            },
            "exchanges": [],
            "proctoring_events": [],
        },
    }
    return _details.get(submission_id)


# ═══════════════════════════════════════════════════════════════════
# Mock: performance statistics
# ═══════════════════════════════════════════════════════════════════

def mock_stats() -> dict:
    return {
        "total_interviews": 3,
        "average_score": 83.0,
        "pass_rate": 67.0,
        "total_practice_time_minutes": 1110,
        "total_practice_time": "18h 30m",
        "strong_areas": ["coding_round", "problem_solving", "behavioral"],
        "improvement_areas": ["resume_analysis", "self_introduction", "system_design"],
        "score_history": [
            {"date": "2025-10", "score": 68},
            {"date": "2025-11", "score": 74},
            {"date": "2025-12", "score": 91},
            {"date": "2026-01", "score": 72},
            {"date": "2026-02", "score": 85},
        ],
        "skill_breakdown": [
            {"skill": "behavioral", "score": 81},
            {"skill": "coding_round", "score": 89},
            {"skill": "resume_analysis", "score": 74},
            {"skill": "self_introduction", "score": 76},
            {"skill": "problem_solving", "score": 84},
            {"skill": "system_design", "score": 79},
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# Mock: practice data
# ═══════════════════════════════════════════════════════════════════

def mock_practice_skills() -> list[dict]:
    return [
        {"id": "arrays", "name": "Arrays & Strings", "icon": "\U0001f4ca", "question_count": 45, "completed_count": 12, "color": "bg-chart-1/10 text-chart-1"},
        {"id": "trees", "name": "Trees & Graphs", "icon": "\U0001f333", "question_count": 38, "completed_count": 8, "color": "bg-chart-2/10 text-chart-2"},
        {"id": "dp", "name": "Dynamic Programming", "icon": "\U0001f9e9", "question_count": 32, "completed_count": 5, "color": "bg-chart-3/10 text-chart-3"},
        {"id": "system-design", "name": "System Design", "icon": "\U0001f3d7\ufe0f", "question_count": 20, "completed_count": 6, "color": "bg-chart-4/10 text-chart-4"},
        {"id": "api-design", "name": "REST API Design", "icon": "\U0001f517", "question_count": 15, "completed_count": 10, "color": "bg-chart-5/10 text-chart-5"},
        {"id": "behavioral", "name": "Behavioral", "icon": "\U0001f5e3\ufe0f", "question_count": 25, "completed_count": 14, "color": "bg-chart-1/10 text-chart-1"},
        {"id": "sql", "name": "SQL & Databases", "icon": "\U0001f5c4\ufe0f", "question_count": 28, "completed_count": 9, "color": "bg-chart-2/10 text-chart-2"},
        {"id": "oop", "name": "OOP & Design Patterns", "icon": "\u2699\ufe0f", "question_count": 22, "completed_count": 7, "color": "bg-chart-3/10 text-chart-3"},
    ]


def mock_practice_questions() -> list[dict]:
    return [
        {"id": 1, "skill": "arrays", "title": "Given an array of integers, find the maximum subarray sum using Kadane's algorithm.", "difficulty": "medium", "type": "coding", "estimated_time_minutes": 15, "completed": False},
        {"id": 2, "skill": "arrays", "title": "Implement a function to rotate an array to the right by k steps.", "difficulty": "easy", "type": "coding", "estimated_time_minutes": 10, "completed": True},
        {"id": 3, "skill": "trees", "title": "Given a binary tree, determine if it is height-balanced.", "difficulty": "medium", "type": "coding", "estimated_time_minutes": 20, "completed": False},
        {"id": 4, "skill": "dp", "title": "Find the length of the longest increasing subsequence in an array.", "difficulty": "hard", "type": "coding", "estimated_time_minutes": 30, "completed": False},
        {"id": 5, "skill": "system-design", "title": "Design a chat application like WhatsApp. Focus on message delivery guarantees.", "difficulty": "hard", "type": "system-design", "estimated_time_minutes": 45, "completed": False},
        {"id": 6, "skill": "behavioral", "title": "Tell me about a time you had to deal with a difficult team member.", "difficulty": "medium", "type": "behavioral", "estimated_time_minutes": 10, "completed": True},
    ]


# ═══════════════════════════════════════════════════════════════════
# Mock: resumes
# ═══════════════════════════════════════════════════════════════════

def mock_resumes() -> list[dict]:
    return [
        {
            "id": 1,
            "candidate_id": 1,
            "file_url": "/resumes/alex_johnson_resume.pdf",
            "parsed_text": "Alex Johnson\nSoftware Engineer\n3 years of experience...",
            "extracted_data": {
                "name": "Alex Johnson",
                "email": "alex.johnson@university.edu",
                "phone": "+1 (555) 123-4567",
                "skills": ["Python", "Java", "React", "Node.js", "PostgreSQL", "Docker", "Kubernetes"],
                "experience_years": 3,
                "education": [
                    {"institution": "Stanford University", "degree": "M.S.", "field": "Computer Science", "start_year": 2020, "end_year": 2022, "gpa": 3.85},
                    {"institution": "UC Berkeley", "degree": "B.S.", "field": "Computer Science", "start_year": 2016, "end_year": 2020, "gpa": 3.72},
                ],
                "work_experience": [
                    {"company": "TechCorp Inc.", "title": "Software Engineer", "start_date": "2022-06-01", "end_date": None, "description": "Building microservices architecture for e-commerce platform serving 5M+ users.", "is_current": True},
                    {"company": "StartupXYZ", "title": "Backend Developer Intern", "start_date": "2021-06-01", "end_date": "2021-09-01", "description": "Developed REST APIs and implemented caching strategies reducing latency by 40%.", "is_current": False},
                ],
                "certifications": ["AWS Solutions Architect Associate", "Kubernetes Certified Developer"],
                "summary": "Experienced software engineer with strong backend skills and growing frontend expertise.",
                "match_score": 87,
                "feedback": [
                    {"category": "Skills Match", "score": 90, "feedback": "Strong alignment with target roles.", "suggestions": ["Add more cloud-specific certifications", "Highlight system design experience"]},
                    {"category": "Experience", "score": 85, "feedback": "Good progression from intern to full-time.", "suggestions": ["Quantify more achievements", "Add impact metrics"]},
                    {"category": "Format & Structure", "score": 82, "feedback": "Well-organized but could be more concise.", "suggestions": ["Reduce to 1 page", "Use more action verbs"]},
                    {"category": "Keywords", "score": 88, "feedback": "Good keyword coverage for backend roles.", "suggestions": ["Add more system design keywords", "Include specific methodology terms"]},
                ],
            },
            "uploaded_at": "2025-01-15T10:00:00Z",
            "created_at": "2025-01-15T10:00:00Z",
        },
    ]
