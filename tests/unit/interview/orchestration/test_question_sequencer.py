"""
Unit Tests — Question Sequencer

Tests pure domain logic for deterministic question resolution
from frozen template snapshots. No I/O, no mocks needed.
"""

import pytest

from app.interview.orchestration.contracts import (
    NextQuestionResult,
    TemplateSectionSnapshot,
    TemplateSnapshot,
)
from app.interview.orchestration.errors import (
    TemplateSnapshotInvalidError,
    TemplateSnapshotMissingError,
)
from app.interview.orchestration.question_sequencer import (
    get_section_for_sequence,
    get_total_questions,
    resolve_next_question,
    validate_template_snapshot,
)


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def simple_snapshot() -> TemplateSnapshot:
    """3 sections, 8 total questions."""
    return TemplateSnapshot(
        template_id=3,
        template_name="Full Stack Engineer Interview",
        sections=[
            TemplateSectionSnapshot(
                section_name="resume",
                question_count=2,
                question_ids=[101, 102],
            ),
            TemplateSectionSnapshot(
                section_name="behavioral",
                question_count=3,
                question_ids=[201, 202, 203],
            ),
            TemplateSectionSnapshot(
                section_name="coding",
                question_count=3,
                question_ids=[301, 302, 303],
            ),
        ],
        total_questions=8,
    )


@pytest.fixture
def single_section_snapshot() -> TemplateSnapshot:
    """Single section, 3 questions."""
    return TemplateSnapshot(
        template_id=1,
        template_name="Quick Screen",
        sections=[
            TemplateSectionSnapshot(
                section_name="technical",
                question_count=3,
                question_ids=[10, 20, 30],
            ),
        ],
        total_questions=3,
    )


@pytest.fixture
def single_question_snapshot() -> TemplateSnapshot:
    """Single section, single question."""
    return TemplateSnapshot(
        template_id=99,
        template_name="Single Question",
        sections=[
            TemplateSectionSnapshot(
                section_name="intro",
                question_count=1,
                question_ids=[500],
            ),
        ],
        total_questions=1,
    )


# ════════════════════════════════════════════════════════════════════════
# resolve_next_question
# ════════════════════════════════════════════════════════════════════════


