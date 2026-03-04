"""
Input Safety — Sanitization and Prompt Injection Detection

Protects against:
- HTML / XSS in candidate-provided resume / JD text
- Prompt injection patterns ("ignore previous instructions", etc.)
- Excessively long inputs

References:
- prompting/REQUIREMENTS.md §6 (Injection Safety)
"""

from __future__ import annotations

import html
import logging
import re
from typing import List, Tuple

from app.shared.errors import ValidationError

logger = logging.getLogger(__name__)

# Default injection patterns (compiled once at import time).
_INJECTION_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|all|the)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(previous|all|the)\s+(instructions?|prompts?|rules?)",
        r"you\s+are\s+now\s+\w+",
        r"new\s+instructions?\s+follow",
        r"forget\s+(everything|all|previous)",
        r"system\s*:\s*",
        r"assistant\s*:\s*",
    ]
]

# Maximum allowed input length (~12 500 tokens).
_MAX_INPUT_LENGTH = 50_000


class PromptInjectionError(ValidationError):
    """Raised when prompt injection is detected in user-provided text."""

    def __init__(
        self,
        message: str,
        *,
        matched_patterns: List[str] | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            field=field,
            metadata={"matched_patterns": matched_patterns or []},
        )
        self.matched_patterns = matched_patterns or []


# ─── Public API ────────────────────────────────────────────────────────


def sanitize_text(text: str, *, max_length: int = _MAX_INPUT_LENGTH) -> str:
    """
    Sanitize user-provided text for safe LLM prompt injection.

    Steps:
    1. Strip HTML tags and decode entities.
    2. Remove ``<script>`` / ``<style>`` blocks.
    3. Collapse excessive whitespace.
    4. Truncate to *max_length* characters.
    5. Remove null bytes.

    Args:
        text: Raw user-provided text (resume, JD, etc.).
        max_length: Maximum allowed character count.

    Returns:
        Sanitized text string.
    """
    if not text:
        return ""

    # Remove script / style blocks
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL
    )

    # Strip all HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities (e.g. &amp; → &)
    text = html.unescape(text)

    # Remove null bytes
    text = text.replace("\x00", "")

    # Collapse excessive whitespace (preserve single newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # Truncate
    if len(text) > max_length:
        logger.warning(
            "Input text truncated",
            extra={"original_length": len(text), "max_length": max_length},
        )
        text = text[:max_length] + " [truncated]"

    return text


def detect_prompt_injection(
    text: str,
    *,
    extra_patterns: List[str] | None = None,
) -> Tuple[bool, List[str]]:
    """
    Detect potential prompt injection attempts in text.

    Args:
        text: Text to scan.
        extra_patterns: Additional regex patterns to check (optional).

    Returns:
        ``(is_suspicious, matched_patterns)`` tuple.
    """
    matched: List[str] = []

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)

    if extra_patterns:
        for raw in extra_patterns:
            if re.search(raw, text, re.IGNORECASE):
                matched.append(raw)

    return (len(matched) > 0, matched)


def validate_input_safety(
    *,
    resume_text: str = "",
    job_description: str = "",
) -> None:
    """
    Validate that candidate-provided inputs are safe for prompt injection.

    Raises:
        PromptInjectionError: If suspicious patterns are detected.
    """
    for label, text in [("resume", resume_text), ("job_description", job_description)]:
        if not text:
            continue

        is_suspicious, patterns = detect_prompt_injection(text)
        if is_suspicious:
            logger.warning(
                "Prompt injection detected",
                extra={"field": label, "patterns": patterns},
            )
            raise PromptInjectionError(
                message=f"Suspicious content detected in {label}",
                matched_patterns=patterns,
                field=label,
            )
