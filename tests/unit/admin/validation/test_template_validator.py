"""
Unit tests for TemplateStructureValidator.

Pure domain logic — no mocks, no DB.
Tests both "simple" and "v2" template structure flavours.
"""

import pytest

from app.admin.validation.template_validator import TemplateStructureValidator
from app.admin.validation.result import ValidationResult


# ─────────────────────────────────────────────────────────────────
# Valid structures
# ─────────────────────────────────────────────────────────────────


VALID_SIMPLE_TEMPLATE = {
    "resume_analysis": {"enabled": True, "weight": 10},
    "self_introduction": {"enabled": True, "max_duration_seconds": 120, "weight": 5},
    "topics_assessment": {
        "enabled": True,
        "total_questions": 6,
        "topics": [
            {
                "topic_id": 12,
                "difficulty_strategy": "dynamic",
                "allowed_difficulties": ["easy", "medium", "hard"],
                "weight": 15,
            },
            {
                "topic_id": 18,
                "difficulty_strategy": "fixed",
                "difficulty": "medium",
                "weight": 20,
            },
        ],
    },
    "coding_round": {
        "enabled": True,
        "total_problems": 1,
        "difficulty": "medium",
        "languages_allowed": ["python", "java", "cpp"],
        "weight": 30,
    },
    "scoring": {"strategy": "weighted_sum", "normalization": "percentage", "pass_threshold": 60},
}


VALID_V2_TEMPLATE = {
    "$schema": "interview_template_v2.0",
    "template_metadata": {"template_name": "Test"},
    "sections": {
        "resume_analysis": {"enabled": True, "weight": 10},
        "coding_round": {"enabled": True, "total_problems": 2, "weight": 30},
    },
    "scoring": {"strategy": "weighted_sum", "pass_threshold": 70},
}


# ─────────────────────────────────────────────────────────────────
# Valid template tests
# ─────────────────────────────────────────────────────────────────


class TestValidTemplates:
    def test_simple_template_passes(self):
        result = TemplateStructureValidator.validate(VALID_SIMPLE_TEMPLATE)
        assert result.is_valid, [e.message for e in result.errors]

    def test_v2_template_passes(self):
        result = TemplateStructureValidator.validate(VALID_V2_TEMPLATE)
        assert result.is_valid, [e.message for e in result.errors]

    def test_minimal_single_section(self):
        result = TemplateStructureValidator.validate(
            {"resume_analysis": {"enabled": True}}
        )
        assert result.is_valid

    def test_section_enabled_defaults_to_true(self):
        """If 'enabled' is not set, section counts as enabled."""
        result = TemplateStructureValidator.validate(
            {"coding_round": {"total_problems": 1}}
        )
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Invalid type
# ─────────────────────────────────────────────────────────────────


class TestInvalidType:
    def test_not_a_dict(self):
        result = TemplateStructureValidator.validate("not a dict")  # type: ignore[arg-type]
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_TYPE"

    def test_none_value(self):
        result = TemplateStructureValidator.validate(None)  # type: ignore[arg-type]
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_TYPE"


# ─────────────────────────────────────────────────────────────────
# Missing / empty sections
# ─────────────────────────────────────────────────────────────────


