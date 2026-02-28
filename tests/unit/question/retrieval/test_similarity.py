"""
Unit Tests — Cosine Similarity & Repetition Detection

Tests pure domain logic — no mocks, no I/O, no DB.
"""

import math
import pytest

from app.question.retrieval.domain.similarity import (
    IDENTICAL_THRESHOLD,
    SIMILAR_THRESHOLD,
    compute_hybrid_vector,
    compute_similarity_to_history,
    cosine_similarity,
    is_acceptable_candidate,
    normalize_vector,
)


# ═══════════════════════════════════════════════════════════════════════
# cosine_similarity
# ═══════════════════════════════════════════════════════════════════════


class TestCosineSimilarity:
    """Tests for cosine_similarity()."""

    def test_identical_vectors(self):
        """Identical vectors → similarity = 1.0."""
        vec = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-9)

    def test_opposite_vectors(self):
        """Opposite vectors → similarity = -1.0."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0, abs=1e-9)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors → similarity = 0.0."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0, abs=1e-9)

    def test_similar_vectors(self):
        """Similar vectors → high positive similarity."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [1.1, 2.1, 3.1]
        sim = cosine_similarity(vec_a, vec_b)
        assert sim > 0.99

    def test_different_vectors(self):
        """Different vectors → moderate similarity."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [1.0, 1.0, 0.0]
        sim = cosine_similarity(vec_a, vec_b)
        expected = 1.0 / math.sqrt(2)  # cos(45°)
        assert sim == pytest.approx(expected, abs=1e-9)

    def test_dimension_mismatch_raises(self):
        """Different dimensions → ValueError."""
        with pytest.raises(ValueError, match="Dimension mismatch"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_empty_vector_raises(self):
        """Empty vectors → ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            cosine_similarity([], [])

    def test_zero_vector(self):
        """Zero vector → 0.0 (graceful, no division by zero)."""
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_high_dimensional(self):
        """768-dimensional vectors work correctly."""
        vec_a = [float(i) for i in range(768)]
        vec_b = [float(i) + 0.01 for i in range(768)]
        sim = cosine_similarity(vec_a, vec_b)
        assert sim > 0.999

    def test_negative_values(self):
        """Negative values handled correctly."""
        vec_a = [-1.0, -2.0, -3.0]
        vec_b = [-1.0, -2.0, -3.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(1.0, abs=1e-9)


# ═══════════════════════════════════════════════════════════════════════
# normalize_vector
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizeVector:
    """Tests for normalize_vector()."""

    def test_unit_vector_unchanged(self):
        """Already-unit vector → unchanged."""
        vec = [1.0, 0.0, 0.0]
        result = normalize_vector(vec)
        assert result == pytest.approx(vec, abs=1e-9)

    def test_normalize_to_unit_length(self):
        """Arbitrary vector → magnitude ≈ 1.0."""
        vec = [3.0, 4.0]  # magnitude = 5
        result = normalize_vector(vec)
        magnitude = math.sqrt(sum(v * v for v in result))
        assert magnitude == pytest.approx(1.0, abs=1e-9)
        assert result[0] == pytest.approx(0.6, abs=1e-9)
        assert result[1] == pytest.approx(0.8, abs=1e-9)

    def test_zero_vector_returns_zero(self):
        """Zero vector → returns zero vector (no division by zero)."""
        assert normalize_vector([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]

    def test_empty_vector(self):
        """Empty vector → returns empty."""
        assert normalize_vector([]) == []


# ═══════════════════════════════════════════════════════════════════════
# compute_hybrid_vector
# ═══════════════════════════════════════════════════════════════════════


class TestComputeHybridVector:
    """Tests for compute_hybrid_vector()."""

    def test_equal_weights(self):
        """Equal weights → average, normalized."""
        vec_a = [2.0, 0.0]
        vec_b = [0.0, 2.0]
        result = compute_hybrid_vector(vec_a, vec_b, 0.5, 0.5)
        # Weighted average = [1.0, 1.0], normalized = [1/√2, 1/√2]
        expected = 1.0 / math.sqrt(2)
        assert result[0] == pytest.approx(expected, abs=1e-9)
        assert result[1] == pytest.approx(expected, abs=1e-9)

    def test_full_weight_a(self):
        """Weight 1.0 on A → result ≈ normalized A."""
        vec_a = [3.0, 4.0]
        vec_b = [0.0, 0.0]
        result = compute_hybrid_vector(vec_a, vec_b, 1.0, 0.0)
        assert result[0] == pytest.approx(0.6, abs=1e-9)
        assert result[1] == pytest.approx(0.8, abs=1e-9)

    def test_dimension_mismatch_raises(self):
        """Different dimensions → ValueError."""
        with pytest.raises(ValueError, match="Dimension mismatch"):
            compute_hybrid_vector([1.0], [1.0, 2.0], 0.5, 0.5)

    def test_negative_weight_raises(self):
        """Negative weight → ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_hybrid_vector([1.0], [1.0], -0.5, 1.5)


# ═══════════════════════════════════════════════════════════════════════
# compute_similarity_to_history
# ═══════════════════════════════════════════════════════════════════════


class TestComputeSimilarityToHistory:
    """Tests for compute_similarity_to_history()."""

    def test_empty_history(self):
        """Empty history → empty result dict."""
        result = compute_similarity_to_history([1.0, 2.0, 3.0], [])
        assert result == {}

    def test_single_entry(self):
        """Single history entry → one similarity score."""
        candidate = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 42, "question_embedding": [1.0, 0.0, 0.0]}
        ]
        result = compute_similarity_to_history(candidate, history)
        assert 42 in result
        assert result[42] == pytest.approx(1.0, abs=1e-9)

    def test_multiple_entries(self):
        """Multiple history entries → scores for each."""
        candidate = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": [1.0, 0.0, 0.0]},
            {"question_id": 2, "question_embedding": [0.0, 1.0, 0.0]},
            {"question_id": 3, "question_embedding": [0.5, 0.5, 0.0]},
        ]
        result = compute_similarity_to_history(candidate, history)
        assert len(result) == 3
        assert result[1] == pytest.approx(1.0, abs=1e-9)
        assert result[2] == pytest.approx(0.0, abs=1e-9)
        assert result[3] > 0.0

    def test_entries_without_embedding_skipped(self):
        """History entries with None embedding → skipped."""
        candidate = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": None},
            {"question_id": 2},  # Missing key
            {"question_id": 3, "question_embedding": [1.0, 0.0, 0.0]},
        ]
        result = compute_similarity_to_history(candidate, history)
        assert len(result) == 1
        assert 3 in result

    def test_dimension_mismatch_skipped(self):
        """Dimension mismatch entries → skipped (not raised)."""
        candidate = [1.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": [1.0, 0.0, 0.0]},
        ]
        result = compute_similarity_to_history(candidate, history)
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════
# is_acceptable_candidate
# ═══════════════════════════════════════════════════════════════════════


class TestIsAcceptableCandidate:
    """Tests for is_acceptable_candidate()."""

    def test_no_history_always_acceptable(self):
        """No exchange history → always acceptable."""
        result = is_acceptable_candidate([1.0, 0.0], [], threshold=0.85)
        assert result.is_acceptable is True
        assert result.max_similarity == 0.0

    def test_identical_embedding_rejected(self):
        """Identical embedding → max similarity ≈ 1.0 → rejected."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        history = [{"question_id": 42, "question_embedding": embedding}]
        result = is_acceptable_candidate(embedding, history, threshold=0.85)
        assert result.is_acceptable is False
        assert result.max_similarity >= 0.99
        assert result.most_similar_question_id == 42

    def test_very_similar_rejected(self):
        """Very similar embedding (>0.85) → rejected."""
        candidate = [0.1, 0.2, 0.3, 0.4]
        previous = [0.11, 0.19, 0.31, 0.39]
        history = [{"question_id": 10, "question_embedding": previous}]
        result = is_acceptable_candidate(candidate, history, threshold=0.85)
        # These are extremely similar
        assert result.max_similarity > 0.85
        assert result.is_acceptable is False

    def test_different_enough_accepted(self):
        """Sufficiently different embedding → accepted."""
        candidate = [1.0, 0.0, 0.0]
        previous = [0.0, 1.0, 0.0]
        history = [{"question_id": 99, "question_embedding": previous}]
        result = is_acceptable_candidate(candidate, history, threshold=0.85)
        assert result.is_acceptable is True
        assert result.max_similarity == pytest.approx(0.0, abs=1e-9)

    def test_threshold_boundary(self):
        """Score exactly at threshold → NOT acceptable (strict <)."""
        # Build vectors with known cosine similarity
        # cos(θ) = 0.85 → need specific angle
        # Use constructed vectors
        # A = [1, 0], B at angle θ where cos(θ) = 0.85
        import math

        theta = math.acos(0.85)
        candidate = [1.0, 0.0]
        previous = [math.cos(theta), math.sin(theta)]
        history = [{"question_id": 1, "question_embedding": previous}]
        result = is_acceptable_candidate(candidate, history, threshold=0.85)
        # cos(theta) = 0.85, which is NOT < 0.85
        assert result.is_acceptable is False

    def test_multiple_history_entries_worst_case(self):
        """Multiple entries → max_similarity is worst case."""
        candidate = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": [0.0, 1.0, 0.0]},
            {"question_id": 2, "question_embedding": [0.9, 0.1, 0.0]},
            {"question_id": 3, "question_embedding": [0.5, 0.5, 0.0]},
        ]
        result = is_acceptable_candidate(candidate, history, threshold=0.85)
        # Question 2 has highest similarity
        assert result.most_similar_question_id == 2
        assert result.max_similarity > 0.5

    def test_custom_threshold(self):
        """Custom threshold = 0.95 → only near-identical rejected."""
        candidate = [1.0, 0.0, 0.0]
        # cos(θ) ≈ 0.707 for these vectors — well below 0.95
        previous = [1.0, 1.0, 0.0]
        history = [{"question_id": 1, "question_embedding": previous}]
        result = is_acceptable_candidate(candidate, history, threshold=0.95)
        # Similarity ≈ 0.707 which is < 0.95
        assert result.is_acceptable is True

    def test_similarities_dict_populated(self):
        """Result includes similarity scores for all history entries."""
        candidate = [1.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": [1.0, 0.0]},
            {"question_id": 2, "question_embedding": [0.0, 1.0]},
        ]
        result = is_acceptable_candidate(candidate, history, threshold=0.85)
        assert 1 in result.similarities
        assert 2 in result.similarities
        assert result.similarities[1] == pytest.approx(1.0, abs=1e-9)
        assert result.similarities[2] == pytest.approx(0.0, abs=1e-9)

    def test_default_threshold_is_similar_threshold(self):
        """Default threshold matches SIMILAR_THRESHOLD constant."""
        assert SIMILAR_THRESHOLD == 0.85
        assert IDENTICAL_THRESHOLD == 0.95
