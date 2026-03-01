"""
Post-Generation Validation

Pure domain logic — no I/O, no framework imports.
Validates LLM output against the generation request constraints.

Reuses similarity computation from retrieval module
(import at function level to avoid circular imports).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.question.generation.domain.entities import (
    GeneratedQuestionOutput,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Individual checks
# ════════════════════════════════════════════════════════════════════════════

_VAGUE_PATTERNS = frozenset(
    {"something", "anything", "whatever", "stuff", "things"}
)

_MIN_QUESTION_LENGTH = 20
_MIN_ANSWER_LENGTH = 10


def check_difficulty_match(
    generated_difficulty: str,
    requested_difficulty: str,
) -> bool:
    """Return True when difficulties match (case-insensitive)."""
    return generated_difficulty.strip().lower() == requested_difficulty.strip().lower()


def check_topic_allowed(
    generated_topic: str,
    allowed_topics: List[str],
) -> bool:
    """
    Return True when the generated topic is in the allowed set.

    If allowed_topics is empty the check is skipped (permissive).
    """
    if not allowed_topics:
        return True
    gen_lower = generated_topic.strip().lower()
    return any(gen_lower == t.strip().lower() for t in allowed_topics)


def check_not_empty(
    question_text: str,
    expected_answer: str,
) -> tuple[bool, str]:
    """
    Reject vague / too-short questions.

    Returns (is_valid, reason).
    """
    if len(question_text.strip()) < _MIN_QUESTION_LENGTH:
        return False, f"question_text too short (<{_MIN_QUESTION_LENGTH} chars)"

    if len(expected_answer.strip()) < _MIN_ANSWER_LENGTH:
        return False, f"expected_answer too short (<{_MIN_ANSWER_LENGTH} chars)"

    question_lower = question_text.lower()
    for vague in _VAGUE_PATTERNS:
        if vague in question_lower.split():
            return False, f"question_text contains vague term '{vague}'"

    return True, ""


def check_semantic_similarity(
    question_text: str,
    previous_question_embeddings: List[List[float]],
    new_embedding: Optional[List[float]],
    threshold: float = 0.85,
) -> tuple[bool, float]:
    """
    Return (is_acceptable, max_similarity).

    Delegates cosine similarity to the retrieval domain layer.
    If new_embedding is None (embedding service unavailable),
    the check is skipped with a warning.
    """
    if new_embedding is None or not previous_question_embeddings:
        return True, 0.0

    from app.question.retrieval.domain.similarity import cosine_similarity

    max_sim = 0.0
    for prev_emb in previous_question_embeddings:
        sim = cosine_similarity(new_embedding, prev_emb)
        if sim > max_sim:
            max_sim = sim

    return max_sim < threshold, max_sim


# ════════════════════════════════════════════════════════════════════════════
# Combined validation
# ════════════════════════════════════════════════════════════════════════════


def validate_generated_question(
    output: GeneratedQuestionOutput,
    requested_difficulty: str,
    allowed_topics: List[str],
    previous_question_embeddings: List[List[float]],
    new_embedding: Optional[List[float]] = None,
    similarity_threshold: float = 0.85,
) -> ValidationResult:
    """
    Run all post-generation validation checks.

    Returns a ValidationResult aggregating all individual outcomes.
    """
    failures: List[str] = []

    # 1. Difficulty match
    difficulty_ok = check_difficulty_match(output.difficulty, requested_difficulty)
    if not difficulty_ok:
        failures.append(
            f"difficulty_mismatch (got {output.difficulty}, expected {requested_difficulty})"
        )

    # 2. Topic check
    topic_ok = check_topic_allowed(output.topic, allowed_topics)
    if not topic_ok:
        failures.append(f"topic_not_allowed (got {output.topic})")

    # 3. Substance / not-empty
    not_empty, empty_reason = check_not_empty(
        output.question_text, output.expected_answer
    )
    if not not_empty:
        failures.append(f"empty_or_vague ({empty_reason})")

    # 4. Similarity
    is_acceptable, max_similarity = check_semantic_similarity(
        output.question_text,
        previous_question_embeddings,
        new_embedding,
        similarity_threshold,
    )
    if not is_acceptable:
        failures.append(f"too_similar (similarity={max_similarity:.2f})")

    return ValidationResult(
        passed=len(failures) == 0,
        failures=failures,
        similarity_score=max_similarity,
        difficulty_match=difficulty_ok,
        topic_allowed=topic_ok,
        not_empty=not_empty,
    )