class TestMissingSections:
    def test_empty_dict(self):
        result = TemplateStructureValidator.validate({})
        assert not result.is_valid
        assert any(e.code == "NO_SECTIONS" for e in result.errors)

    def test_only_unknown_keys(self):
        result = TemplateStructureValidator.validate(
            {"$schema": "v2", "template_metadata": {"name": "test"}}
        )
        assert not result.is_valid
        assert any(e.code == "NO_SECTIONS" for e in result.errors)

    def test_v2_empty_sections(self):
        result = TemplateStructureValidator.validate({"sections": {}})
        assert not result.is_valid
        assert any(e.code == "EMPTY_SECTIONS" for e in result.errors)

    def test_v2_sections_not_dict(self):
        result = TemplateStructureValidator.validate({"sections": "invalid"})
        assert not result.is_valid

    def test_all_sections_disabled(self):
        result = TemplateStructureValidator.validate(
            {"resume_analysis": {"enabled": False}, "coding_round": {"enabled": False}}
        )
        assert not result.is_valid
        assert any(e.code == "NO_ENABLED_SECTIONS" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Section content validation
# ─────────────────────────────────────────────────────────────────


class TestSectionContent:
    def test_section_not_dict(self):
        result = TemplateStructureValidator.validate(
            {"resume_analysis": "not_a_dict"}
        )
        assert not result.is_valid
        assert any(e.code == "INVALID_SECTION_TYPE" for e in result.errors)

    def test_negative_weight(self):
        result = TemplateStructureValidator.validate(
            {"resume_analysis": {"enabled": True, "weight": -5}}
        )
        assert not result.is_valid
        assert any(e.code == "INVALID_WEIGHT" for e in result.errors)

    def test_string_weight(self):
        result = TemplateStructureValidator.validate(
            {"resume_analysis": {"enabled": True, "weight": "ten"}}
        )
        assert not result.is_valid
        assert any(e.code == "INVALID_WEIGHT" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Topic section validation
# ─────────────────────────────────────────────────────────────────


class TestTopicSectionValidation:
    def test_invalid_difficulty_strategy(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {
                "enabled": True,
                "topics": [{"topic_id": 1, "difficulty_strategy": "random"}],
            }
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_DIFFICULTY_STRATEGY" for e in result.errors)

    def test_invalid_fixed_difficulty(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {
                "enabled": True,
                "topics": [
                    {"topic_id": 1, "difficulty_strategy": "fixed", "difficulty": "insane"}
                ],
            }
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_DIFFICULTY" for e in result.errors)

    def test_invalid_allowed_difficulties(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {
                "enabled": True,
                "topics": [
                    {
                        "topic_id": 1,
                        "difficulty_strategy": "dynamic",
                        "allowed_difficulties": ["easy", "legendary"],
                    }
                ],
            }
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_DIFFICULTY" for e in result.errors)

    def test_allowed_difficulties_not_list(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {
                "enabled": True,
                "topics": [
                    {"topic_id": 1, "allowed_difficulties": "easy"},
                ],
            }
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_ALLOWED_DIFFICULTIES_TYPE" for e in result.errors)

    def test_topics_not_list(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {"enabled": True, "topics": "not-a-list"}
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_TOPICS_TYPE" for e in result.errors)

    def test_negative_topic_weight(self):
        result = TemplateStructureValidator.validate({
            "topics_assessment": {
                "enabled": True,
                "topics": [{"topic_id": 1, "weight": -10}],
            }
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_WEIGHT" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Coding section validation
# ─────────────────────────────────────────────────────────────────


class TestCodingSectionValidation:
    def test_invalid_coding_difficulty(self):
        result = TemplateStructureValidator.validate({
            "coding_round": {"enabled": True, "difficulty": "nightmare"}
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_DIFFICULTY" for e in result.errors)

    def test_languages_not_list(self):
        result = TemplateStructureValidator.validate({
            "coding_round": {"enabled": True, "languages_allowed": "python"}
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_LANGUAGES_TYPE" for e in result.errors)

    def test_total_problems_zero(self):
        result = TemplateStructureValidator.validate({
            "coding_round": {"enabled": True, "total_problems": 0}
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_COUNT" for e in result.errors)

    def test_total_problems_negative(self):
        result = TemplateStructureValidator.validate({
            "coding_round": {"enabled": True, "total_problems": -1}
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_COUNT" for e in result.errors)

    def test_valid_coding_round(self):
        result = TemplateStructureValidator.validate({
            "coding_round": {
                "enabled": True,
                "total_problems": 2,
                "difficulty": "hard",
                "languages_allowed": ["python", "java"],
            }
        })
        assert result.is_valid


# ─────────────────────────────────────────────────────────────────
# Scoring validation
# ─────────────────────────────────────────────────────────────────


class TestScoringValidation:
    def test_valid_scoring(self):
        result = TemplateStructureValidator.validate({
            "resume_analysis": {"enabled": True},
            "scoring": {"strategy": "weighted_sum", "pass_threshold": 70},
        })
        assert result.is_valid

    def test_invalid_scoring_strategy(self):
        result = TemplateStructureValidator.validate({
            "resume_analysis": {"enabled": True},
            "scoring": {"strategy": "magic"},
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_SCORING_STRATEGY" for e in result.errors)

    def test_pass_threshold_out_of_range(self):
        result = TemplateStructureValidator.validate({
            "resume_analysis": {"enabled": True},
            "scoring": {"pass_threshold": 150},
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_PASS_THRESHOLD" for e in result.errors)

    def test_pass_threshold_negative(self):
        result = TemplateStructureValidator.validate({
            "resume_analysis": {"enabled": True},
            "scoring": {"pass_threshold": -10},
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_PASS_THRESHOLD" for e in result.errors)

    def test_scoring_not_dict(self):
        result = TemplateStructureValidator.validate({
            "resume_analysis": {"enabled": True},
            "scoring": "invalid",
        })
        assert not result.is_valid
        assert any(e.code == "INVALID_SCORING_TYPE" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Unknown section keys (v2 sections dict)
# ─────────────────────────────────────────────────────────────────


class TestUnknownSectionKeys:
    def test_unknown_section_key_in_v2(self):
        result = TemplateStructureValidator.validate({
            "sections": {
                "resume_analysis": {"enabled": True},
                "invented_section": {"enabled": True},
            }
        })
        # Should have at least one UNKNOWN_SECTION_KEY error
        assert any(e.code == "UNKNOWN_SECTION_KEY" for e in result.errors)

    def test_no_unknown_section_keys(self):
        result = TemplateStructureValidator.validate({
            "sections": {
                "resume_analysis": {"enabled": True},
                "coding_round": {"enabled": True},
            }
        })
        assert not any(e.code == "UNKNOWN_SECTION_KEY" for e in result.errors)


# ─────────────────────────────────────────────────────────────────
# Multiple errors accumulated
# ─────────────────────────────────────────────────────────────────


class TestMultipleErrors:
    def test_multiple_errors_collected(self):
        """Validation collects ALL errors, not just the first."""
        result = TemplateStructureValidator.validate({
            "coding_round": {
                "enabled": True,
                "difficulty": "impossible",
                "total_problems": -1,
                "languages_allowed": "python",
            }
        })
        assert not result.is_valid
        # Should have at least 3 errors
        assert len(result.errors) >= 3
