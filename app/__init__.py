"""
AI Interviewer Backend Application

A multi-tenant interview orchestration platform with AI-assisted evaluation,
coding assessments, and integrity monitoring.

Architecture Overview:
- bootstrap/: FastAPI app initialization and middleware
- config/: Environment configuration and feature flags
- shared/: Cross-module utilities (errors, auth_context, observability)
- auth/: Identity & access control (JWT, RBAC)
- admin/: Control-plane operations (templates, rubrics, scheduling)
- interview/: Runtime interview orchestration engine
- evaluation/: Exchange-level scoring and results computation
- question/: Question selection and generation engine
- ai/: Provider abstraction for LLMs
- proctoring/: Integrity monitoring and risk scoring
- coding/: Sandboxed code execution
- audio/: Speech transcription and analysis
- persistence/: Database and cache infrastructure
"""

__version__ = "1.0.0"
