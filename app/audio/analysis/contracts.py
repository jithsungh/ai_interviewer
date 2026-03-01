"""
Audio Analysis Domain Contracts

Frozen dataclass models exchanged by the analysis module.
No business logic — structure and type validation only.

Follows the same pattern as ``audio.ingestion.contracts``
and ``audio.transcription.contracts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SpeechState(str, Enum):
    """Classification of sentence completeness state."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONTINUING = "continuing"


class IntentType(str, Enum):
    """Primary classification of candidate utterance intent."""

    ANSWER = "ANSWER"
    CLARIFICATION = "CLARIFICATION"
    REPEAT = "REPEAT"
    POST_ANSWER = "POST_ANSWER"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


class SemanticDepth(str, Enum):
    """Content complexity classification."""

    NONE = "none"
    SURFACE = "surface"
    DEEP = "deep"


class ConfidenceLevel(str, Enum):
    """Sentiment confidence level."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Input Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletenessRequest:
    """
    Request to classify sentence completeness.

    Frozen (immutable) after creation.
    """

    transcript: str
    segments: tuple = ()

    def __post_init__(self) -> None:
        if self.transcript is None:
            raise ValueError("transcript must not be None")


@dataclass(frozen=True)
class FillerDetectionRequest:
    """
    Request to detect filler words in transcript.

    Frozen (immutable) after creation.
    """

    transcript: str
    context_aware: bool = True

    def __post_init__(self) -> None:
        if self.transcript is None:
            raise ValueError("transcript must not be None")


@dataclass(frozen=True)
class SpeechRateRequest:
    """
    Request to calculate speech rate from transcript and segments.

    Frozen (immutable) after creation.
    """

    transcript: str
    segments: tuple = ()
    exclude_pauses: bool = True

    def __post_init__(self) -> None:
        if self.transcript is None:
            raise ValueError("transcript must not be None")


@dataclass(frozen=True)
class SentimentRequest:
    """
    Request to analyse sentiment of a transcript.

    Frozen (immutable) after creation.
    """

    transcript: str
    audio_features: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.transcript is None:
            raise ValueError("transcript must not be None")


@dataclass(frozen=True)
class IntentClassificationRequest:
    """
    Request to classify candidate utterance intent.

    Frozen (immutable) after creation.
    """

    transcript: str
    confidence_score: float
    previous_submissions: int = 0
    question_context: Optional[str] = None

    def __post_init__(self) -> None:
        if self.transcript is None:
            raise ValueError("transcript must not be None")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        if self.previous_submissions < 0:
            raise ValueError("previous_submissions must be >= 0")


# ---------------------------------------------------------------------------
# Output Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletenessResult:
    """
    Immutable result of sentence completeness classification.

    speech_state: "complete" | "incomplete" | "continuing"
    sentence_complete: Grammatically complete sentence
    confidence: 0.0–1.0 classification confidence
    """

    speech_state: str
    sentence_complete: bool
    confidence: float
    incomplete_reason: Optional[str] = None
    linguistic_features: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.speech_state not in ("complete", "incomplete", "continuing"):
            raise ValueError(
                f"speech_state must be 'complete', 'incomplete', or 'continuing', got '{self.speech_state}'"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class FillerWord:
    """Single detected filler word with position information."""

    word: str
    position: int
    timestamp_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.word:
            raise ValueError("word must not be empty")
        if self.position < 0:
            raise ValueError("position must be >= 0")


@dataclass(frozen=True)
class FillerDetectionResult:
    """
    Immutable result of filler word detection.

    filler_rate is fillers / total words (0.0–1.0).
    """

    filler_word_count: int
    filler_rate: float
    filler_positions: tuple = ()

    def __post_init__(self) -> None:
        if self.filler_word_count < 0:
            raise ValueError("filler_word_count must be >= 0")
        if not (0.0 <= self.filler_rate <= 1.0):
            raise ValueError("filler_rate must be between 0.0 and 1.0")


@dataclass(frozen=True)
class SpeechRateResult:
    """
    Immutable result of speech rate analysis.

    speech_rate_wpm: Words per minute (excluding pauses if configured).
    """

    speech_rate_wpm: float
    total_words: int
    speech_duration_ms: int
    total_duration_ms: int
    long_pause_count: int
    longest_pause_ms: int

    def __post_init__(self) -> None:
        if self.speech_rate_wpm < 0:
            raise ValueError("speech_rate_wpm must be >= 0")
        if self.total_words < 0:
            raise ValueError("total_words must be >= 0")
        if self.speech_duration_ms < 0:
            raise ValueError("speech_duration_ms must be >= 0")
        if self.total_duration_ms < 0:
            raise ValueError("total_duration_ms must be >= 0")


@dataclass(frozen=True)
class SentimentResult:
    """
    Immutable result of sentiment analysis.

    sentiment_score: -1.0 (negative) to +1.0 (positive).
    """

    sentiment_score: float
    confidence_level: str
    hesitation_detected: bool
    frustration_detected: bool

    def __post_init__(self) -> None:
        if not (-1.0 <= self.sentiment_score <= 1.0):
            raise ValueError("sentiment_score must be between -1.0 and 1.0")
        if self.confidence_level not in ("high", "medium", "low"):
            raise ValueError(
                f"confidence_level must be 'high', 'medium', or 'low', got '{self.confidence_level}'"
            )


@dataclass(frozen=True)
class IntentClassificationResult:
    """
    Immutable result of intent classification.

    Deterministic: same input always produces the same output.
    """

    intent: str
    confidence: float
    contains_solution_attempt: bool
    semantic_depth: str
    low_asr_confidence_warning: bool

    def __post_init__(self) -> None:
        valid_intents = {
            "ANSWER",
            "CLARIFICATION",
            "REPEAT",
            "POST_ANSWER",
            "INVALID",
            "INCOMPLETE",
            "UNKNOWN",
        }
        if self.intent not in valid_intents:
            raise ValueError(f"intent must be one of {valid_intents}, got '{self.intent}'")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.semantic_depth not in ("none", "surface", "deep"):
            raise ValueError(
                f"semantic_depth must be 'none', 'surface', or 'deep', got '{self.semantic_depth}'"
            )
