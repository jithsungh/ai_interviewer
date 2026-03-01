"""
Intent Classifier

Lightweight, deterministic intent classifier for candidate utterances.
Classifies intent BEFORE any other business logic runs.

Algorithm (from REQUIREMENTS.md §5a):
  0. If previous_submissions >= 1 → POST_ANSWER
  1. Check ASR confidence (if too low → INVALID with warning)
  2. Check for silence/empty → INVALID
  3. Check for solution keywords → ANSWER
  4. Check for clarification keywords → CLARIFICATION
  5. Check for repeat request → REPEAT
  6. Otherwise → UNKNOWN (conservative)

Invariants enforced:
  - Deterministic: temperature=0, no randomness
  - Runs FIRST before any business logic
  - Same input → same output
  - Keyword-based (no LLM calls)

Does NOT:
  - Call any external service
  - Write to any database
  - Use any randomness
"""

from __future__ import annotations

from typing import FrozenSet

from app.shared.observability import get_context_logger

from .contracts import IntentClassificationRequest, IntentClassificationResult

logger = get_context_logger(__name__)


# ---------------------------------------------------------------------------
# Keyword sets (frozen for thread safety and immutability)
# ---------------------------------------------------------------------------

SOLUTION_KEYWORDS: FrozenSet[str] = frozenset({
    "algorithm", "approach", "logic", "code", "loop", "recursion",
    "if", "condition", "variable", "array", "queue", "stack",
    "would", "use", "implement", "call", "pass", "filter",
    "sort", "search", "traverse", "hash", "map", "list",
    "function", "method", "class", "return", "iterate",
})

CLARIFICATION_KEYWORDS: FrozenSet[str] = frozenset({
    "what", "mean", "define", "clarify", "understand", "explain",
    "rephrase", "unclear", "specify",
})

REPEAT_PHRASES: tuple = (
    "again",
    "repeat",
    "say that",
    "one more time",
    "come again",
    "didn't hear",
    "didn't catch",
)

SILENCE_TOKENS: FrozenSet[str] = frozenset({
    "", "um", "uh", "umm", "uhh", "hmm", "hhh",
})


class IntentClassifier:
    """
    Lightweight, keyword-based intent classifier.

    Deterministic: temperature=0 equivalent (no randomness).

    Parameters
    ----------
    asr_confidence_threshold : float
        ASR confidence below this triggers INVALID (default: 0.70).
    intent_confidence_threshold : float
        Minimum confidence for non-UNKNOWN classification (default: 0.75).
    """

    # Class-level thresholds (overridable via constructor)
    ASR_CONFIDENCE_THRESHOLD: float = 0.70
    INTENT_CONFIDENCE_THRESHOLD: float = 0.75

    def __init__(
        self,
        asr_confidence_threshold: float = 0.70,
        intent_confidence_threshold: float = 0.75,
    ) -> None:
        self.ASR_CONFIDENCE_THRESHOLD = asr_confidence_threshold
        self.INTENT_CONFIDENCE_THRESHOLD = intent_confidence_threshold

        logger.info(
            "IntentClassifier initialised",
            event_type="audio.analysis.intent.init",
            metadata={
                "asr_confidence_threshold": asr_confidence_threshold,
                "intent_confidence_threshold": intent_confidence_threshold,
            },
        )

    def classify(self, request: IntentClassificationRequest) -> IntentClassificationResult:
        """
        Classify candidate utterance intent deterministically.

        Parameters
        ----------
        request : IntentClassificationRequest
            Frozen request with transcript, ASR confidence, and context.

        Returns
        -------
        IntentClassificationResult
            Frozen, deterministic classification result.
        """
        # Step 0: Post-answer check (immutability)
        if request.previous_submissions >= 1:
            return IntentClassificationResult(
                intent="POST_ANSWER",
                confidence=0.95,
                contains_solution_attempt=False,
                semantic_depth="none",
                low_asr_confidence_warning=False,
            )

        # Step 1: ASR confidence check
        if request.confidence_score < self.ASR_CONFIDENCE_THRESHOLD:
            return IntentClassificationResult(
                intent="INVALID",
                confidence=0.80,
                contains_solution_attempt=False,
                semantic_depth="none",
                low_asr_confidence_warning=True,
            )

        # Step 2: Empty / silence check
        transcript = request.transcript.strip()
        if not transcript or self._is_silence(transcript):
            return IntentClassificationResult(
                intent="INVALID",
                confidence=0.95,
                contains_solution_attempt=False,
                semantic_depth="none",
                low_asr_confidence_warning=False,
            )

        # Step 3: Solution detection
        if self._has_solution_keywords(transcript):
            return IntentClassificationResult(
                intent="ANSWER",
                confidence=0.90,
                contains_solution_attempt=True,
                semantic_depth="deep",
                low_asr_confidence_warning=False,
            )

        # Step 4: Clarification detection
        if self._has_clarification_keywords(transcript):
            return IntentClassificationResult(
                intent="CLARIFICATION",
                confidence=0.85,
                contains_solution_attempt=False,
                semantic_depth="surface",
                low_asr_confidence_warning=False,
            )

        # Step 5: Repeat detection
        if self._is_repeat_request(transcript):
            return IntentClassificationResult(
                intent="REPEAT",
                confidence=0.88,
                contains_solution_attempt=False,
                semantic_depth="none",
                low_asr_confidence_warning=False,
            )

        # Step 6: Ambiguous → conservative UNKNOWN
        return IntentClassificationResult(
            intent="UNKNOWN",
            confidence=0.60,
            contains_solution_attempt=False,
            semantic_depth="surface",
            low_asr_confidence_warning=False,
        )

    # ------------------------------------------------------------------
    # Keyword matching helpers
    # ------------------------------------------------------------------

    def _has_solution_keywords(self, transcript: str) -> bool:
        """Check if transcript contains solution keywords."""
        tokens = set(transcript.lower().split())
        return bool(tokens & SOLUTION_KEYWORDS)

    def _has_clarification_keywords(self, transcript: str) -> bool:
        """Check if transcript contains clarification keywords."""
        tokens = set(transcript.lower().split())
        return bool(tokens & CLARIFICATION_KEYWORDS)

    def _is_repeat_request(self, transcript: str) -> bool:
        """Check if candidate is asking for repetition."""
        lower = transcript.lower()
        return any(phrase in lower for phrase in REPEAT_PHRASES)

    def _is_silence(self, transcript: str) -> bool:
        """Check if transcript represents silence or noise only."""
        lower = transcript.lower().strip()

        # ASR silence markers
        if "[silence]" in lower or "[noise]" in lower:
            return True

        # Filler-only utterance
        return lower in SILENCE_TOKENS
