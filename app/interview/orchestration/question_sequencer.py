"""
Question Sequencer — Deterministic Question Resolution from Template Snapshot

Pure domain logic — no I/O, no framework dependencies.

Resolves the next question by flattening the template snapshot's section
structure into a contiguous sequence. The template snapshot is FROZEN at
interview creation time and NEVER dynamically resolved.

Critical invariant: MUST use template_structure_snapshot (JSONB, frozen).
MUST NOT use dynamic JOIN to interview_templates table.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.interview.orchestration.contracts import (
    NextQuestionResult,
    TemplateSnapshot,
)
from app.interview.orchestration.errors import (
    InterviewCompleteError,
    TemplateSnapshotInvalidError,
    TemplateSnapshotMissingError,
)

logger = logging.getLogger(__name__)


def validate_template_snapshot(
    raw_snapshot: Any,
    submission_id: int,
) -> TemplateSnapshot:
    """
    Parse and validate a raw template snapshot (from JSONB column).

    Args:
        raw_snapshot: Raw value from ``interview_submissions.template_structure_snapshot``.
        submission_id: Submission ID (for error context).

    Returns:
        Validated ``TemplateSnapshot`` instance.

    Raises:
        TemplateSnapshotMissingError: If snapshot is None.
        TemplateSnapshotInvalidError: If snapshot structure is invalid.
    """
    if raw_snapshot is None:
        raise TemplateSnapshotMissingError(submission_id=submission_id)

    if not isinstance(raw_snapshot, dict):
        raise TemplateSnapshotInvalidError(
            submission_id=submission_id,
            reason=f"Expected dict, got {type(raw_snapshot).__name__}",
        )

    try:
        return TemplateSnapshot.model_validate(raw_snapshot)
    except Exception as e:
        raise TemplateSnapshotInvalidError(
            submission_id=submission_id,
            reason=str(e),
        )


def resolve_next_question(
    template_snapshot: TemplateSnapshot,
    current_sequence: int,
) -> Optional[NextQuestionResult]:
    """
    Resolve the next question from a frozen template snapshot.

    Flattens the section structure into a contiguous sequence:
    - Section 1: question_ids[0..n] → sequence 0..(n-1)
    - Section 2: question_ids[0..m] → sequence n..(n+m-1)
    - etc.

    Args:
        template_snapshot: Validated frozen template structure.
        current_sequence: Current exchange sequence (0-indexed).
            0 means no exchanges yet, 1 means first exchange done, etc.

    Returns:
        ``NextQuestionResult`` if more questions remain, ``None`` if all
        questions are complete.

    Raises:
        ValueError: If sequencing logic encounters an inconsistency.
    """
    total_questions = template_snapshot.total_questions

    # Check if all questions answered
    if current_sequence >= total_questions:
        return None

    # Flatten sections into contiguous sequence
    question_index = 0
    for section in template_snapshot.sections:
        section_count = section.question_count

        if question_index + section_count > current_sequence:
            # Target question is in this section
            local_index = current_sequence - question_index
            question_id = section.question_ids[local_index]

            return NextQuestionResult(
                question_id=question_id,
                sequence_order=current_sequence + 1,  # 1-indexed for persistence
                section_name=section.section_name,
                is_final_question=(current_sequence == total_questions - 1),
            )

        question_index += section_count

    # Should never reach here if total_questions is correct
    # (validated by TemplateSnapshot.model_post_init)
    raise ValueError(
        f"Question sequencing error: current_sequence={current_sequence} "
        f"exceeded traversal of {question_index} questions across "
        f"{len(template_snapshot.sections)} sections"
    )


def get_total_questions(template_snapshot: TemplateSnapshot) -> int:
    """Return total question count from snapshot."""
    return template_snapshot.total_questions


def get_section_for_sequence(
    template_snapshot: TemplateSnapshot,
    sequence: int,
) -> Optional[str]:
    """
    Return the section name for a given 0-indexed sequence number.

    Args:
        template_snapshot: Validated frozen template structure.
        sequence: 0-indexed sequence number.

    Returns:
        Section name, or None if sequence is out of range.
    """
    question_index = 0
    for section in template_snapshot.sections:
        section_count = section.question_count
        if question_index + section_count > sequence:
            return section.section_name
        question_index += section_count
    return None
