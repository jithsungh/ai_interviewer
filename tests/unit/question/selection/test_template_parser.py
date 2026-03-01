"""
Unit Tests — Template Snapshot Parser

Tests pure domain logic — no mocks, no I/O, no DB.

Covers:
  1. Snapshot validation (valid / missing sections / malformed)
  2. Section finding (found / not found / multiple sections)
  3. Adaptation config extraction (present / absent / partial)
  4. Exchange counting per section
  5. Last exchange finding
"""

import pytest

from app.question.selection.contracts import (
    DifficultyAdaptationConfig,
    SectionConfig,
)
from app.question.selection.domain.template_parser import (
    SectionCompleteError,
    TemplateSnapshotError,
    count_section_exchanges,
    find_section,
    get_last_exchange_in_section,
    parse_adaptation_config,
    validate_template_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def valid_snapshot():
    return {
        "template_id": 42,
        "template_version": "v1.2.0",
        "sections": [
            {
                "section_name": "behavioral",
                "question_count": 3,
                "topic_constraints": ["communication", "teamwork"],
                "difficulty_range": ["easy", "medium"],
                "selection_strategy": "static_pool",
            },
            {
                "section_name": "technical",
                "question_count": 5,
                "topic_constraints": ["algorithms"],
                "difficulty_range": ["medium", "hard"],
                "selection_strategy": "adaptive",
            },
            {
                "section_name": "coding",
                "question_count": 2,
                "topic_constraints": ["arrays", "dp"],
                "difficulty_range": ["hard"],
                "selection_strategy": "semantic_retrieval",
            },
        ],
        "difficulty_adaptation": {
            "enabled": True,
            "threshold_up": 80.0,
            "threshold_down": 50.0,
            "max_difficulty_jump": 1,
        },
    }


@pytest.fixture
def exchange_history():
    return [
        {
            "question_id": 1,
            "section_name": "behavioral",
            "difficulty": "easy",
            "evaluation_score": 75.0,
            "sequence_order": 1,
        },
        {
            "question_id": 2,
            "section_name": "behavioral",
            "difficulty": "medium",
            "evaluation_score": 60.0,
            "sequence_order": 2,
        },
        {
            "question_id": 3,
            "section_name": "technical",
            "difficulty": "medium",
            "evaluation_score": 85.0,
            "sequence_order": 3,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════
# validate_template_snapshot
# ═══════════════════════════════════════════════════════════════════════


class TestValidateTemplateSnapshot:
    """Tests for validate_template_snapshot()."""

    def test_valid_snapshot(self, valid_snapshot):
        """No error raised for valid snapshot."""
        validate_template_snapshot(valid_snapshot)

    def test_not_a_dict(self):
        with pytest.raises(TemplateSnapshotError, match="must be a dict"):
            validate_template_snapshot("not a dict")

    def test_missing_sections(self):
        with pytest.raises(TemplateSnapshotError, match="non-empty 'sections'"):
            validate_template_snapshot({})

    def test_empty_sections(self):
        with pytest.raises(TemplateSnapshotError, match="non-empty 'sections'"):
            validate_template_snapshot({"sections": []})

    def test_sections_not_list(self):
        with pytest.raises(TemplateSnapshotError, match="must be a list"):
            validate_template_snapshot({"sections": "invalid"})

    def test_section_not_dict(self):
        with pytest.raises(TemplateSnapshotError, match="must be a dict"):
            validate_template_snapshot({"sections": ["invalid"]})

    def test_section_missing_name(self):
        with pytest.raises(TemplateSnapshotError, match="missing 'section_name'"):
            validate_template_snapshot(
                {"sections": [{"question_count": 3}]}
            )

    def test_section_missing_question_count(self):
        with pytest.raises(TemplateSnapshotError, match="missing 'question_count'"):
            validate_template_snapshot(
                {"sections": [{"section_name": "test"}]}
            )

    def test_section_zero_question_count(self):
        with pytest.raises(TemplateSnapshotError, match="positive integer"):
            validate_template_snapshot(
                {"sections": [{"section_name": "test", "question_count": 0}]}
            )

    def test_section_negative_question_count(self):
        with pytest.raises(TemplateSnapshotError, match="positive integer"):
            validate_template_snapshot(
                {"sections": [{"section_name": "test", "question_count": -1}]}
            )

    def test_section_non_integer_question_count(self):
        with pytest.raises(TemplateSnapshotError, match="positive integer"):
            validate_template_snapshot(
                {"sections": [{"section_name": "test", "question_count": 2.5}]}
            )


# ═══════════════════════════════════════════════════════════════════════
# find_section
# ═══════════════════════════════════════════════════════════════════════


class TestFindSection:
    """Tests for find_section()."""

    def test_find_existing_section(self, valid_snapshot):
        config = find_section(valid_snapshot, "behavioral")
        assert config is not None
        assert config.section_name == "behavioral"
        assert config.question_count == 3
        assert config.topic_constraints == ["communication", "teamwork"]
        assert config.selection_strategy == "static_pool"

    def test_find_technical_section(self, valid_snapshot):
        config = find_section(valid_snapshot, "technical")
        assert config is not None
        assert config.selection_strategy == "adaptive"
        assert config.difficulty_range == ["medium", "hard"]

    def test_section_not_found(self, valid_snapshot):
        config = find_section(valid_snapshot, "nonexistent")
        assert config is None

    def test_empty_sections(self):
        config = find_section({"sections": []}, "test")
        assert config is None

    def test_defaults_applied(self):
        """Missing optional fields get defaults."""
        snapshot = {
            "sections": [
                {"section_name": "minimal", "question_count": 1}
            ]
        }
        config = find_section(snapshot, "minimal")
        assert config is not None
        assert config.question_type == "technical"
        assert config.topic_constraints == []
        assert config.selection_strategy == "static_pool"


# ═══════════════════════════════════════════════════════════════════════
# parse_adaptation_config
# ═══════════════════════════════════════════════════════════════════════


class TestParseAdaptationConfig:
    """Tests for parse_adaptation_config()."""

    def test_full_config(self, valid_snapshot):
        config = parse_adaptation_config(valid_snapshot)
        assert config.enabled is True
        assert config.threshold_up == 80.0
        assert config.threshold_down == 50.0
        assert config.max_difficulty_jump == 1

    def test_missing_section(self):
        """Missing difficulty_adaptation → defaults."""
        config = parse_adaptation_config({})
        assert config.enabled is True
        assert config.threshold_up == 80.0

    def test_partial_config(self):
        """Only some fields → rest default."""
        config = parse_adaptation_config(
            {"difficulty_adaptation": {"threshold_up": 90.0}}
        )
        assert config.threshold_up == 90.0
        assert config.threshold_down == 50.0  # default

    def test_non_dict_section(self):
        """Non-dict adaptation section → defaults."""
        config = parse_adaptation_config(
            {"difficulty_adaptation": "invalid"}
        )
        assert isinstance(config, DifficultyAdaptationConfig)


# ═══════════════════════════════════════════════════════════════════════
# count_section_exchanges
# ═══════════════════════════════════════════════════════════════════════


class TestCountSectionExchanges:
    """Tests for count_section_exchanges()."""

    def test_count_behavioral(self, exchange_history):
        assert count_section_exchanges(exchange_history, "behavioral") == 2

    def test_count_technical(self, exchange_history):
        assert count_section_exchanges(exchange_history, "technical") == 1

    def test_count_nonexistent_section(self, exchange_history):
        assert count_section_exchanges(exchange_history, "coding") == 0

    def test_empty_history(self):
        assert count_section_exchanges([], "behavioral") == 0


# ═══════════════════════════════════════════════════════════════════════
# get_last_exchange_in_section
# ═══════════════════════════════════════════════════════════════════════


class TestGetLastExchangeInSection:
    """Tests for get_last_exchange_in_section()."""

    def test_last_in_behavioral(self, exchange_history):
        last = get_last_exchange_in_section(exchange_history, "behavioral")
        assert last is not None
        assert last["question_id"] == 2
        assert last["sequence_order"] == 2

    def test_last_in_technical(self, exchange_history):
        last = get_last_exchange_in_section(exchange_history, "technical")
        assert last is not None
        assert last["question_id"] == 3

    def test_no_exchanges_in_section(self, exchange_history):
        last = get_last_exchange_in_section(exchange_history, "coding")
        assert last is None

    def test_empty_history(self):
        last = get_last_exchange_in_section([], "behavioral")
        assert last is None


# ═══════════════════════════════════════════════════════════════════════
# SectionCompleteError
# ═══════════════════════════════════════════════════════════════════════


class TestSectionCompleteError:
    """Tests for SectionCompleteError."""

    def test_error_message(self):
        err = SectionCompleteError("behavioral", asked=3, total=3)
        assert "behavioral" in str(err)
        assert "3/3" in str(err)
        assert err.section_name == "behavioral"
        assert err.asked == 3
        assert err.total == 3
