"""
LLM Response Parsing

Parses and validates the JSON response returned by the LLM provider.
Pure domain logic — no I/O, no framework imports.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.question.generation.domain.entities import GeneratedQuestionOutput

logger = logging.getLogger(__name__)

_VALID_DIFFICULTIES = frozenset({"easy", "medium", "hard"})

_VALID_ANSWER_TYPES = frozenset(
    {"conceptual", "analytical", "design", "coding", "behavioral"}
)


class ResponseParseError(Exception):
    """Raised when LLM response cannot be parsed into a valid question output."""

    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.raw_text = raw_text


def parse_llm_response(raw_text: str) -> GeneratedQuestionOutput:
    """
    Parse raw LLM text into a GeneratedQuestionOutput.

    Raises:
        ResponseParseError on any parse / validation failure.
    """
    if not raw_text or not raw_text.strip():
        raise ResponseParseError("LLM returned empty response", raw_text)

    # Strip markdown fences if the LLM wraps in ```json...```
    cleaned = _strip_markdown_fences(raw_text)

    # Parse JSON
    try:
        data: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(
            f"Invalid JSON from LLM: {exc}", raw_text
        ) from exc

    # Validate required fields
    _require_field(data, "question_text", str, raw_text)
    _require_field(data, "difficulty", str, raw_text)

    # Normalise difficulty
    difficulty = data["difficulty"].strip().lower()
    if difficulty not in _VALID_DIFFICULTIES:
        raise ResponseParseError(
            f"difficulty must be one of {_VALID_DIFFICULTIES}, got '{difficulty}'",
            raw_text,
        )

    # Extract optional fields with safe defaults
    expected_answer = data.get("expected_answer_outline") or data.get(
        "expected_answer", ""
    )
    topic = data.get("topic", "")
    subtopic = data.get("subtopic")
    skill_tags = data.get("skill_tags", [])
    if not isinstance(skill_tags, list):
        skill_tags = []
    expected_answer_type = data.get("expected_answer_type")
    if expected_answer_type and expected_answer_type not in _VALID_ANSWER_TYPES:
        expected_answer_type = None

    estimated_minutes = data.get("estimated_answer_minutes")
    estimated_seconds = data.get("estimated_time_seconds")
    if estimated_seconds and isinstance(estimated_seconds, (int, float)):
        est_time = int(estimated_seconds)
    elif estimated_minutes and isinstance(estimated_minutes, (int, float)):
        est_time = int(estimated_minutes * 60)
    else:
        est_time = 120  # default 2 min

    followup = data.get("followup_suggestions", [])
    if not isinstance(followup, list):
        followup = []

    return GeneratedQuestionOutput(
        question_text=data["question_text"].strip(),
        expected_answer=str(expected_answer).strip(),
        difficulty=difficulty,
        topic=str(topic).strip(),
        subtopic=subtopic.strip() if subtopic else None,
        skill_tags=[str(t).strip() for t in skill_tags],
        expected_answer_type=expected_answer_type,
        estimated_time_seconds=max(30, min(est_time, 900)),
        followup_suggestions=[str(f).strip() for f in followup],
    )


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _strip_markdown_fences(text: str) -> str:
    """Remove optional ```json ... ``` wrapper."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove first line
        lines = stripped.splitlines()
        lines = lines[1:]  # drop ```json
        # Remove trailing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _require_field(
    data: Dict[str, Any],
    field: str,
    expected_type: type,
    raw_text: str,
) -> None:
    if field not in data:
        raise ResponseParseError(f"Missing required field: {field}", raw_text)
    if not isinstance(data[field], expected_type):
        raise ResponseParseError(
            f"Field '{field}' must be {expected_type.__name__}, "
            f"got {type(data[field]).__name__}",
            raw_text,
        )
