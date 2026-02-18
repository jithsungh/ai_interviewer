"""
Domain Constants

Immutable constants used throughout the application.
No magic numbers in business logic - all constants defined here.
"""

from typing import Final

# ====================
# Code Execution
# ====================
SUPPORTED_LANGUAGES: Final[list[str]] = ["cpp", "java", "python3"]
MAX_CODE_SIZE_BYTES: Final[int] = 100_000
MAX_TEST_CASE_INPUT_SIZE_BYTES: Final[int] = 10_485_760  # 10MB

# ====================
# Interview
# ====================
MAX_QUESTION_LENGTH: Final[int] = 10_000
MAX_ANSWER_LENGTH: Final[int] = 50_000
MAX_EXCHANGES_PER_INTERVIEW: Final[int] = 50

# ====================
# Evaluation
# ====================
MIN_EVALUATION_SCORE: Final[float] = 0.0
MAX_EVALUATION_SCORE: Final[float] = 100.0
DEFAULT_RUBRIC_WEIGHT: Final[int] = 1

# ====================
# Audio
# ====================
AUDIO_SAMPLE_RATE: Final[int] = 16000
AUDIO_CHANNELS: Final[int] = 1
MAX_AUDIO_CHUNK_SIZE_BYTES: Final[int] = 1_048_576  # 1MB

# ====================
# Status Values
# ====================
INTERVIEW_STATUS_VALUES: Final[list[str]] = [
    "scheduled",
    "in_progress",
    "completed",
    "cancelled"
]

SUBMISSION_STATUS_VALUES: Final[list[str]] = [
    "pending",
    "running",
    "passed",
    "failed",
    "error",
    "timeout",
    "memory_exceeded"
]

# ====================
# Time Constants
# ====================
SECONDS_PER_MINUTE: Final[int] = 60
MILLISECONDS_PER_SECOND: Final[int] = 1000
MICROSECONDS_PER_SECOND: Final[int] = 1_000_000

# ====================
# File Size Constants
# ====================
BYTES_PER_KB: Final[int] = 1024
BYTES_PER_MB: Final[int] = 1024 * 1024
BYTES_PER_GB: Final[int] = 1024 * 1024 * 1024

# ====================
# Pagination
# ====================
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 1

# ====================
# Password Requirements
# ====================
MIN_PASSWORD_LENGTH: Final[int] = 8
MAX_PASSWORD_LENGTH: Final[int] = 128

# ====================
# API Versioning
# ====================
API_V1_PREFIX: Final[str] = "/api/v1"

# ====================
# Question Types
# ====================
QUESTION_TYPES: Final[list[str]] = [
    "coding",
    "system_design",
    "behavioral",
    "technical_knowledge"
]

# ====================
# Difficulty Levels
# ====================
DIFFICULTY_LEVELS: Final[list[str]] = [
    "easy",
    "medium",
    "hard"
]

# ====================
# User Roles
# ====================
USER_ROLES: Final[list[str]] = [
    "candidate",
    "interviewer",
    "admin",
    "organization_admin"
]

# ====================
# Proctoring
# ====================
MAX_TAB_SWITCH_WARNINGS: Final[int] = 3
MAX_OFFLINE_DURATION_SECONDS: Final[int] = 30
FACE_DETECTION_INTERVAL_MS: Final[int] = 5000  # 5 seconds

# ====================
# Embedding
# ====================
DEFAULT_EMBEDDING_DIM: Final[int] = 768  # Self-hosted all-mpnet-base-v2 (default)
OPENAI_EMBEDDING_DIM: Final[int] = 1536  # text-embedding-ada-002 (alternative)
OPENAI_EMBEDDING_DIM_LARGE: Final[int] = 3072  # text-embedding-3-large (alternative)

# ====================
# Vector Search
# ====================
DEFAULT_TOP_K: Final[int] = 10
MAX_TOP_K: Final[int] = 100
MIN_SIMILARITY_THRESHOLD: Final[float] = 0.7
