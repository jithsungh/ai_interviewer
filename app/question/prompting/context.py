"""
Context Prioritization

Fits prompt context pieces within a token budget, prioritizing essential
over optional content.

Priority order (from REQUIREMENTS.md §2.2):
1. Template instructions  (always included)
2. Difficulty + topic     (always included)
3. Previous exchanges     (recent 3-5, trimmed if needed)
4. Job description        (if fits)
5. Resume text            (if fits, truncated from end)

References:
- prompting/REQUIREMENTS.md §5.2 (Context prioritization)
- prompting/REQUIREMENTS.md §5.3 (Safe truncation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.question.prompting.tokens import TokenEstimator

logger = logging.getLogger(__name__)


@dataclass
class ContextPiece:
    """
    A named piece of context to inject into the prompt.

    Pieces are processed in ``priority`` order (lower = higher priority).
    ``required=True`` pieces are always included even if they must be truncated.
    """

    name: str
    value: str
    priority: int
    required: bool = False
    truncated: bool = False


def prioritize_context(
    *,
    template_instructions: str,
    difficulty: str,
    topic: str,
    previous_exchanges: Optional[List[str]] = None,
    job_description: Optional[str] = None,
    resume_text: Optional[str] = None,
    max_tokens: int = 7500,
    token_model: str = "gpt-4",
    max_previous_exchanges: int = 5,
) -> Dict[str, str]:
    """
    Fit context pieces within a token budget.

    Returns a ``{placeholder_name: value}`` dict ready for template substitution.
    Lower-priority items are dropped or truncated first.

    Args:
        template_instructions: Always included (priority 1).
        difficulty: Always included (priority 2).
        topic: Always included (priority 2).
        previous_exchanges: Past question summaries (priority 3).
        job_description: JD text (priority 4).
        resume_text: Candidate resume text (priority 5).
        max_tokens: Token budget.
        token_model: Model name for token estimation.
        max_previous_exchanges: Max exchange entries to consider.

    Returns:
        Dict mapping placeholder names to (possibly truncated) values.
    """
    estimator = TokenEstimator(model=token_model)

    result: Dict[str, str] = {}
    truncated_fields: List[str] = []

    # ── Priority 1 & 2: Essential context (always included) ─────

    result["template_instructions"] = template_instructions
    result["difficulty"] = difficulty
    result["topic"] = topic

    essential_text = f"{template_instructions} {difficulty} {topic}"
    remaining = max_tokens - estimator.estimate(essential_text)

    if remaining <= 0:
        logger.warning(
            "Essential context exceeds token budget",
            extra={"essential_tokens": estimator.estimate(essential_text), "budget": max_tokens},
        )
        # Still return essentials — caller will validate total
        result["previous_topics"] = ""
        result["job_description"] = ""
        result["resume_truncated"] = "[Resume omitted due to token limit]"
        return result

    # ── Priority 3: Previous exchanges ──────────────────────────

    if previous_exchanges:
        summaries = previous_exchanges[:max_previous_exchanges]
        summary_text = "\n".join(summaries)
        tokens_needed = estimator.estimate(summary_text)

        if tokens_needed <= remaining:
            result["previous_topics"] = summary_text
            remaining -= tokens_needed
        else:
            # Truncate to fit
            truncated = estimator.truncate_to_fit(summary_text, remaining)
            result["previous_topics"] = truncated
            remaining = 0
            truncated_fields.append("previous_topics")
    else:
        result["previous_topics"] = ""

    # ── Priority 4: Job description ─────────────────────────────

    if remaining > 0 and job_description:
        jd_tokens = estimator.estimate(job_description)
        if jd_tokens <= remaining:
            result["job_description"] = job_description
            remaining -= jd_tokens
        else:
            truncated = estimator.truncate_to_fit(job_description, remaining)
            result["job_description"] = truncated
            remaining = 0
            truncated_fields.append("job_description")
    else:
        result["job_description"] = job_description or ""

    # ── Priority 5: Resume ──────────────────────────────────────

    if remaining > 0 and resume_text:
        resume_tokens = estimator.estimate(resume_text)
        if resume_tokens <= remaining:
            result["resume_truncated"] = resume_text
        else:
            truncated = estimator.truncate_to_fit(resume_text, remaining)
            result["resume_truncated"] = truncated
            truncated_fields.append("resume_truncated")
    else:
        result["resume_truncated"] = (
            resume_text or "[Resume omitted due to token limit]"
            if remaining <= 0
            else resume_text or ""
        )

    if truncated_fields:
        logger.info(
            "Context fields truncated to fit token budget",
            extra={
                "truncated_fields": truncated_fields,
                "remaining_tokens": remaining,
            },
        )

    return result
