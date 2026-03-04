"""
Token Estimation Utilities

Provides token-count estimation for prompt budget management.

Uses ``tiktoken`` when available, falling back to a character-based
heuristic (1 token ≈ 4 characters) when the library is not installed.

References:
- prompting/REQUIREMENTS.md §5.1 (Token estimation)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import tiktoken; fall back to heuristic if unavailable.
try:
    import tiktoken  # type: ignore[import-untyped]

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    logger.info(
        "tiktoken not installed — using character-based token estimation "
        "(pip install tiktoken for accurate counting)"
    )

# Rough character-to-token ratio (English text, cl100k_base)
_CHARS_PER_TOKEN = 4.0


class TokenEstimator:
    """
    Estimates token counts for text strings.

    Uses ``tiktoken`` encoding for the specified model when available;
    otherwise falls back to ``len(text) / 4``.
    """

    def __init__(self, model: str = "gpt-4") -> None:
        self._model = model
        self._encoding: Optional[object] = None

        if _TIKTOKEN_AVAILABLE:
            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Unknown model → use cl100k_base (GPT-4 / GPT-3.5)
                self._encoding = tiktoken.get_encoding("cl100k_base")

    def estimate(self, text: str) -> int:
        """
        Estimate the number of tokens in *text*.

        Returns:
            Estimated token count (always ≥ 0).
        """
        if not text:
            return 0

        if self._encoding is not None:
            return len(self._encoding.encode(text))  # type: ignore[union-attr]

        # Heuristic fallback
        return max(1, int(len(text) / _CHARS_PER_TOKEN))

    def truncate_to_fit(
        self,
        text: str,
        max_tokens: int,
    ) -> str:
        """
        Truncate *text* so its token count fits within *max_tokens*.

        Strategy: remove sentences from the end, preserving the beginning
        (most important context is usually at the start).

        Falls back to character-based truncation when sentence splitting
        is not possible.
        """
        if max_tokens <= 0:
            return ""

        if self.estimate(text) <= max_tokens:
            return text

        # Try sentence-level truncation
        sentences = _split_sentences(text)
        while len(sentences) > 1 and self.estimate(" ".join(sentences)) > max_tokens:
            sentences.pop()

        truncated = " ".join(sentences)

        # If even one sentence is still too long, fall back to character cut
        if self.estimate(truncated) > max_tokens:
            chars_budget = int(max_tokens * _CHARS_PER_TOKEN)
            truncated = text[:chars_budget]

        return truncated + " [truncated]"


def _split_sentences(text: str) -> list[str]:
    """
    Lightweight sentence splitter.

    Uses standard punctuation boundaries (. ! ?) followed by whitespace.
    Does not rely on NLTK.
    """
    import re

    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if p.strip()]