class TestResolveNextQuestion:
    """Tests for resolve_next_question()."""

    def test_first_question(self, simple_snapshot):
        """Sequence 0 → first question in first section."""
        result = resolve_next_question(simple_snapshot, current_sequence=0)

        assert result is not None
        assert result.question_id == 101
        assert result.sequence_order == 1
        assert result.section_name == "resume"
        assert result.is_final_question is False

    def test_second_question_same_section(self, simple_snapshot):
        """Sequence 1 → second question in first section."""
        result = resolve_next_question(simple_snapshot, current_sequence=1)

        assert result is not None
        assert result.question_id == 102
        assert result.sequence_order == 2
        assert result.section_name == "resume"
        assert result.is_final_question is False

    def test_first_question_second_section(self, simple_snapshot):
        """Sequence 2 → first question in behavioral section."""
        result = resolve_next_question(simple_snapshot, current_sequence=2)

        assert result is not None
        assert result.question_id == 201
        assert result.sequence_order == 3
        assert result.section_name == "behavioral"
        assert result.is_final_question is False

    def test_last_question_middle_section(self, simple_snapshot):
        """Sequence 4 → last question in behavioral section."""
        result = resolve_next_question(simple_snapshot, current_sequence=4)

        assert result is not None
        assert result.question_id == 203
        assert result.sequence_order == 5
        assert result.section_name == "behavioral"
        assert result.is_final_question is False

    def test_first_question_last_section(self, simple_snapshot):
        """Sequence 5 → first question in coding section."""
        result = resolve_next_question(simple_snapshot, current_sequence=5)

        assert result is not None
        assert result.question_id == 301
        assert result.sequence_order == 6
        assert result.section_name == "coding"
        assert result.is_final_question is False

    def test_final_question(self, simple_snapshot):
        """Sequence 7 → last question, is_final_question=True."""
        result = resolve_next_question(simple_snapshot, current_sequence=7)

        assert result is not None
        assert result.question_id == 303
        assert result.sequence_order == 8
        assert result.section_name == "coding"
        assert result.is_final_question is True

    def test_all_questions_complete(self, simple_snapshot):
        """Sequence 8 (all done) → returns None."""
        result = resolve_next_question(simple_snapshot, current_sequence=8)
        assert result is None

    def test_beyond_total_questions(self, simple_snapshot):
        """Sequence > total → returns None."""
        result = resolve_next_question(simple_snapshot, current_sequence=100)
        assert result is None

    def test_single_section(self, single_section_snapshot):
        """Works correctly with single section."""
        r0 = resolve_next_question(single_section_snapshot, 0)
        r1 = resolve_next_question(single_section_snapshot, 1)
        r2 = resolve_next_question(single_section_snapshot, 2)
        r3 = resolve_next_question(single_section_snapshot, 3)

        assert r0.question_id == 10
        assert r1.question_id == 20
        assert r2.question_id == 30
        assert r2.is_final_question is True
        assert r3 is None

    def test_single_question(self, single_question_snapshot):
        """Works correctly with single question."""
        result = resolve_next_question(single_question_snapshot, 0)

        assert result is not None
        assert result.question_id == 500
        assert result.sequence_order == 1
        assert result.is_final_question is True

        done = resolve_next_question(single_question_snapshot, 1)
        assert done is None

    def test_complete_walkthrough(self, simple_snapshot):
        """Walk through all 8 questions sequentially."""
        expected_ids = [101, 102, 201, 202, 203, 301, 302, 303]
        expected_sections = [
            "resume", "resume",
            "behavioral", "behavioral", "behavioral",
            "coding", "coding", "coding",
        ]

        for i in range(8):
            result = resolve_next_question(simple_snapshot, i)
            assert result is not None, f"Expected question at sequence {i}"
            assert result.question_id == expected_ids[i], f"Wrong ID at seq {i}"
            assert result.section_name == expected_sections[i], f"Wrong section at seq {i}"
            assert result.sequence_order == i + 1
            assert result.is_final_question == (i == 7)

        # After all 8
        assert resolve_next_question(simple_snapshot, 8) is None


# ════════════════════════════════════════════════════════════════════════
# validate_template_snapshot
# ════════════════════════════════════════════════════════════════════════


class TestValidateTemplateSnapshot:
    """Tests for validate_template_snapshot()."""

    def test_valid_snapshot(self):
        """Valid raw dict → TemplateSnapshot."""
        raw = {
            "template_id": 1,
            "template_name": "Test",
            "sections": [
                {
                    "section_name": "sec1",
                    "question_count": 2,
                    "question_ids": [1, 2],
                }
            ],
            "total_questions": 2,
        }
        result = validate_template_snapshot(raw, submission_id=42)
        assert isinstance(result, TemplateSnapshot)
        assert result.template_id == 1
        assert result.total_questions == 2

    def test_none_snapshot_raises(self):
        """None → TemplateSnapshotMissingError."""
        with pytest.raises(TemplateSnapshotMissingError) as exc_info:
            validate_template_snapshot(None, submission_id=42)
        assert exc_info.value.metadata["submission_id"] == 42

    def test_non_dict_raises(self):
        """Non-dict → TemplateSnapshotInvalidError."""
        with pytest.raises(TemplateSnapshotInvalidError):
            validate_template_snapshot("not a dict", submission_id=42)

    def test_missing_required_field(self):
        """Missing template_id → TemplateSnapshotInvalidError."""
        raw = {
            "template_name": "Test",
            "sections": [],
            "total_questions": 0,
        }
        with pytest.raises(TemplateSnapshotInvalidError):
            validate_template_snapshot(raw, submission_id=42)

    def test_total_questions_mismatch(self):
        """total_questions doesn't match sum → TemplateSnapshotInvalidError."""
        raw = {
            "template_id": 1,
            "template_name": "Test",
            "sections": [
                {
                    "section_name": "sec1",
                    "question_count": 2,
                    "question_ids": [1, 2],
                }
            ],
            "total_questions": 5,  # Wrong! Should be 2
        }
        with pytest.raises(TemplateSnapshotInvalidError):
            validate_template_snapshot(raw, submission_id=42)

    def test_question_ids_count_mismatch(self):
        """question_ids length != question_count → error."""
        raw = {
            "template_id": 1,
            "template_name": "Test",
            "sections": [
                {
                    "section_name": "sec1",
                    "question_count": 3,
                    "question_ids": [1, 2],  # Only 2, should be 3
                }
            ],
            "total_questions": 3,
        }
        with pytest.raises(TemplateSnapshotInvalidError):
            validate_template_snapshot(raw, submission_id=42)

    def test_empty_sections(self):
        """Empty sections list → TemplateSnapshotInvalidError."""
        raw = {
            "template_id": 1,
            "template_name": "Test",
            "sections": [],
            "total_questions": 1,
        }
        with pytest.raises(TemplateSnapshotInvalidError):
            validate_template_snapshot(raw, submission_id=42)


