"""
Intent Classification — Utterance Intent Taxonomy

Pure domain logic — no I/O, no framework dependencies.

Every candidate utterance is classified deterministically before business
logic runs. This ensures fair, auditable, and reproducible interviews.

Classification Rules:
- Default to ANSWER (conservative) if ambiguity between CLARIFICATION + ANSWER
- Temperature = 0 (deterministic, no randomness)
- Every classification logged immutably (audit trail)
- Classification runs FIRST before any evaluation logic
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Protocol


class UtteranceIntent(str, enum.Enum):
    """Strict taxonomy of candidate utterance intents."""

    ANSWER = "ANSWER"
    """Solution attempt (code logic, algorithm, direct response)."""

    CLARIFICATION = "CLARIFICATION"
    """Requesting clarification of question wording, terms, or constraints."""

    REPEAT = "REPEAT"
    """Asking for the question to be repeated."""

    POST_ANSWER = "POST_ANSWER"
    """Speech after answer submission (unsolicited, not scored)."""

    INVALID = "INVALID"
    """Unintelligible, silence, noise, off-topic rambling."""

    INCOMPLETE = "INCOMPLETE"
    """Fragment suggesting candidate will continue speaking."""

    UNKNOWN = "UNKNOWN"
    """Ambiguous — cannot determine intent with confidence."""


class SemanticLevel(str, enum.Enum):
    """Depth of semantic content in the utterance."""

    NONE = "none"
    """No meaningful content."""

    SURFACE = "surface"
    """Surface-level content (definitions, restatements)."""

    DEEP = "deep"
    """Deep content (algorithm steps, code logic, analysis)."""


@dataclass(frozen=True)
class UtteranceIntentClassification:
    """
    Immutable classification result for a candidate utterance.

    Attributes:
        intent: Classified intent category.
        confidence: 0.0–1.0 classification confidence.
        contains_solution_attempt: True if solution logic detected.
        semantic_level: Depth of utterance content.
        raw_transcript: Original transcript text (for audit).
        classifier_version: Version of the classifier used (for reproducibility).
    """

    intent: UtteranceIntent
    confidence: float
    contains_solution_attempt: bool
    semantic_level: SemanticLevel
    raw_transcript: Optional[str] = None
    classifier_version: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate confidence range."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    def to_audit_dict(self) -> dict:
        """Serialize for immutable audit logging (intent_sequence JSONB)."""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "contains_solution_attempt": self.contains_solution_attempt,
            "semantic_level": self.semantic_level.value,
        }


@dataclass
class InterviewContext:
    """
    Context provided to the classifier for more accurate classification.

    Includes information about the current question and exchange state.
    """

    question_text: str
    question_type: str
    exchange_state: str
    clarification_count: int = 0
    previous_intents: list = field(default_factory=list)


class UtteranceIntentClassifier(Protocol):
    """
    Protocol for utterance intent classifiers.

    Implementations must be:
    - Fast (<500ms)
    - Deterministic (temperature=0 or equivalent)
    - Auditable (every classification logged)

    This is a Protocol (structural subtyping) — implementations do NOT need
    to inherit from this class.
    """

    def classify(
        self,
        transcript: str,
        context: InterviewContext,
    ) -> UtteranceIntentClassification:
        """
        Classify utterance intent.

        Args:
            transcript: Raw transcript text from ASR.
            context: Interview context for classification.

        Returns:
            Immutable classification result.

        Raises:
            ClassificationError: If classification fails.
        """
        ...


class RuleBasedIntentClassifier:
    """
    Lightweight rule-based intent classifier.

    Provides deterministic classification using keyword matching and
    heuristics. Suitable for fallback or low-latency scenarios.

    For production use with LLM-based classification, implement the
    ``UtteranceIntentClassifier`` protocol with an AI provider.
    """

    VERSION = "rule-based-v1"

    # Keywords indicating clarification intent
    _CLARIFICATION_KEYWORDS = frozenset({
        "what do you mean",
        "can you explain",
        "can you clarify",
        "what does",
        "could you define",
        "rephrase",
        "i don't understand",
        "not sure what",
        "can you elaborate",
    })

    # Keywords indicating repeat intent
    _REPEAT_KEYWORDS = frozenset({
        "repeat",
        "say that again",
        "can you say",
        "one more time",
        "didn't catch",
        "come again",
        "pardon",
    })

    # Keywords indicating answer intent (solution logic)
    _ANSWER_KEYWORDS = frozenset({
        "i would use",
        "my approach",
        "we can implement",
        "the solution is",
        "i think we should",
        "first we",
        "the algorithm",
        "the time complexity",
        "the space complexity",
        "i would start",
        "let me think",
        "so the idea is",
    })

    def classify(
        self,
        transcript: str,
        context: InterviewContext,
    ) -> UtteranceIntentClassification:
        """Classify utterance using rule-based heuristics."""
        if not transcript or not transcript.strip():
            return UtteranceIntentClassification(
                intent=UtteranceIntent.INVALID,
                confidence=0.95,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.NONE,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        lower = transcript.lower().strip()

        # Check if in post-answer state
        if context.exchange_state == "POST_ANSWER_WINDOW":
            return UtteranceIntentClassification(
                intent=UtteranceIntent.POST_ANSWER,
                confidence=0.99,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.NONE,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        # Check for answer keywords FIRST (conservative: answer > clarification)
        has_answer = any(kw in lower for kw in self._ANSWER_KEYWORDS)
        has_clarification = any(kw in lower for kw in self._CLARIFICATION_KEYWORDS)

        if has_answer:
            # Rule: If ambiguity between CLARIFICATION + ANSWER → ANSWER
            return UtteranceIntentClassification(
                intent=UtteranceIntent.ANSWER,
                confidence=0.85 if has_clarification else 0.90,
                contains_solution_attempt=True,
                semantic_level=SemanticLevel.DEEP,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        if has_clarification:
            return UtteranceIntentClassification(
                intent=UtteranceIntent.CLARIFICATION,
                confidence=0.90,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.SURFACE,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        # Check for repeat
        if any(kw in lower for kw in self._REPEAT_KEYWORDS):
            return UtteranceIntentClassification(
                intent=UtteranceIntent.REPEAT,
                confidence=0.92,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.NONE,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        # Check for incomplete fragment
        if len(lower.split()) < 5 and lower.endswith("..."):
            return UtteranceIntentClassification(
                intent=UtteranceIntent.INCOMPLETE,
                confidence=0.75,
                contains_solution_attempt=False,
                semantic_level=SemanticLevel.SURFACE,
                raw_transcript=transcript,
                classifier_version=self.VERSION,
            )

        # Default: treat as ANSWER (conservative rule)
        return UtteranceIntentClassification(
            intent=UtteranceIntent.ANSWER,
            confidence=0.60,
            contains_solution_attempt=False,
            semantic_level=SemanticLevel.SURFACE,
            raw_transcript=transcript,
            classifier_version=self.VERSION,
        )
