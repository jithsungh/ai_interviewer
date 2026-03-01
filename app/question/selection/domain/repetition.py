"""
Repetition Prevention

Delegates to app.question.retrieval.domain.similarity for cosine computation.
Adds exact-match checking and orchestrates both checks.

Pure domain logic — no I/O, no DB calls.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.question.retrieval.domain.similarity import (
    is_acceptable_candidate,
)
from app.question.retrieval.contracts import SimilarityCheckResult
from app.question.selection.contracts import RepetitionConfig

logger = logging.getLogger(__name__)


def is_exact_match(
    candidate_question_id: Optional[int],
    exchange_history: List[Dict],
) -> bool:
    """
    Check if candidate question was already asked (exact ID match).

    Args:
        candidate_question_id: ID of the candidate question.
        exchange_history: Previous exchanges.

    Returns:
        True if question_id appears in history.
    """
    if candidate_question_id is None:
        return False

    asked_ids = {
        e.get("question_id")
        for e in exchange_history
        if e.get("question_id") is not None
    }
    return candidate_question_id in asked_ids


def check_repetition(
    candidate_question_id: Optional[int],
    candidate_embedding: Optional[List[float]],
    exchange_history: List[Dict],
    config: RepetitionConfig,
) -> Tuple[bool, float]:
    """
    Check if candidate question is a repetition.

    Strategy:
      1. Exact match: question_id already in history → reject
      2. Semantic similarity > threshold → reject

    Args:
        candidate_question_id: Question ID (None for generated).
        candidate_embedding: Embedding vector (None if unavailable).
        exchange_history: Previous exchanges with question_embedding.
        config: Repetition configuration.

    Returns:
        Tuple of (is_repetition, max_similarity_score).
        max_similarity_score is 1.0 for exact match, else cosine sim.
    """
    # Step 1: Exact match check
    if config.enable_exact_match_check:
        if is_exact_match(candidate_question_id, exchange_history):
            return (True, 1.0)

    # Step 2: Semantic similarity check
    if config.enable_semantic_check and candidate_embedding is not None:
        # Filter history entries that have embeddings
        history_with_embeddings = [
            e for e in exchange_history
            if e.get("question_embedding") is not None
        ]

        if history_with_embeddings:
            result: SimilarityCheckResult = is_acceptable_candidate(
                candidate_embedding=candidate_embedding,
                exchange_history=history_with_embeddings,
                threshold=config.similarity_threshold_similar,
            )

            if not result.is_acceptable:
                return (True, result.max_similarity)

            return (False, result.max_similarity)

    return (False, 0.0)


def filter_candidates_by_repetition(
    candidates: List[Dict],
    exchange_history: List[Dict],
    config: RepetitionConfig,
) -> List[Dict]:
    """
    Filter out repetitive candidates from a candidate list.

    Args:
        candidates: List of candidate dicts with at least 'question_id'
                    and optionally 'embedding'.
        exchange_history: Previous exchanges.
        config: Repetition configuration.

    Returns:
        Filtered list of non-repetitive candidates.
    """
    unique_candidates = []

    for candidate in candidates:
        q_id = candidate.get("question_id")
        embedding = candidate.get("embedding")

        is_repeat, similarity = check_repetition(
            candidate_question_id=q_id,
            candidate_embedding=embedding,
            exchange_history=exchange_history,
            config=config,
        )

        if not is_repeat:
            unique_candidates.append(candidate)
        else:
            logger.info(
                "Rejected question %s (similarity: %.3f)",
                q_id,
                similarity,
            )

    return unique_candidates
