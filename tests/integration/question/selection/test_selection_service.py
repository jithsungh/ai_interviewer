"""
Integration Tests — Selection Service (End-to-End with Mocked Infra)

Tests the full selection workflow with a real template snapshot,
real domain logic, and mocked retrieval/generation services.

Does NOT require PostgreSQL or Qdrant (all infra mocked).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from app.question.retrieval.contracts import (
    QuestionCandidate,
    RetrievalResult,
    RetrievalStrategy,
)
from app.question.selection.contracts import (
    CandidateProfile,
    ExchangeHistoryEntry,
    RepetitionConfig,
    SelectionContext,
    SelectionResult,
)
from app.question.selection.domain.template_parser import SectionCompleteError
from app.question.selection.service import (
    NoQuestionAvailableError,
    QuestionSelectionService,
)


# ═══════════════════════════════════════════════════════════════════════
# Realistic Template Snapshots
# ═══════════════════════════════════════════════════════════════════════


REALISTIC_TEMPLATE = {
    "sections": [
        {
            "section_name": "behavioral",
            "question_count": 3,
            "question_type": "behavioral",
            "selection_strategy": "static_pool",
            "difficulty_range": ["easy", "medium"],
        },
        {
            "section_name": "technical",
            "question_count": 5,
            "question_type": "technical",
            "selection_strategy": "adaptive",
            "difficulty_range": ["easy", "medium", "hard"],
        },
        {
            "section_name": "coding",
            "question_count": 2,
            "question_type": "coding",
            "selection_strategy": "static_pool",
            "difficulty_range": ["medium", "hard"],
        },
    ],
    "difficulty_adaptation": {
        "enabled": True,
        "threshold_up": 80.0,
        "threshold_down": 50.0,
        "max_difficulty_jump": 1,
    },
}


def _candidate(qid: int, diff: str = "medium") -> QuestionCandidate:
    return QuestionCandidate(
        question_id=qid,
        similarity_score=0.85,
        difficulty=diff,
        metadata={},
    )


def _result(candidates: List[QuestionCandidate]) -> RetrievalResult:
    return RetrievalResult(
        candidates=candidates,
        strategy_used=RetrievalStrategy.TOPIC_FILTER,
        total_found=len(candidates),
    )


def _build_service(
    retrieval_candidates: Optional[List[QuestionCandidate]] = None,
) -> QuestionSelectionService:
    """Build service with mocked retrieval that returns provided candidates."""
    mock_retrieval = MagicMock()
    cands = retrieval_candidates or [_candidate(100)]
    mock_retrieval.search_by_topic.return_value = _result(cands)
    mock_retrieval.search_semantic.return_value = _result(cands)
    mock_retrieval.get_embedding_vector.return_value = None

    mock_repo = MagicMock()
    mock_repo.log_decision.return_value = 1

    return QuestionSelectionService(
        retrieval_service=mock_retrieval,
        generation_service=None,
        adaptation_repo=mock_repo,
    )


# ═══════════════════════════════════════════════════════════════════════
# Full Workflow Integration
# ═══════════════════════════════════════════════════════════════════════


class TestFullWorkflow:
    """End-to-end workflow tests with realistic template."""

    def test_first_behavioral_question(self):
        svc = _build_service([_candidate(10, "easy")])
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot=REALISTIC_TEMPLATE,
            current_section="behavioral",
            exchange_history=[],
            exchange_sequence_order=1,
        )
        result = svc.select_next_question(ctx)

        assert isinstance(result, SelectionResult)
        assert result.question_snapshot.question_id == 10
        assert result.fallback_used is False
        # Behavioral uses static_pool → no adaptation
        assert result.adaptation_decision is None

    def test_first_technical_question_adaptive(self):
        svc = _build_service([_candidate(20, "easy")])
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot=REALISTIC_TEMPLATE,
            current_section="technical",
            exchange_history=[],
            exchange_sequence_order=1,
        )
        result = svc.select_next_question(ctx)

        assert result.question_snapshot is not None
        # Adaptive + first question → adaptation decision logged
        assert result.adaptation_decision is not None
        assert result.adaptation_decision.adaptation_reason == "first_question_in_section"

    def test_adaptive_escalation_across_exchanges(self):
        """Simulate multi-exchange adaptive progression."""
        svc = _build_service([_candidate(30, "medium")])
        history = [
            ExchangeHistoryEntry(
                question_id=20,
                question_text="What is polymorphism?",
                difficulty="easy",
                section_name="technical",
                evaluation_score=90.0,
                sequence_order=1,
            )
        ]
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot=REALISTIC_TEMPLATE,
            current_section="technical",
            exchange_history=history,
            exchange_sequence_order=2,
        )
        result = svc.select_next_question(ctx)

        assert result.adaptation_decision is not None
        # Score 90 >= threshold_up 80 → escalate from easy → medium
        assert result.adaptation_decision.next_difficulty == "medium"
        assert result.adaptation_decision.difficulty_changed is True

    def test_section_complete_enforcement(self):
        """All questions asked in section → SectionCompleteError."""
        svc = _build_service()
        history = [
            ExchangeHistoryEntry(
                question_id=i,
                question_text=f"Q{i}",
                difficulty="easy",
                section_name="behavioral",
                evaluation_score=70.0,
                sequence_order=i,
            )
            for i in range(1, 4)  # 3 questions asked, behavioral has 3
        ]
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot=REALISTIC_TEMPLATE,
            current_section="behavioral",
            exchange_history=history,
            exchange_sequence_order=4,
        )
        with pytest.raises(SectionCompleteError):
            svc.select_next_question(ctx)

    def test_cross_section_history_isolation(self):
        """Exchanges in 'behavioral' don't count toward 'technical' quota."""
        svc = _build_service([_candidate(40)])
        history = [
            ExchangeHistoryEntry(
                question_id=i,
                question_text=f"Q{i}",
                difficulty="easy",
                section_name="behavioral",
                evaluation_score=70.0,
                sequence_order=i,
            )
            for i in range(1, 4)  # 3 behavioral questions
        ]
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot=REALISTIC_TEMPLATE,
            current_section="technical",
            exchange_history=history,
            exchange_sequence_order=4,
        )
        # Technical section has 5 questions, 0 asked in tech → should succeed
        result = svc.select_next_question(ctx)
        assert result.question_snapshot is not None