# ════════════════════════════════════════════════════════════════════════
# get_total_questions
# ════════════════════════════════════════════════════════════════════════


class TestGetTotalQuestions:
    def test_returns_total(self, simple_snapshot):
        assert get_total_questions(simple_snapshot) == 8

    def test_single_question(self, single_question_snapshot):
        assert get_total_questions(single_question_snapshot) == 1


# ════════════════════════════════════════════════════════════════════════
# get_section_for_sequence
# ════════════════════════════════════════════════════════════════════════


class TestGetSectionForSequence:
    def test_first_section(self, simple_snapshot):
        assert get_section_for_sequence(simple_snapshot, 0) == "resume"
        assert get_section_for_sequence(simple_snapshot, 1) == "resume"

    def test_second_section(self, simple_snapshot):
        assert get_section_for_sequence(simple_snapshot, 2) == "behavioral"
        assert get_section_for_sequence(simple_snapshot, 4) == "behavioral"

    def test_third_section(self, simple_snapshot):
        assert get_section_for_sequence(simple_snapshot, 5) == "coding"
        assert get_section_for_sequence(simple_snapshot, 7) == "coding"

    def test_out_of_range(self, simple_snapshot):
        assert get_section_for_sequence(simple_snapshot, 8) is None
        assert get_section_for_sequence(simple_snapshot, 100) is None


# ════════════════════════════════════════════════════════════════════════
# TemplateSnapshot Pydantic validation
# ════════════════════════════════════════════════════════════════════════


class TestTemplateSnapshotValidation:
    """Test Pydantic model validation rules."""

    def test_valid_construction(self):
        """Valid data creates snapshot."""
        ts = TemplateSnapshot(
            template_id=1,
            template_name="Test",
            sections=[
                TemplateSectionSnapshot(
                    section_name="a",
                    question_count=1,
                    question_ids=[10],
                ),
            ],
            total_questions=1,
        )
        assert ts.total_questions == 1

    def test_zero_total_questions_rejected(self):
        """total_questions must be > 0."""
        with pytest.raises(Exception):
            TemplateSnapshot(
                template_id=1,
                template_name="Test",
                sections=[
                    TemplateSectionSnapshot(
                        section_name="a",
                        question_count=0,
                        question_ids=[],
                    ),
                ],
                total_questions=0,
            )

    def test_negative_template_id_rejected(self):
        """template_id must be > 0."""
        with pytest.raises(Exception):
            TemplateSnapshot(
                template_id=-1,
                template_name="Test",
                sections=[
                    TemplateSectionSnapshot(
                        section_name="a",
                        question_count=1,
                        question_ids=[1],
                    ),
                ],
                total_questions=1,
            )

    def test_multi_section_total_mismatch(self):
        """total_questions must match sum of all section counts."""
        with pytest.raises(ValueError, match="total_questions"):
            TemplateSnapshot(
                template_id=1,
                template_name="Test",
                sections=[
                    TemplateSectionSnapshot(
                        section_name="a",
                        question_count=2,
                        question_ids=[1, 2],
                    ),
                    TemplateSectionSnapshot(
                        section_name="b",
                        question_count=3,
                        question_ids=[3, 4, 5],
                    ),
                ],
                total_questions=4,  # Should be 5
            )
