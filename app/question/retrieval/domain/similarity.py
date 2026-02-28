"""
Cosine Similarity & Repetition Detection

Pure computation — no I/O, no DB calls, no external dependencies.

Formulas:
    cosine_similarity(A, B) = (A · B) / (||A|| × ||B||)
    Range: [-1, 1]  — higher = more similar

Thresholds (from REQUIREMENTS):
    identical_threshold  = 0.95  (essentially same question → reject)
    similar_threshold    = 0.85  (too similar for candidate experience → reject)
    acceptable_threshold < 0.85  (different enough → accept)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.question.retrieval.contracts import SimilarityCheckResult

# ════════════════════════════════════════════════════════════════════════════
# Default thresholds
# ════════════════════════════════════════════════════════════════════════════

IDENTICAL_THRESHOLD: float = 0.95
SIMILAR_THRESHOLD: float = 0.85


# ════════════════════════════════════════════════════════════════════════════
# Vector operations
# ════════════════════════════════════════════════════════════════════════════


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity in range [-1, 1].

    Raises:
        ValueError: If vectors have different dimensions or are empty.
    """
    if not vec_a or not vec_b:
        raise ValueError("Vectors must not be empty")

    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Dimension mismatch: vec_a has {len(vec_a)}, "
            f"vec_b has {len(vec_b)}"
        )

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def normalize_vector(vec: List[float]) -> List[float]:
    """
    L2-normalize a vector to unit length.

    Args:
        vec: Input vector.

    Returns:
        Unit vector (same direction, magnitude = 1).
        Returns zero vector if input magnitude is zero.
    """
    if not vec:
        return vec

    magnitude = math.sqrt(sum(v * v for v in vec))
    if magnitude == 0.0:
        return vec

    return [v / magnitude for v in vec]


def compute_hybrid_vector(
    vec_a: List[float],
    vec_b: List[float],
    weight_a: float = 0.5,
    weight_b: float = 0.5,
) -> List[float]:
    """
    Compute weighted average of two vectors, then L2-normalize.

    Used for hybrid resume + JD search.

    Args:
        vec_a: First vector (e.g. resume embedding).
        vec_b: Second vector (e.g. JD embedding).
        weight_a: Weight for vec_a.
        weight_b: Weight for vec_b.

    Returns:
        Normalized hybrid vector.

    Raises:
        ValueError: If vectors have different dimensions or weights are invalid.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Dimension mismatch: vec_a has {len(vec_a)}, "
            f"vec_b has {len(vec_b)}"
        )

    if weight_a < 0.0 or weight_b < 0.0:
        raise ValueError("Weights must be non-negative")

    hybrid = [weight_a * a + weight_b * b for a, b in zip(vec_a, vec_b)]
    return normalize_vector(hybrid)


# ════════════════════════════════════════════════════════════════════════════
# Repetition detection
# ════════════════════════════════════════════════════════════════════════════


def compute_similarity_to_history(
    candidate_embedding: List[float],
    history: List[Dict],
) -> Dict[int, float]:
    """
    Compute similarity between a candidate question embedding and all
    previously asked questions.

    Args:
        candidate_embedding: Embedding of the candidate question.
        history: List of dicts, each with at least:
            - "question_id": int
            - "question_embedding": List[float] (may be None/missing)

    Returns:
        {question_id: similarity_score} for all history entries
        that have an embedding.
    """
    similarities: Dict[int, float] = {}

    for entry in history:
        q_id = entry.get("question_id")
        prev_embedding = entry.get("question_embedding")

        if q_id is None or prev_embedding is None:
            continue

        if len(prev_embedding) == 0:
            continue

        try:
            score = cosine_similarity(candidate_embedding, prev_embedding)
            similarities[q_id] = score
        except ValueError:
            # Dimension mismatch — skip this entry
            continue

    return similarities


def is_acceptable_candidate(
    candidate_embedding: List[float],
    exchange_history: List[Dict],
    threshold: float = SIMILAR_THRESHOLD,
) -> SimilarityCheckResult:
    """
    Determine if a candidate question is sufficiently distinct from
    all previously asked questions.

    Args:
        candidate_embedding: Embedding of the candidate question.
        exchange_history: Previous exchanges with embeddings.
        threshold: Maximum acceptable similarity (default 0.85).

    Returns:
        SimilarityCheckResult with is_acceptable flag and details.
    """
    if not exchange_history:
        return SimilarityCheckResult(
            is_acceptable=True,
            max_similarity=0.0,
            most_similar_question_id=None,
            similarities={},
        )

    similarities = compute_similarity_to_history(
        candidate_embedding, exchange_history
    )

    if not similarities:
        return SimilarityCheckResult(
            is_acceptable=True,
            max_similarity=0.0,
            most_similar_question_id=None,
            similarities=similarities,
        )

    max_q_id = max(similarities, key=similarities.get)  # type: ignore[arg-type]
    max_sim = similarities[max_q_id]

    # Clamp to [-1.0, 1.0] to handle floating-point imprecision
    max_sim = max(-1.0, min(1.0, max_sim))

    return SimilarityCheckResult(
        is_acceptable=max_sim < threshold,
        max_similarity=max_sim,
        most_similar_question_id=max_q_id,
        similarities=similarities,
    )
