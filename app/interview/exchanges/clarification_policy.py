"""
Clarification Policy — Strict Bounds for Clarification Responses

Pure domain logic — no I/O, no framework dependencies.

Enforces:
- Max 3 clarifications per question
- Strict LLM prompt constraints (≤120 words, no hints, no algorithm suggestions)
- Fairness rules (same policy for all candidates)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ════════════════════════════════════════════════════════════════════════
# Prompt constraints (global policy)
# ════════════════════════════════════════════════════════════════════════

CLARIFICATION_PROMPT_CONSTRAINTS: Dict[str, Any] = {
    "MAX_WORDS": 120,
    "ALLOW_ANALOGY": True,
    "ANALOGY_COUNT": 1,  # Max 1 per question
    "ALLOW_HINT": False,  # False for fairness
    "HINT_COUNT": 0,  # If enabled, max 1 per question
    "PROHIBITIONS": [
        "algorithm_suggestions",
        "data_structure_suggestions",
        "step_sequencing",
        "partial_validation",
        "encouraging_phrases",
        "answer_description",
        "solution_examples",
    ],
    "OUTPUT_FORMAT": "natural_language",  # No JSON, no scoring
}


# ════════════════════════════════════════════════════════════════════════
# Data classes
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ClarificationRequest:
    """
    Input for clarification generation.

    Passed to the LLM (or other generator) to produce a policy-compliant
    clarification response.
    """

    original_question: str
    candidate_clarification_request: str
    clarification_count_so_far: int
    constraints: Dict[str, Any] = field(
        default_factory=lambda: CLARIFICATION_PROMPT_CONSTRAINTS.copy()
    )
    allow_hint: bool = False
    previous_clarifications: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClarificationResponse:
    """
    Output from clarification generation.

    Contains the response text and policy compliance metadata for audit.
    """

    clarification_text: str
    contains_hint: bool
    contains_analogy: bool
    violates_policy: bool
    word_count: int = 0

    def __post_init__(self) -> None:
        """Compute word count if not set."""
        if self.word_count == 0 and self.clarification_text:
            object.__setattr__(
                self, "word_count", len(self.clarification_text.split())
            )


@dataclass
class ClarificationAuditEntry:
    """
    Immutable audit record for a single clarification attempt.

    Stored in content_metadata.intent_sequence for the exchange.
    """

    clarification_number: int
    candidate_request: str
    response_text: str
    contains_hint: bool
    contains_analogy: bool
    violates_policy: bool
    word_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSONB storage."""
        return {
            "clarification_number": self.clarification_number,
            "candidate_request": self.candidate_request,
            "response_text": self.response_text,
            "contains_hint": self.contains_hint,
            "contains_analogy": self.contains_analogy,
            "violates_policy": self.violates_policy,
            "word_count": self.word_count,
        }


# ════════════════════════════════════════════════════════════════════════
# Policy
# ════════════════════════════════════════════════════════════════════════


class ClarificationPolicy:
    """
    Enforces clarification rules for a single question.

    Rules:
    1. Max 3 clarifications per question
    2. Response must be ≤120 words
    3. Max 1 analogy per question (if allowed)
    4. No hints by default (fairness)
    5. All prohibited content detected and flagged

    This is a stateful tracker for ONE question's clarification lifecycle.
    """

    MAX_CLARIFICATIONS = 3
    MAX_WORDS = CLARIFICATION_PROMPT_CONSTRAINTS["MAX_WORDS"]

    def __init__(self) -> None:
        self._clarification_count: int = 0
        self._analogy_given: bool = False
        self._hint_given: bool = False
        self._audit_log: List[ClarificationAuditEntry] = []

    @property
    def clarification_count(self) -> int:
        """Current clarification count."""
        return self._clarification_count

    @property
    def limit_exceeded(self) -> bool:
        """True if max clarifications reached."""
        return self._clarification_count >= self.MAX_CLARIFICATIONS

    @property
    def can_clarify(self) -> bool:
        """True if another clarification is allowed."""
        return self._clarification_count < self.MAX_CLARIFICATIONS

    @property
    def audit_log(self) -> List[ClarificationAuditEntry]:
        """Immutable view of clarification audit log."""
        return list(self._audit_log)

    def request_clarification(
        self,
        candidate_request: str,
    ) -> Optional[ClarificationRequest]:
        """
        Process a clarification request from the candidate.

        Returns:
            ClarificationRequest if allowed, None if limit exceeded.
        """
        if self.limit_exceeded:
            return None

        return ClarificationRequest(
            original_question="",  # Caller must fill this in
            candidate_clarification_request=candidate_request,
            clarification_count_so_far=self._clarification_count,
            allow_hint=False,
            previous_clarifications=[
                entry.response_text for entry in self._audit_log
            ],
        )

    def validate_response(self, response: ClarificationResponse) -> ClarificationResponse:
        """
        Validate and record a clarification response.

        Checks:
        1. Word count ≤ MAX_WORDS
        2. Analogy limit (max 1 per question)
        3. Hint policy (forbidden by default)

        Returns:
            The response with ``violates_policy`` updated if violations found.
        """
        violates = False

        # Check word count
        if response.word_count > self.MAX_WORDS:
            violates = True

        # Check analogy limit
        if response.contains_analogy and self._analogy_given:
            violates = True

        # Check hint policy
        if response.contains_hint and not CLARIFICATION_PROMPT_CONSTRAINTS.get(
            "ALLOW_HINT", False
        ):
            violates = True

        # Track state
        if response.contains_analogy:
            self._analogy_given = True
        if response.contains_hint:
            self._hint_given = True

        self._clarification_count += 1

        # Create audit entry
        audit_entry = ClarificationAuditEntry(
            clarification_number=self._clarification_count,
            candidate_request="",  # Caller should set this
            response_text=response.clarification_text,
            contains_hint=response.contains_hint,
            contains_analogy=response.contains_analogy,
            violates_policy=violates,
            word_count=response.word_count,
        )
        self._audit_log.append(audit_entry)

        if violates != response.violates_policy:
            # Return corrected response
            return ClarificationResponse(
                clarification_text=response.clarification_text,
                contains_hint=response.contains_hint,
                contains_analogy=response.contains_analogy,
                violates_policy=violates,
                word_count=response.word_count,
            )

        return response

    def to_audit_dict(self) -> Dict[str, Any]:
        """
        Serialize policy state for JSONB storage.

        Used in the exchange's content_metadata for audit trail.
        """
        return {
            "clarification_count": self._clarification_count,
            "clarification_limit_exceeded": self.limit_exceeded,
            "hint_given": self._hint_given,
            "analogy_given": self._analogy_given,
            "clarifications": [entry.to_dict() for entry in self._audit_log],
        }
