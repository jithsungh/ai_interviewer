"""
Unit Tests — Pydantic DTOs (Contracts)

Tests validation rules, default values, enum behavior, and edge cases.
No mocks, no I/O.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError as PydanticValidationError

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


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class TestSelectionStrategy:
    """Tests for SelectionStrategy enum."""

    def test_values(self):
        assert SelectionStrategy.SEMANTIC_RETRIEVAL == "semantic_retrieval"
        assert SelectionStrategy.STATIC_POOL == "static_pool"
        assert SelectionStrategy.ADAPTIVE == "adaptive"
        assert SelectionStrategy.GENERATION == "generation"
        assert SelectionStrategy.FALLBACK_GENERIC == "fallback_generic"

    def test_all_strategies(self):
        assert len(SelectionStrategy) == 5


class TestFallbackType:
    """Tests for FallbackType enum."""

    def test_values(self):
        assert FallbackType.RELAXED_DIFFICULTY == "relaxed_difficulty"
        assert FallbackType.RELAXED_TOPIC == "relaxed_topic"
        assert FallbackType.RELAXED_SIMILARITY == "relaxed_similarity"
        assert FallbackType.LLM_GENERATION == "llm_generation"
        assert FallbackType.GENERIC_FALLBACK == "generic_fallback"

    def test_all_types(self):
        assert len(FallbackType) == 5


# ═══════════════════════════════════════════════════════════════════════
# DifficultyAdaptationConfig
# ═══════════════════════════════════════════════════════════════════════


class TestDifficultyAdaptationConfig:
    """Tests for DifficultyAdaptationConfig DTO."""

    def test_defaults(self):
        config = DifficultyAdaptationConfig()
        assert config.enabled is True
        assert config.threshold_up == 80.0
        assert config.threshold_down == 50.0
        assert config.max_difficulty_jump == 1
        assert config.difficulty_order == ["easy", "medium", "hard"]

    def test_custom_thresholds(self):
        config = DifficultyAdaptationConfig(
            threshold_up=90.0, threshold_down=40.0, max_difficulty_jump=2
        )
        assert config.threshold_up == 90.0
        assert config.threshold_down == 40.0
        assert config.max_difficulty_jump == 2

    def test_threshold_up_out_of_range(self):
        with pytest.raises(PydanticValidationError):
            DifficultyAdaptationConfig(threshold_up=101.0)

    def test_threshold_down_negative(self):
        with pytest.raises(PydanticValidationError):
            DifficultyAdaptationConfig(threshold_down=-1.0)

    def test_max_jump_zero(self):
        with pytest.raises(PydanticValidationError):
            DifficultyAdaptationConfig(max_difficulty_jump=0)

    def test_max_jump_too_large(self):
        with pytest.raises(PydanticValidationError):
            DifficultyAdaptationConfig(max_difficulty_jump=3)

    def test_invalid_difficulty_in_order(self):
        with pytest.raises(PydanticValidationError, match="Invalid difficulty"):
            DifficultyAdaptationConfig(
                difficulty_order=["easy", "medium", "extreme"]
            )

    def test_duplicate_difficulty_in_order(self):
        with pytest.raises(PydanticValidationError, match="Duplicate"):
            DifficultyAdaptationConfig(
                difficulty_order=["easy", "easy", "hard"]
            )


# ═══════════════════════════════════════════════════════════════════════
# RepetitionConfig
# ═══════════════════════════════════════════════════════════════════════


class TestRepetitionConfig:
    """Tests for RepetitionConfig DTO."""

    def test_defaults(self):
        config = RepetitionConfig()
        assert config.enable_exact_match_check is True
        assert config.enable_semantic_check is True
        assert config.similarity_threshold_identical == 0.95
        assert config.similarity_threshold_similar == 0.85
        assert config.relax_threshold_on_exhaustion is True
        assert config.relaxed_similarity_threshold == 0.90

    def test_threshold_range_validation(self):
        with pytest.raises(PydanticValidationError):
            RepetitionConfig(similarity_threshold_similar=1.5)

    def test_negative_threshold(self):
        with pytest.raises(PydanticValidationError):
            RepetitionConfig(similarity_threshold_similar=-0.1)


# ═══════════════════════════════════════════════════════════════════════
# SectionConfig
# ═══════════════════════════════════════════════════════════════════════


class TestSectionConfig:
    """Tests for SectionConfig DTO."""

    def test_valid_section(self):
        config = SectionConfig(
            section_name="behavioral",
            question_count=3,
            topic_constraints=["communication"],
            difficulty_range=["easy", "medium"],
            selection_strategy="static_pool",
        )
        assert config.section_name == "behavioral"
        assert config.question_count == 3
        assert config.selection_strategy == "static_pool"

    def test_invalid_strategy(self):
        with pytest.raises(PydanticValidationError, match="selection_strategy"):
            SectionConfig(
                section_name="test",
                question_count=1,
                selection_strategy="invalid_strategy",
            )

    def test_negative_question_count(self):
        with pytest.raises(PydanticValidationError):
            SectionConfig(
                section_name="test",
                question_count=0,
            )

    def test_defaults(self):
        config = SectionConfig(section_name="test", question_count=2)
        assert config.question_type == "technical"
        assert config.topic_constraints == []
        assert config.difficulty_range == []
        assert config.selection_strategy == "static_pool"
        assert config.template_instructions is None


# ═══════════════════════════════════════════════════════════════════════
# ExchangeHistoryEntry
# ═══════════════════════════════════════════════════════════════════════


class TestExchangeHistoryEntry:
    """Tests for ExchangeHistoryEntry DTO."""

    def test_valid_entry(self):
        entry = ExchangeHistoryEntry(
            question_id=42,
            question_text="What is polymorphism?",
            difficulty="medium",
            section_name="technical",
            evaluation_score=85.0,
            sequence_order=1,
        )
        assert entry.question_id == 42
        assert entry.evaluation_score == 85.0

    def test_score_out_of_range(self):
        with pytest.raises(PydanticValidationError):
            ExchangeHistoryEntry(
                question_text="Q",
                difficulty="easy",
                sequence_order=1,
                evaluation_score=101.0,
            )

    def test_negative_sequence_order(self):
        with pytest.raises(PydanticValidationError):
            ExchangeHistoryEntry(
                question_text="Q",
                difficulty="easy",
                sequence_order=0,
            )


# ═══════════════════════════════════════════════════════════════════════
# SelectionContext
# ═══════════════════════════════════════════════════════════════════════


class TestSelectionContext:
    """Tests for SelectionContext DTO."""

    def test_valid_context(self):
        ctx = SelectionContext(
            submission_id=1,
            organization_id=1,
            template_snapshot={
                "sections": [
                    {"section_name": "tech", "question_count": 3}
                ]
            },
            current_section="tech",
            exchange_sequence_order=1,
        )
        assert ctx.submission_id == 1
        assert ctx.exchange_history == []

    def test_zero_submission_id(self):
        with pytest.raises(PydanticValidationError):
            SelectionContext(
                submission_id=0,
                organization_id=1,
                template_snapshot={"sections": []},
                current_section="x",
                exchange_sequence_order=1,
            )

    def test_empty_section_name(self):
        with pytest.raises(PydanticValidationError):
            SelectionContext(
                submission_id=1,
                organization_id=1,
                template_snapshot={"sections": []},
                current_section="",
                exchange_sequence_order=1,
            )


# ═══════════════════════════════════════════════════════════════════════
# QuestionSnapshot
# ═══════════════════════════════════════════════════════════════════════


class TestQuestionSnapshot:
    """Tests for QuestionSnapshot DTO."""

    def test_valid_snapshot(self):
        snap = QuestionSnapshot(
            question_id=42,
            question_type="technical",
            question_text="Explain REST vs GraphQL.",
            difficulty="medium",
            selection_strategy="static_pool",
        )
        assert snap.question_id == 42
        assert snap.selection_rule_version == "1.0.0"
        assert isinstance(snap.selected_at, datetime)

    def test_generated_question_no_id(self):
        snap = QuestionSnapshot(
            question_id=None,
            question_type="behavioral",
            question_text="Describe a conflict situation.",
            difficulty="easy",
            selection_strategy="generation",
        )
        assert snap.question_id is None

    def test_empty_question_text(self):
        with pytest.raises(PydanticValidationError):
            QuestionSnapshot(
                question_type="technical",
                question_text="",
                difficulty="medium",
                selection_strategy="static_pool",
            )


# ═══════════════════════════════════════════════════════════════════════
# AdaptationDecision
# ═══════════════════════════════════════════════════════════════════════


class TestAdaptationDecision:
    """Tests for AdaptationDecision DTO."""

    def test_valid_decision(self):
        decision = AdaptationDecision(
            submission_id=1,
            exchange_sequence_order=3,
            previous_difficulty="easy",
            previous_score=85.0,
            adaptation_rule="score_escalation",
            threshold_up=80.0,
            threshold_down=50.0,
            next_difficulty="medium",
            adaptation_reason="score_85.0_above_threshold_80.0",
            difficulty_changed=True,
            rule_version="1.0.0",
        )
        assert decision.difficulty_changed is True

    def test_first_question_no_previous(self):
        decision = AdaptationDecision(
            submission_id=1,
            exchange_sequence_order=1,
            previous_difficulty=None,
            previous_score=None,
            adaptation_rule="template_default",
            next_difficulty="medium",
            adaptation_reason="first_question",
        )
        assert decision.previous_difficulty is None
        assert decision.previous_score is None


# ═══════════════════════════════════════════════════════════════════════
# SelectionResult
# ═══════════════════════════════════════════════════════════════════════


class TestSelectionResult:
    """Tests for SelectionResult DTO."""

    def test_result_with_fallback(self):
        snap = QuestionSnapshot(
            question_type="technical",
            question_text="Test question",
            difficulty="easy",
            selection_strategy="static_pool",
        )
        result = SelectionResult(
            question_snapshot=snap,
            fallback_used=True,
            fallback_type="relaxed_difficulty",
        )
        assert result.fallback_used is True
        assert result.fallback_type == "relaxed_difficulty"

    def test_result_without_fallback(self):
        snap = QuestionSnapshot(
            question_type="technical",
            question_text="Test question",
            difficulty="medium",
            selection_strategy="semantic_retrieval",
        )
        result = SelectionResult(question_snapshot=snap)
        assert result.fallback_used is False
        assert result.adaptation_decision is None


# ═══════════════════════════════════════════════════════════════════════
# CandidateProfile
# ═══════════════════════════════════════════════════════════════════════


class TestCandidateProfile:
    """Tests for CandidateProfile DTO."""

    def test_empty_profile(self):
        profile = CandidateProfile()
        assert profile.resume_text is None
        assert profile.resume_embedding is None

    def test_with_embeddings(self):
        profile = CandidateProfile(
            resume_embedding=[0.1, 0.2, 0.3],
            jd_embedding=[0.4, 0.5, 0.6],
        )
        assert len(profile.resume_embedding) == 3
