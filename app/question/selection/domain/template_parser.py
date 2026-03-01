"""
Template Snapshot Parser

Pure domain logic for parsing and validating frozen template snapshots.
No I/O, no DB calls, no FastAPI imports.

Template snapshot format (from REQUIREMENTS):
{
  "template_id": 42,
  "template_version": "v1.2.0",
  "sections": [
    {
      "section_name": "behavioral",
      "question_count": 3,
      "topic_constraints": ["communication"],
      "difficulty_range": ["easy", "medium"],
      "selection_strategy": "static_pool"
    },
    ...
  ],
  "difficulty_adaptation": {
    "enabled": true,
    "threshold_up": 80.0,
    "threshold_down": 50.0,
    "max_difficulty_jump": 1
  }
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.question.selection.contracts import (
    DifficultyAdaptationConfig,
    SectionConfig,
)


class TemplateSnapshotError(Exception):
    """Raised when template snapshot is malformed."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SectionCompleteError(Exception):
    """Raised when a section has no remaining questions."""

    def __init__(self, section_name: str, asked: int, total: int):
        self.section_name = section_name
        self.asked = asked
        self.total = total
        self.message = (
            f"Section '{section_name}' complete: "
            f"{asked}/{total} questions asked"
        )
        super().__init__(self.message)


def validate_template_snapshot(snapshot: Dict[str, Any]) -> None:
    """
    Validate template snapshot structure.

    Raises TemplateSnapshotError if malformed.
    """
    if not isinstance(snapshot, dict):
        raise TemplateSnapshotError("Template snapshot must be a dict")

    sections = snapshot.get("sections")
    if not sections:
        raise TemplateSnapshotError(
            "Template snapshot must contain non-empty 'sections' list"
        )

    if not isinstance(sections, list):
        raise TemplateSnapshotError("'sections' must be a list")

    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise TemplateSnapshotError(
                f"Section at index {i} must be a dict"
            )
        if "section_name" not in section:
            raise TemplateSnapshotError(
                f"Section at index {i} missing 'section_name'"
            )
        if "question_count" not in section:
            raise TemplateSnapshotError(
                f"Section '{section.get('section_name', i)}' "
                f"missing 'question_count'"
            )
        count = section["question_count"]
        if not isinstance(count, int) or count < 1:
            raise TemplateSnapshotError(
                f"Section '{section['section_name']}' "
                f"question_count must be a positive integer, got {count}"
            )


def find_section(
    snapshot: Dict[str, Any],
    section_name: str,
) -> Optional[SectionConfig]:
    """
    Find and parse a section from the template snapshot.

    Args:
        snapshot: Validated template snapshot.
        section_name: Section to find.

    Returns:
        SectionConfig if found, None otherwise.
    """
    sections = snapshot.get("sections", [])

    for section in sections:
        if section.get("section_name") == section_name:
            return SectionConfig(
                section_name=section["section_name"],
                question_count=section["question_count"],
                question_type=section.get("question_type", "technical"),
                topic_constraints=section.get("topic_constraints", []),
                difficulty_range=section.get("difficulty_range", ["medium"]),
                selection_strategy=section.get(
                    "selection_strategy", "static_pool"
                ),
                template_instructions=section.get("template_instructions"),
            )

    return None


def parse_adaptation_config(
    snapshot: Dict[str, Any],
) -> DifficultyAdaptationConfig:
    """
    Extract difficulty adaptation config from template snapshot.

    Falls back to sensible defaults if section is absent.
    """
    adaptation = snapshot.get("difficulty_adaptation", {})

    if not isinstance(adaptation, dict):
        return DifficultyAdaptationConfig()

    return DifficultyAdaptationConfig(
        enabled=adaptation.get("enabled", True),
        threshold_up=adaptation.get("threshold_up", 80.0),
        threshold_down=adaptation.get("threshold_down", 50.0),
        max_difficulty_jump=adaptation.get("max_difficulty_jump", 1),
    )


def count_section_exchanges(
    exchange_history: List[Dict[str, Any]],
    section_name: str,
) -> int:
    """
    Count how many exchanges belong to a given section.

    Args:
        exchange_history: List of exchange dicts.
        section_name: Section to count.

    Returns:
        Number of exchanges in the section.
    """
    return sum(
        1
        for e in exchange_history
        if e.get("section_name") == section_name
    )


def get_last_exchange_in_section(
    exchange_history: List[Dict[str, Any]],
    section_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Get the most recent exchange in a section (by sequence_order).

    Returns None if no exchanges in the section.
    """
    section_exchanges = [
        e
        for e in exchange_history
        if e.get("section_name") == section_name
    ]

    if not section_exchanges:
        return None

    return max(section_exchanges, key=lambda e: e.get("sequence_order", 0))
