"""
Unit Tests — QuestionSelectionService

All external dependencies (retrieval, generation, adaptation repo) are MOCKED.
Tests orchestration logic: difficulty adaptation, candidate retrieval,
repetition filtering, fallback chains, adaptation logging.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.question.retrieval.contracts import (
    DifficultyLevel,
    QuestionCandidate,
    RetrievalResult,
    RetrievalStrategy,
    SearchCriteria,
)
from app.question.generation.contracts import (
    GenerationResult,
    GenerationStatus,
)
from app.question.selection.contracts import (
    AdaptationDecision,
    CandidateProfile,
    DifficultyAdaptationConfig,
    ExchangeHistoryEntry,
    FallbackType,
    QuestionSnapshot,
    RepetitionConfig,
    SectionConfig,
    SelectionContext,
    SelectionResult,
    SelectionStrategy,
)
from app.question.selection.domain.template_parser import (
    SectionCompleteError,
    TemplateSnapshotError,
)
from app.question.selection.service import (
    NoQuestionAvailableError,
    QuestionSelectionService,
)


# ═══════════════════════════════════════════════════════════════════════
# Factories
# ═══════════════════════════════════════════════════════════════════════


def _make_candidate(
    question_id: int = 1,
    score: float = 0.9,
    difficulty: str = "medium",
) -> QuestionCandidate:
    """Factory for test QuestionCandidates."""
    return QuestionCandidate(
        question_id=question_id,
        similarity_score=score,
        point_id=f"point-{question_id}",
        difficulty=difficulty,
        topic_id=10,
        scope="organization",
        metadata={"source_type": "question"},
    )


def _make_retrieval_result(
    candidates: Optional[List[QuestionCandidate]] = None,
) -> RetrievalResult:
    """Factory for test RetrievalResult."""
    cands = candidates if candidates is not None else [_make_candidate()]
    return RetrievalResult(
        candidates=cands,
        strategy_used=RetrievalStrategy.TOPIC_FILTER,
        total_found=len(cands),
        search_duration_ms=5.0,
    )


def _make_template_snapshot(
    section_name: str = "technical",
    question_count: int = 5,
    selection_strategy: str = "static_pool",
    question_type: str = "technical",
    difficulty_range: Optional[List[str]] = None,
    adaptation_enabled: bool = False,
) -> Dict[str, Any]:
    """Factory for test template snapshot."""
    diff_range = difficulty_range or ["medium"]
    snapshot: Dict[str, Any] = {
        "sections": [
            {
                "section_name": section_name,
                "question_count": question_count,
                "question_type": question_type,
                "selection_strategy": selection_strategy,
                "difficulty_range": diff_range,
            }
        ],
    }
    if adaptation_enabled:
        snapshot["difficulty_adaptation"] = {
            "enabled": True,
            "threshold_up": 80.0,
            "threshold_down": 50.0,
            "max_difficulty_jump": 1,
        }
    return snapshot


def _make_context(
    submission_id: int = 1,
    organization_id: int = 1,
    current_section: str = "technical",
    exchange_history: Optional[List[ExchangeHistoryEntry]] = None,
    exchange_sequence_order: int = 1,
    template_snapshot: Optional[Dict[str, Any]] = None,
    candidate_profile: Optional[CandidateProfile] = None,
) -> SelectionContext:
    """Factory for test SelectionContext."""
    return SelectionContext(
        submission_id=submission_id,
        organization_id=organization_id,
        template_snapshot=template_snapshot or _make_template_snapshot(),
        current_section=current_section,
        exchange_history=exchange_history or [],
        exchange_sequence_order=exchange_sequence_order,
        candidate_profile=candidate_profile,
    )


def _make_exchange(
    question_id: int = 1,
    difficulty: str = "medium",
    section_name: str = "technical",
    evaluation_score: Optional[float] = None,
    sequence_order: int = 1,
) -> ExchangeHistoryEntry:
    """Factory for test ExchangeHistoryEntry."""
    return ExchangeHistoryEntry(
        question_id=question_id,
        question_text=f"Test question {question_id}",
        difficulty=difficulty,
        section_name=section_name,
        evaluation_score=evaluation_score,
        sequence_order=sequence_order,
    )


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def mock_retrieval():
    """Mocked QdrantRetrievalService.

    Default candidate uses question_id=999 to avoid collisions with
    exchange history entries (which typically use id=1, 2, etc.).
    """
    svc = MagicMock()
    default_result = _make_retrieval_result(
        candidates=[_make_candidate(question_id=999)]
    )
    svc.search_semantic.return_value = default_result
    svc.search_by_topic.return_value = default_result
    svc.get_embedding_vector.return_value = None
    return svc


@pytest.fixture()
def mock_generation():
    """Mocked QuestionGenerationService."""
    svc = MagicMock()
    return svc


@pytest.fixture()
def mock_adaptation_repo():
    """Mocked AdaptationLogRepository."""
    repo = MagicMock()
    repo.log_decision.return_value = None
    return repo


@pytest.fixture()
def service(mock_retrieval, mock_generation, mock_adaptation_repo):
    """Service with all mocked dependencies."""
    return QuestionSelectionService(
        retrieval_service=mock_retrieval,
        generation_service=mock_generation,
        adaptation_repo=mock_adaptation_repo,
    )


@pytest.fixture()
def service_no_generation(mock_retrieval, mock_adaptation_repo):
    """Service with no generation service."""
    return QuestionSelectionService(
        retrieval_service=mock_retrieval,
        generation_service=None,
        adaptation_repo=mock_adaptation_repo,
    )


# ═══════════════════════════════════════════════════════════════════════
# Basic Selection (Happy Path)
# ═══════════════════════════════════════════════════════════════════════


class TestBasicSelection:
    """Tests for successful question selection without fallback."""

    def test_returns_selection_result(self, service, mock_retrieval):
        context = _make_context()
        result = service.select_next_question(context)

        assert isinstance(result, SelectionResult)
        assert result.question_snapshot is not None
        assert result.fallback_used is False

    def test_calls_retrieval_search(self, service, mock_retrieval):
        context = _make_context()
        service.select_next_question(context)

        mock_retrieval.search_by_topic.assert_called_once()

    def test_uses_semantic_search_when_embedding_present(
        self, service, mock_retrieval
    ):
        """With resume_embedding → semantic search."""
        profile = CandidateProfile(
            resume_embedding=[0.1] * 768
        )
        snapshot = _make_template_snapshot(
            selection_strategy="semantic_retrieval"
        )
        context = _make_context(
            template_snapshot=snapshot,
            candidate_profile=profile,
        )
        service.select_next_question(context)

        mock_retrieval.search_semantic.assert_called_once()

    def test_snapshot_has_question_id(self, service, mock_retrieval):
        context = _make_context()
        result = service.select_next_question(context)

        assert result.question_snapshot.question_id == 999

    def test_snapshot_has_placeholder_text(self, service, mock_retrieval):
        """Snapshot uses resolve placeholder — interview module resolves."""
        context = _make_context()
        result = service.select_next_question(context)

        assert "[resolve:question:" in result.question_snapshot.question_text

    def test_excludes_already_asked_ids(self, service, mock_retrieval):
        """Previously asked question IDs passed as exclude list."""
        history = [_make_exchange(question_id=42, sequence_order=1)]
        context = _make_context(exchange_history=history, exchange_sequence_order=2)
        service.select_next_question(context)

        call_args = mock_retrieval.search_by_topic.call_args
        criteria: SearchCriteria = call_args[0][0]
        assert 42 in criteria.exclude_question_ids


# ═══════════════════════════════════════════════════════════════════════
# Template Validation
# ═══════════════════════════════════════════════════════════════════════


class TestTemplateValidation:
    """Tests for template snapshot validation edge cases."""

    def test_invalid_snapshot_raises(self, service):
        context = _make_context(
            template_snapshot={"not_valid": True}
        )
        with pytest.raises(TemplateSnapshotError):
            service.select_next_question(context)

    def test_missing_section_raises(self, service):
        context = _make_context(
            current_section="nonexistent",
        )
        with pytest.raises(TemplateSnapshotError):
            service.select_next_question(context)


# ═══════════════════════════════════════════════════════════════════════
# Section Completion
# ═══════════════════════════════════════════════════════════════════════


class TestSectionCompletion:
    """Tests for section completion enforcement."""

    def test_section_complete_raises(self, service, mock_retrieval):
        """When all questions asked → SectionCompleteError."""
        snapshot = _make_template_snapshot(question_count=2)
        history = [
            _make_exchange(question_id=1, section_name="technical", sequence_order=1),
            _make_exchange(question_id=2, section_name="technical", sequence_order=2),
        ]
        context = _make_context(
            template_snapshot=snapshot,
            exchange_history=history,
            exchange_sequence_order=3,
        )
        with pytest.raises(SectionCompleteError):
            service.select_next_question(context)

    def test_section_not_complete_continues(self, service, mock_retrieval):
        """When still have remaining questions → proceeds."""
        snapshot = _make_template_snapshot(question_count=3)
        history = [
            _make_exchange(question_id=1, section_name="technical", sequence_order=1),
        ]
        context = _make_context(
            template_snapshot=snapshot,
            exchange_history=history,
            exchange_sequence_order=2,
        )
        result = service.select_next_question(context)
        assert result.question_snapshot is not None


# ═══════════════════════════════════════════════════════════════════════
# Difficulty Adaptation
# ═══════════════════════════════════════════════════════════════════════


class TestDifficultyAdaptation:
    """Tests for adaptive difficulty logic."""

    def test_static_strategy_no_adaptation(self, service, mock_retrieval):
        """Non-adaptive → static difficulty, no decision logged."""
        context = _make_context()
        result = service.select_next_question(context)

        assert result.adaptation_decision is None

    def test_adaptive_first_question_uses_default(
        self, service, mock_retrieval
    ):
        """First question in adaptive section → default difficulty."""
        snapshot = _make_template_snapshot(
            selection_strategy="adaptive",
            adaptation_enabled=True,
            difficulty_range=["easy", "medium", "hard"],
        )
        context = _make_context(
            template_snapshot=snapshot,
        )
        result = service.select_next_question(context)

        assert result.adaptation_decision is not None
        assert result.adaptation_decision.next_difficulty == "easy"
        assert result.adaptation_decision.adaptation_reason == "first_question_in_section"

    def test_adaptive_escalates_on_high_score(
        self, service, mock_retrieval
    ):
        """Score >= threshold_up → escalate difficulty."""
        snapshot = _make_template_snapshot(
            selection_strategy="adaptive",
            adaptation_enabled=True,
            difficulty_range=["easy", "medium", "hard"],
        )
        history = [
            _make_exchange(
                question_id=1,
                difficulty="easy",
                evaluation_score=90.0,
                section_name="technical",
                sequence_order=1,
            )
        ]
        context = _make_context(
            template_snapshot=snapshot,
            exchange_history=history,
            exchange_sequence_order=2,
        )
        result = service.select_next_question(context)

        assert result.adaptation_decision is not None
        assert result.adaptation_decision.next_difficulty == "medium"
        assert result.adaptation_decision.difficulty_changed is True

    def test_adaptive_downgrades_on_low_score(
        self, service, mock_retrieval
    ):
        """Score < threshold_down → downgrade difficulty."""
        snapshot = _make_template_snapshot(
            selection_strategy="adaptive",
            adaptation_enabled=True,
            difficulty_range=["easy", "medium", "hard"],
        )
        history = [
            _make_exchange(
                question_id=1,
                difficulty="medium",
                evaluation_score=30.0,
                section_name="technical",
                sequence_order=1,
            )
        ]
        context = _make_context(
            template_snapshot=snapshot,
            exchange_history=history,
            exchange_sequence_order=2,
        )
        result = service.select_next_question(context)

        assert result.adaptation_decision is not None
        assert result.adaptation_decision.next_difficulty == "easy"


# ═══════════════════════════════════════════════════════════════════════
# Repetition Filtering
# ═══════════════════════════════════════════════════════════════════════


class TestRepetitionFiltering:
    """Tests for repetition prevention."""

    def test_exact_match_filtered(self, service, mock_retrieval):
        """Candidate with same ID as history → filtered out."""
        # Set up retrieval to return candidate with id=42
        mock_retrieval.search_by_topic.return_value = _make_retrieval_result(
            candidates=[_make_candidate(question_id=42)]
        )
        history = [_make_exchange(question_id=42, sequence_order=1)]
        context = _make_context(
            exchange_history=history,
            exchange_sequence_order=2,
        )

        # When the only candidate is an exact match, fallback is triggered
        # (or NoQuestionAvailableError). We check that retrieval was called.
        try:
            result = service.select_next_question(context)
            # If fallback succeeded, it should be marked
            assert result.fallback_used is True
        except NoQuestionAvailableError:
            pass  # Expected if all fallbacks exhausted

    def test_non_matching_candidate_passes(self, service, mock_retrieval):
        """Candidate not in history → selected."""
        mock_retrieval.search_by_topic.return_value = _make_retrieval_result(
            candidates=[_make_candidate(question_id=500)]
        )
        context = _make_context()
        result = service.select_next_question(context)

        assert result.question_snapshot.question_id == 500


# ═══════════════════════════════════════════════════════════════════════
# Fallback Selection
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackSelection:
    """Tests for fallback strategy chain."""

    def test_fallback_relaxed_difficulty(self, service, mock_retrieval):
        """When primary returns empty → relaxed difficulty fallback."""
        # First call returns empty, second returns a candidate
        mock_retrieval.search_by_topic.side_effect = [
            _make_retrieval_result(candidates=[]),  # Primary
            _make_retrieval_result(candidates=[_make_candidate(question_id=10, difficulty="easy")]),  # Relaxed
        ]
        context = _make_context()
        result = service.select_next_question(context)

        assert result.fallback_used is True
        assert result.fallback_type == "relaxed_difficulty"

    def test_exhausted_fallbacks_raises(self, service, mock_retrieval):
        """When all fallbacks fail → NoQuestionAvailableError."""
        mock_retrieval.search_by_topic.return_value = _make_retrieval_result(
            candidates=[]
        )
        # No generation service available
        service._generation = None

        context = _make_context()
        with pytest.raises(NoQuestionAvailableError):
            service.select_next_question(context)


# ═══════════════════════════════════════════════════════════════════════
# Adaptation Logging
# ═══════════════════════════════════════════════════════════════════════


class TestAdaptationLogging:
    """Tests for adaptation decision audit logging."""

    def test_logs_decision_when_adaptive(
        self, service, mock_retrieval, mock_adaptation_repo
    ):
        """Adaptive strategy → adaptation decision logged."""
        snapshot = _make_template_snapshot(
            selection_strategy="adaptive",
            adaptation_enabled=True,
        )
        context = _make_context(template_snapshot=snapshot)
        service.select_next_question(context)

        mock_adaptation_repo.log_decision.assert_called_once()

    def test_no_log_when_static(
        self, service, mock_retrieval, mock_adaptation_repo
    ):
        """Static strategy → no adaptation logging."""
        context = _make_context()
        service.select_next_question(context)

        mock_adaptation_repo.log_decision.assert_not_called()

    def test_logging_failure_does_not_raise(
        self, service, mock_retrieval, mock_adaptation_repo
    ):
        """Adaptation log failure is swallowed (non-critical)."""
        mock_adaptation_repo.log_decision.side_effect = RuntimeError("DB error")

        snapshot = _make_template_snapshot(
            selection_strategy="adaptive",
            adaptation_enabled=True,
        )
        context = _make_context(template_snapshot=snapshot)

        # Should not raise
        result = service.select_next_question(context)
        assert result.question_snapshot is not None


# ═══════════════════════════════════════════════════════════════════════
# Service Initialization
# ═══════════════════════════════════════════════════════════════════════


class TestServiceInit:
    """Tests for service creation and optional dependencies."""

    def test_minimal_init(self, mock_retrieval):
        """Service works with only retrieval."""
        svc = QuestionSelectionService(retrieval_service=mock_retrieval)
        assert svc._retrieval is mock_retrieval
        assert svc._generation is None
        assert svc._adaptation_repo is None

    def test_full_init(self, mock_retrieval, mock_generation, mock_adaptation_repo):
        """Service accepts all dependencies."""
        svc = QuestionSelectionService(
            retrieval_service=mock_retrieval,
            generation_service=mock_generation,
            adaptation_repo=mock_adaptation_repo,
        )
        assert svc._retrieval is mock_retrieval
        assert svc._generation is mock_generation
        assert svc._adaptation_repo is mock_adaptation_repo


# ═══════════════════════════════════════════════════════════════════════
# Helper Methods
# ═══════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    """Tests for private utility methods."""

    def test_history_to_dicts(self):
        history = [
            _make_exchange(question_id=1, difficulty="easy", sequence_order=1),
            _make_exchange(question_id=2, difficulty="hard", sequence_order=2),
        ]
        result = QuestionSelectionService._history_to_dicts(history)

        assert len(result) == 2
        assert result[0]["question_id"] == 1
        assert result[0]["difficulty"] == "easy"
        assert result[1]["question_id"] == 2

    def test_history_to_dicts_empty(self):
        result = QuestionSelectionService._history_to_dicts([])
        assert result == []

    def test_candidate_to_snapshot(self):
        candidate = _make_candidate(question_id=5, difficulty="hard")
        section = SectionConfig(
            section_name="technical",
            question_count=5,
            question_type="technical",
        )
        snapshot = QuestionSelectionService._candidate_to_snapshot(
            candidate=candidate,
            section_config=section,
            strategy="static_pool",
            metadata={"test": True},
        )

        assert isinstance(snapshot, QuestionSnapshot)
        assert snapshot.question_id == 5
        assert snapshot.difficulty == "hard"
        assert snapshot.selection_strategy == "static_pool"
        assert snapshot.selection_metadata["test"] is True

    def test_candidate_snapshot_placeholder_text(self):
        candidate = _make_candidate(question_id=7)
        section = SectionConfig(
            section_name="tech",
            question_count=1,
            question_type="technical",
        )
        snapshot = QuestionSelectionService._candidate_to_snapshot(
            candidate=candidate,
            section_config=section,
            strategy="static_pool",
            metadata={},
        )
        assert "[resolve:question:7]" in snapshot.question_text
