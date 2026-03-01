"""
Unit Tests — Repetition Prevention

Tests pure domain logic — no mocks, no I/O, no DB.

Covers:
  1. Exact match rejection
  2. Semantic similarity rejection
  3. Different enough accepted
  4. Zero history (first question)
  5. Missing embeddings (graceful degradation)
  6. Config toggles (disable exact/semantic checks)
"""

import math
import pytest

from app.question.selection.contracts import RepetitionConfig
from app.question.selection.domain.repetition import (
    check_repetition,
    filter_candidates_by_repetition,
    is_exact_match,
)


# ═══════════════════════════════════════════════════════════════════════
# is_exact_match
# ═══════════════════════════════════════════════════════════════════════


class TestIsExactMatch:
    """Tests for is_exact_match()."""

    def test_match_found(self):
        history = [
            {"question_id": 42, "question_text": "Q1"},
            {"question_id": 43, "question_text": "Q2"},
        ]
        assert is_exact_match(42, history) is True

    def test_no_match(self):
        history = [
            {"question_id": 42, "question_text": "Q1"},
        ]
        assert is_exact_match(99, history) is False

    def test_empty_history(self):
        assert is_exact_match(42, []) is False

    def test_none_candidate_id(self):
        """Generated questions have None ID → never exact match."""
        history = [{"question_id": 42}]
        assert is_exact_match(None, history) is False

    def test_none_ids_in_history(self):
        """History with None IDs → skip them."""
        history = [
            {"question_id": None, "question_text": "Generated Q"},
            {"question_id": 42, "question_text": "Q1"},
        ]
        assert is_exact_match(99, history) is False
        assert is_exact_match(42, history) is True


# ═══════════════════════════════════════════════════════════════════════
# check_repetition
# ═══════════════════════════════════════════════════════════════════════


class TestCheckRepetition:
    """Tests for check_repetition()."""

    @pytest.fixture
    def default_config(self) -> RepetitionConfig:
        return RepetitionConfig()

    def test_exact_match_rejected(self, default_config):
        """question_id already in history → (True, 1.0)."""
        history = [{"question_id": 42}]
        is_repeat, sim = check_repetition(42, None, history, default_config)
        assert is_repeat is True
        assert sim == 1.0

    def test_semantically_similar_rejected(self, default_config):
        """Similar embeddings (> 0.85 threshold) → rejected."""
        # Create nearly identical vectors
        vec_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        vec_b = [1.01, 2.01, 3.01, 4.01, 5.01]  # Very similar
        history = [
            {"question_id": 50, "question_embedding": vec_b}
        ]

        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=vec_a,
            exchange_history=history,
            config=default_config,
        )
        assert is_repeat is True
        assert sim > 0.85

    def test_different_enough_accepted(self, default_config):
        """Very different embeddings → accepted."""
        vec_a = [1.0, 0.0, 0.0, 0.0, 0.0]
        vec_b = [0.0, 0.0, 0.0, 0.0, 1.0]  # Orthogonal
        history = [
            {"question_id": 50, "question_embedding": vec_b}
        ]

        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=vec_a,
            exchange_history=history,
            config=default_config,
        )
        assert is_repeat is False
        assert sim < 0.85

    def test_empty_history_no_repetition(self, default_config):
        """No history → no repetition."""
        is_repeat, sim = check_repetition(
            candidate_question_id=42,
            candidate_embedding=[1.0, 2.0, 3.0],
            exchange_history=[],
            config=default_config,
        )
        assert is_repeat is False
        assert sim == 0.0

    def test_no_embedding_no_semantic_check(self, default_config):
        """No embedding provided → skip semantic, only exact match."""
        history = [{"question_id": 42, "question_embedding": [1.0, 2.0]}]
        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=None,
            exchange_history=history,
            config=default_config,
        )
        assert is_repeat is False
        assert sim == 0.0

    def test_history_without_embeddings(self, default_config):
        """History entries without embeddings → skip semantic."""
        history = [{"question_id": 42}]  # No question_embedding
        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=[1.0, 2.0, 3.0],
            exchange_history=history,
            config=default_config,
        )
        assert is_repeat is False
        assert sim == 0.0

    def test_exact_match_disabled(self):
        """Exact check disabled → don't reject on ID match."""
        config = RepetitionConfig(
            enable_exact_match_check=False,
            enable_semantic_check=False,
        )
        is_repeat, sim = check_repetition(42, None, [{"question_id": 42}], config)
        assert is_repeat is False

    def test_semantic_check_disabled(self):
        """Semantic check disabled → don't reject on similarity."""
        config = RepetitionConfig(enable_semantic_check=False)
        vec = [1.0, 2.0, 3.0]
        history = [{"question_id": 50, "question_embedding": vec}]

        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=vec,
            exchange_history=history,
            config=config,
        )
        assert is_repeat is False
        assert sim == 0.0

    def test_moderate_similarity_accepted(self, default_config):
        """Similarity in the 0.5-0.84 range → accepted."""
        vec_a = [1.0, 1.0, 0.0, 0.0]
        vec_b = [1.0, 0.0, 1.0, 0.0]  # cos(60°) ≈ 0.5
        history = [{"question_id": 50, "question_embedding": vec_b}]

        is_repeat, sim = check_repetition(
            candidate_question_id=99,
            candidate_embedding=vec_a,
            exchange_history=history,
            config=default_config,
        )
        assert is_repeat is False
        assert sim < 0.85


# ═══════════════════════════════════════════════════════════════════════
# filter_candidates_by_repetition
# ═══════════════════════════════════════════════════════════════════════


class TestFilterCandidatesByRepetition:
    """Tests for filter_candidates_by_repetition()."""

    def test_all_unique(self):
        """All candidates are unique → returned unmodified."""
        candidates = [
            {"question_id": 10, "embedding": None},
            {"question_id": 20, "embedding": None},
        ]
        history = [{"question_id": 99}]
        config = RepetitionConfig(enable_semantic_check=False)

        filtered = filter_candidates_by_repetition(candidates, history, config)
        assert len(filtered) == 2

    def test_exact_match_filtered(self):
        """Candidate with same ID as history → removed."""
        candidates = [
            {"question_id": 42, "embedding": None},
            {"question_id": 43, "embedding": None},
        ]
        history = [{"question_id": 42}]
        config = RepetitionConfig(enable_semantic_check=False)

        filtered = filter_candidates_by_repetition(candidates, history, config)
        assert len(filtered) == 1
        assert filtered[0]["question_id"] == 43

    def test_all_filtered_returns_empty(self):
        """All candidates are repeats → empty list."""
        candidates = [
            {"question_id": 42, "embedding": None},
        ]
        history = [{"question_id": 42}]
        config = RepetitionConfig(enable_semantic_check=False)

        filtered = filter_candidates_by_repetition(candidates, history, config)
        assert len(filtered) == 0

    def test_empty_candidates(self):
        """No candidates → empty list."""
        filtered = filter_candidates_by_repetition([], [], RepetitionConfig())
        assert len(filtered) == 0
