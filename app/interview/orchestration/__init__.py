"""
Interview Orchestration — Runtime Coordination Layer

The orchestration layer is the runtime brain of the interview module.
It coordinates exchange lifecycle, question sequencing, progress tracking,
and race condition resolution.

Architectural Philosophy:
    The orchestration layer COORDINATES. It does NOT score, parse rubrics,
    or make AI calls. It delegates to domain modules: question, coding,
    audio, evaluation. It enforces architectural invariants at runtime.

Public API:
- Coordinator: ExchangeCoordinator (central orchestration service)
- Sequencer: resolve_next_question, validate_template_snapshot
- Handlers: AudioCompletionHandler, CodingCompletionHandler
- Progress: ProgressTracker
- Race Safety: RaceResolver
- Contracts: NextQuestionResult, TemplateSnapshot, ProgressUpdate, etc.
- Errors: TemplateSnapshotMissingError, SequenceMismatchError, etc.

Invariants Enforced:
- Template snapshot immutability (NEVER dynamic template resolution)
- Deterministic question sequencing (contiguous, no gaps, no duplicates)
- Race-safe exchange creation (Redis distributed locks)
- Progress monotonicity (sequence never regresses)
- Exchange creation requires active (in_progress) submission
"""

# Coordinator
from app.interview.orchestration.exchange_coordinator import ExchangeCoordinator

# Question Sequencer (pure domain)
from app.interview.orchestration.question_sequencer import (
    resolve_next_question,
    validate_template_snapshot,
    get_total_questions,
    get_section_for_sequence,
)

# Handlers
from app.interview.orchestration.audio_handler import AudioCompletionHandler
from app.interview.orchestration.coding_handler import CodingCompletionHandler

# Progress Tracking
from app.interview.orchestration.progress_tracker import ProgressTracker

# Race Resolution
from app.interview.orchestration.race_resolver import RaceResolver

# Contracts
from app.interview.orchestration.contracts import (
    NextQuestionResult,
    TemplateSnapshot,
    TemplateSectionSnapshot,
    ProgressUpdate,
    AudioCompletionSignal,
    CodeCompletionSignal,
    TextResponseSignal,
    ExchangeCompletionSignal,
    OrchestrationConfig,
)

# Errors
from app.interview.orchestration.errors import (
    TemplateSnapshotMissingError,
    TemplateSnapshotInvalidError,
    InterviewCompleteError,
    SequenceMismatchError,
    AudioNotReadyError,
    CodeNotReadyError,
)

__all__ = [
    # Coordinator
    "ExchangeCoordinator",
    # Question Sequencer
    "resolve_next_question",
    "validate_template_snapshot",
    "get_total_questions",
    "get_section_for_sequence",
    # Handlers
    "AudioCompletionHandler",
    "CodingCompletionHandler",
    # Progress
    "ProgressTracker",
    # Race Resolution
    "RaceResolver",
    # Contracts
    "NextQuestionResult",
    "TemplateSnapshot",
    "TemplateSectionSnapshot",
    "ProgressUpdate",
    "AudioCompletionSignal",
    "CodeCompletionSignal",
    "TextResponseSignal",
    "ExchangeCompletionSignal",
    "OrchestrationConfig",
    # Errors
    "TemplateSnapshotMissingError",
    "TemplateSnapshotInvalidError",
    "InterviewCompleteError",
    "SequenceMismatchError",
    "AudioNotReadyError",
    "CodeNotReadyError",
]
