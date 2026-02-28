"""
Template Structure Validator

Validates the ``template_structure`` JSONB field of interview templates.
Pure domain logic — no DB calls, no FastAPI imports.

The validator checks structural correctness based on the canonical template
schemas found in ``docs/sample_i_template.json`` and
``docs/comprehensive_interview_template.json``.

Supported template flavours:
  • "simple"  — flat sections (resume_analysis, topics_assessment, coding_round …)
  • "v2"      — nested ``sections`` dict with per-section config objects

Both flavours require at least one enabled section.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from app.shared.observability import get_context_logger

from .result import ValidationErrorDetail, ValidationResult

logger = get_context_logger(__name__)

# --------------------------------------------------------------------------
# Known section keys (union of both template flavours)
# --------------------------------------------------------------------------

_KNOWN_SECTION_KEYS: Set[str] = frozenset({
    "resume_analysis",
    "self_introduction",
    "topics_assessment",
    "behavioral_assessment",
    "technical_concepts",
    "system_design",
    "live_coding",
    "coding_round",
    "complexity_analysis",
    "closing_questions",
    "scoring",
})

# Sections where ``enabled`` is meaningful
_ENABLEABLE_SECTIONS: Set[str] = _KNOWN_SECTION_KEYS - {"scoring"}

# Allowed difficulty values (reuses DifficultyLevel enum values)
_VALID_DIFFICULTIES: Set[str] = {"easy", "medium", "hard"}

# Allowed difficulty strategies
_VALID_DIFFICULTY_STRATEGIES: Set[str] = {"fixed", "dynamic", "adaptive"}

# Allowed scoring strategies
_VALID_SCORING_STRATEGIES: Set[str] = {"weighted_sum", "average", "rubric_based"}


class TemplateStructureValidator:
    """
    Stateless validator for template_structure JSONB content.

    All methods are pure functions; the class groups them for namespacing.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @staticmethod
    def validate(template_structure: Dict[str, Any]) -> ValidationResult:
        """
        Run all structural checks on a template_structure dict.

        Returns a merged ``ValidationResult`` accumulating all errors.
        """
        if not isinstance(template_structure, dict):
            return ValidationResult.from_single(
                field="template_structure",
                message="template_structure must be a JSON object",
                code="INVALID_TYPE",
            )

        results: List[ValidationResult] = [
            TemplateStructureValidator._validate_has_sections(template_structure),
            TemplateStructureValidator._validate_section_keys(template_structure),
            TemplateStructureValidator._validate_sections_content(template_structure),
            TemplateStructureValidator._validate_scoring(template_structure),
        ]
        return ValidationResult.merge_all(*results)

    # ------------------------------------------------------------------
    # Internal rules
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_has_sections(structure: Dict[str, Any]) -> ValidationResult:
        """At least one enableable section must be present."""
        # v2 style: explicit ``sections`` key
        if "sections" in structure:
            sections = structure["sections"]
            if not isinstance(sections, dict) or len(sections) == 0:
                return ValidationResult.from_single(
                    field="template_structure.sections",
                    message="sections must be a non-empty object",
                    code="EMPTY_SECTIONS",
                )
            return ValidationResult.success()

        # simple style: top-level keys are sections
        section_keys = set(structure.keys()) & _ENABLEABLE_SECTIONS
        if not section_keys:
            return ValidationResult.from_single(
                field="template_structure",
                message="Template must contain at least one section (e.g. resume_analysis, coding_round)",
                code="NO_SECTIONS",
            )
        return ValidationResult.success()

    @staticmethod
    def _validate_section_keys(structure: Dict[str, Any]) -> ValidationResult:
        """
        Warn about unknown top-level keys that are not recognised sections.

        This is advisory — unknown keys produce an UNKNOWN_SECTION_KEY error
        to catch typos, but the template is not rejected solely for this.
        (Templates may contain metadata keys like ``$schema``, ``template_metadata``
        ``interview_structure`` which are informational.)
        """
        # Only validate section keys in simple mode
        if "sections" in structure:
            sections_dict = structure.get("sections", {})
            if isinstance(sections_dict, dict):
                unknown = set(sections_dict.keys()) - _KNOWN_SECTION_KEYS
                errors = [
                    ValidationErrorDetail(
                        field=f"template_structure.sections.{k}",
                        message=f"Unknown section key '{k}'",
                        code="UNKNOWN_SECTION_KEY",
                    )
                    for k in sorted(unknown)
                ]
                return ValidationResult.failure(errors) if errors else ValidationResult.success()
        return ValidationResult.success()

    @staticmethod
    def _validate_sections_content(structure: Dict[str, Any]) -> ValidationResult:
        """Validate individual section configurations."""
        errors: List[ValidationErrorDetail] = []

        # Resolve sections dict
        sections: Dict[str, Any]
        if "sections" in structure and isinstance(structure["sections"], dict):
            sections = structure["sections"]
            prefix = "template_structure.sections"
        else:
            sections = {k: v for k, v in structure.items() if k in _ENABLEABLE_SECTIONS}
            prefix = "template_structure"

        has_enabled = False
        for key, section in sections.items():
            if not isinstance(section, dict):
                errors.append(ValidationErrorDetail(
                    field=f"{prefix}.{key}",
                    message=f"Section '{key}' must be a JSON object",
                    code="INVALID_SECTION_TYPE",
                ))
                continue

            enabled = section.get("enabled", True)
            if enabled:
                has_enabled = True

            # weight validation (if present)
            weight = section.get("weight")
            if weight is not None:
                if not isinstance(weight, (int, float)) or weight < 0:
                    errors.append(ValidationErrorDetail(
                        field=f"{prefix}.{key}.weight",
                        message=f"Section '{key}' weight must be a non-negative number",
                        code="INVALID_WEIGHT",
                    ))

            # topics_assessment / behavioral_assessment: validate topic list
            if key in ("topics_assessment", "behavioral_assessment"):
                errors.extend(
                    TemplateStructureValidator._validate_topic_section(
                        section, f"{prefix}.{key}"
                    )
                )

            # coding_round / live_coding: validate coding config
            if key in ("coding_round", "live_coding"):
                errors.extend(
                    TemplateStructureValidator._validate_coding_section(
                        section, f"{prefix}.{key}"
                    )
                )

        if not has_enabled:
            errors.append(ValidationErrorDetail(
                field=prefix,
                message="At least one section must be enabled",
                code="NO_ENABLED_SECTIONS",
            ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()

    @staticmethod
    def _validate_topic_section(
        section: Dict[str, Any], prefix: str
    ) -> List[ValidationErrorDetail]:
        """Validate topics list within a topics/behavioral section."""
        errors: List[ValidationErrorDetail] = []

        topics = section.get("topics")
        # Topics may be in question_config.topics (v2) or directly on section (simple)
        if topics is None:
            qconfig = section.get("question_config", {})
            if isinstance(qconfig, dict):
                topics = qconfig.get("topics")

        if topics is None:
            # No topics key at all — not necessarily invalid (selection_strategy may handle it)
            return errors

        if not isinstance(topics, list):
            errors.append(ValidationErrorDetail(
                field=f"{prefix}.topics",
                message="topics must be an array",
                code="INVALID_TOPICS_TYPE",
            ))
            return errors

        for idx, topic_entry in enumerate(topics):
            if isinstance(topic_entry, dict):
                # Validate difficulty_strategy if present
                strategy = topic_entry.get("difficulty_strategy")
                if strategy is not None and strategy not in _VALID_DIFFICULTY_STRATEGIES:
                    errors.append(ValidationErrorDetail(
                        field=f"{prefix}.topics[{idx}].difficulty_strategy",
                        message=f"Invalid difficulty_strategy '{strategy}'. "
                                f"Allowed: {sorted(_VALID_DIFFICULTY_STRATEGIES)}",
                        code="INVALID_DIFFICULTY_STRATEGY",
                    ))

                # Validate fixed difficulty value
                if strategy == "fixed":
                    diff = topic_entry.get("difficulty")
                    if diff is not None and diff not in _VALID_DIFFICULTIES:
                        errors.append(ValidationErrorDetail(
                            field=f"{prefix}.topics[{idx}].difficulty",
                            message=f"Invalid difficulty '{diff}'. "
                                    f"Allowed: {sorted(_VALID_DIFFICULTIES)}",
                            code="INVALID_DIFFICULTY",
                        ))

                # Validate allowed_difficulties list
                allowed = topic_entry.get("allowed_difficulties")
                if allowed is not None:
                    if not isinstance(allowed, list):
                        errors.append(ValidationErrorDetail(
                            field=f"{prefix}.topics[{idx}].allowed_difficulties",
                            message="allowed_difficulties must be an array",
                            code="INVALID_ALLOWED_DIFFICULTIES_TYPE",
                        ))
                    else:
                        invalid = set(allowed) - _VALID_DIFFICULTIES
                        if invalid:
                            errors.append(ValidationErrorDetail(
                                field=f"{prefix}.topics[{idx}].allowed_difficulties",
                                message=f"Invalid difficulties: {sorted(invalid)}. "
                                        f"Allowed: {sorted(_VALID_DIFFICULTIES)}",
                                code="INVALID_DIFFICULTY",
                            ))

                # Weight validation
                w = topic_entry.get("weight")
                if w is not None and (not isinstance(w, (int, float)) or w < 0):
                    errors.append(ValidationErrorDetail(
                        field=f"{prefix}.topics[{idx}].weight",
                        message="Topic weight must be a non-negative number",
                        code="INVALID_WEIGHT",
                    ))

            # topic_entry may also be a string (topic_name) in v2 — that's valid
        return errors

    @staticmethod
    def _validate_coding_section(
        section: Dict[str, Any], prefix: str
    ) -> List[ValidationErrorDetail]:
        """Validate coding round / live coding section config."""
        errors: List[ValidationErrorDetail] = []

        # Difficulty validation
        diff = section.get("difficulty")
        if diff is not None and diff not in _VALID_DIFFICULTIES:
            errors.append(ValidationErrorDetail(
                field=f"{prefix}.difficulty",
                message=f"Invalid difficulty '{diff}'. Allowed: {sorted(_VALID_DIFFICULTIES)}",
                code="INVALID_DIFFICULTY",
            ))

        # languages_allowed validation
        langs = section.get("languages_allowed")
        if langs is not None and not isinstance(langs, list):
            errors.append(ValidationErrorDetail(
                field=f"{prefix}.languages_allowed",
                message="languages_allowed must be an array",
                code="INVALID_LANGUAGES_TYPE",
            ))

        # total_problems / question_count positive integer
        for count_key in ("total_problems", "question_count"):
            val = section.get(count_key)
            if val is not None:
                if not isinstance(val, int) or val < 1:
                    errors.append(ValidationErrorDetail(
                        field=f"{prefix}.{count_key}",
                        message=f"{count_key} must be a positive integer",
                        code="INVALID_COUNT",
                    ))

        return errors

    @staticmethod
    def _validate_scoring(structure: Dict[str, Any]) -> ValidationResult:
        """Validate scoring configuration if present."""
        scoring = structure.get("scoring")
        if scoring is None:
            # scoring in v2 may be in sections
            sections = structure.get("sections", {})
            if isinstance(sections, dict):
                scoring = sections.get("scoring")

        if scoring is None:
            return ValidationResult.success()

        if not isinstance(scoring, dict):
            return ValidationResult.from_single(
                field="template_structure.scoring",
                message="scoring must be a JSON object",
                code="INVALID_SCORING_TYPE",
            )

        errors: List[ValidationErrorDetail] = []

        strategy = scoring.get("strategy")
        if strategy is not None and strategy not in _VALID_SCORING_STRATEGIES:
            errors.append(ValidationErrorDetail(
                field="template_structure.scoring.strategy",
                message=f"Invalid scoring strategy '{strategy}'. "
                        f"Allowed: {sorted(_VALID_SCORING_STRATEGIES)}",
                code="INVALID_SCORING_STRATEGY",
            ))

        threshold = scoring.get("pass_threshold")
        if threshold is not None:
            if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 100:
                errors.append(ValidationErrorDetail(
                    field="template_structure.scoring.pass_threshold",
                    message="pass_threshold must be a number between 0 and 100",
                    code="INVALID_PASS_THRESHOLD",
                ))

        return ValidationResult.failure(errors) if errors else ValidationResult.success()
