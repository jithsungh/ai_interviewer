"""
Filler Word Detector

Context-aware filler word detection using spaCy POS tagging.

Distinguishes between filler usage and legitimate word usage:
  - "I like Python" → "like" is a VERB, not a filler
  - "The answer is, like, dynamic programming" → "like" is a filler

Algorithm:
  1. Tokenise transcript
  2. For each token, check against filler word list
  3. If context_aware: use POS tags to filter false positives
  4. Calculate filler rate = filler_count / total_words
  5. Return FillerDetectionResult with positions

Invariants enforced:
  - Deterministic: same input → same output
  - Rule-based only: NO LLM calls
  - Read-only: transcript is NEVER modified
  - Filler rate always in [0.0, 1.0]

Does NOT:
  - Call any external service
  - Write to any database
  - Use any randomness
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

import spacy

from app.shared.observability import get_context_logger

from .contracts import FillerDetectionResult, FillerWord
from .exceptions import SpacyModelNotFoundError

logger = get_context_logger(__name__)

# Default filler words (single tokens)
_DEFAULT_FILLER_WORDS: frozenset = frozenset({
    "um", "uh", "umm", "uhh", "hmm",
    "like", "so", "basically", "actually",
})

# Multi-word fillers (checked as substrings after lowercasing)
_DEFAULT_MULTI_WORD_FILLERS: tuple = (
    "you know",
    "i think",
    "i mean",
)

# POS tags that indicate "like" is used as a verb, not a filler
_LIKE_VERB_DEPS: frozenset = frozenset({"ROOT", "conj", "advcl", "relcl", "ccomp", "xcomp"})


class FillerDetector:
    """
    Detects filler words in transcript text with optional context-aware
    disambiguation using spaCy POS tagging.

    Parameters
    ----------
    context_aware : bool
        When True, uses NLP to distinguish filler vs legitimate word
        (e.g. "like" as verb vs filler). Default True.
    filler_words : set[str] | None
        Custom single-token filler word set. If None, uses defaults.
    multi_word_fillers : tuple[str, ...] | None
        Custom multi-word filler phrases. If None, uses defaults.
    spacy_model : str
        spaCy model name for POS tagging. Only loaded when context_aware=True.
    """

    def __init__(
        self,
        context_aware: bool = True,
        filler_words: Optional[Set[str]] = None,
        multi_word_fillers: Optional[Tuple[str, ...]] = None,
        spacy_model: str = "en_core_web_sm",
    ) -> None:
        self._context_aware = context_aware
        self._filler_words = (
            frozenset(w.lower() for w in filler_words)
            if filler_words is not None
            else _DEFAULT_FILLER_WORDS
        )
        self._multi_word_fillers = (
            tuple(p.lower() for p in multi_word_fillers)
            if multi_word_fillers is not None
            else _DEFAULT_MULTI_WORD_FILLERS
        )

        self._nlp = None
        if self._context_aware:
            try:
                self._nlp = spacy.load(spacy_model)
            except OSError:
                raise SpacyModelNotFoundError(spacy_model)

        logger.info(
            "FillerDetector initialised",
            event_type="audio.analysis.filler.init",
            metadata={
                "context_aware": context_aware,
                "filler_word_count": len(self._filler_words),
            },
        )

    def detect(self, transcript: str) -> FillerDetectionResult:
        """
        Detect filler words in *transcript*.

        Parameters
        ----------
        transcript : str
            The transcript text to analyse.

        Returns
        -------
        FillerDetectionResult
            Frozen result with filler count, rate, and positions.
        """
        if not transcript or not transcript.strip():
            return FillerDetectionResult(
                filler_word_count=0,
                filler_rate=0.0,
                filler_positions=(),
            )

        transcript_clean = transcript.strip()
        words = transcript_clean.split()
        total_words = len(words)

        if total_words == 0:
            return FillerDetectionResult(
                filler_word_count=0,
                filler_rate=0.0,
                filler_positions=(),
            )

        fillers: List[FillerWord] = []

        if self._context_aware and self._nlp is not None:
            fillers = self._detect_context_aware(transcript_clean, words)
        else:
            fillers = self._detect_simple(words)

        # Add multi-word fillers
        multi_fillers = self._detect_multi_word(transcript_clean, words)
        fillers.extend(multi_fillers)

        # Deduplicate by position
        seen_positions: set = set()
        unique_fillers: List[FillerWord] = []
        for f in fillers:
            if f.position not in seen_positions:
                seen_positions.add(f.position)
                unique_fillers.append(f)

        filler_count = len(unique_fillers)
        filler_rate = filler_count / total_words if total_words > 0 else 0.0
        # Clamp to [0.0, 1.0]
        filler_rate = min(1.0, max(0.0, filler_rate))

        return FillerDetectionResult(
            filler_word_count=filler_count,
            filler_rate=filler_rate,
            filler_positions=tuple(unique_fillers),
        )

    # ------------------------------------------------------------------
    # Detection strategies
    # ------------------------------------------------------------------

    def _detect_simple(self, words: List[str]) -> List[FillerWord]:
        """Simple string-match detection without NLP context."""
        fillers: List[FillerWord] = []
        for idx, word in enumerate(words):
            cleaned = word.lower().strip(".,!?;:")
            if cleaned in self._filler_words:
                fillers.append(FillerWord(word=cleaned, position=idx))
        return fillers

    def _detect_context_aware(
        self, transcript: str, words: List[str]
    ) -> List[FillerWord]:
        """
        Context-aware detection using spaCy POS tagging.

        For ambiguous words (e.g. "like"), checks the POS tag:
        - VERB/AUX → not a filler (e.g. "I like Python")
        - INTJ/ADV/other → filler (e.g. "it's, like, hard")
        """
        doc = self._nlp(transcript)
        fillers: List[FillerWord] = []

        # Build word-to-index mapping from raw split
        # (spaCy tokenisation may differ from simple split)
        for token in doc:
            cleaned = token.text.lower().strip(".,!?;:")
            if cleaned not in self._filler_words:
                continue

            # Context check for ambiguous words
            if cleaned == "like":
                if self._is_like_verb(token):
                    continue

            # Map spaCy token back to word index in the original split
            word_idx = self._find_word_index(words, token.idx, transcript)
            fillers.append(FillerWord(word=cleaned, position=word_idx))

        return fillers

    def _detect_multi_word(
        self, transcript: str, words: List[str]
    ) -> List[FillerWord]:
        """Detect multi-word filler phrases."""
        fillers: List[FillerWord] = []
        lower_transcript = transcript.lower()

        for phrase in self._multi_word_fillers:
            start = 0
            while True:
                idx = lower_transcript.find(phrase, start)
                if idx == -1:
                    break
                # Calculate word position
                preceding_text = transcript[:idx]
                word_position = len(preceding_text.split()) if preceding_text.strip() else 0
                fillers.append(
                    FillerWord(word=phrase, position=word_position)
                )
                start = idx + len(phrase)

        return fillers

    # ------------------------------------------------------------------
    # Disambiguation helpers
    # ------------------------------------------------------------------

    def _is_like_verb(self, token) -> bool:
        """
        Determine if "like" is used as a verb (not filler).

        Heuristics:
        - POS == VERB → verb usage ("I like Python")
        - dep_ in ROOT/conj/etc. → verb in clause
        - Otherwise → likely filler
        """
        if token.pos_ == "VERB":
            return True
        if token.dep_ in _LIKE_VERB_DEPS and token.pos_ in ("VERB", "AUX"):
            return True
        return False

    def _find_word_index(
        self, words: List[str], char_offset: int, transcript: str
    ) -> int:
        """Map a character offset in the transcript to a word index in split()."""
        current_offset = 0
        for idx, word in enumerate(words):
            word_start = transcript.find(word, current_offset)
            word_end = word_start + len(word)
            if word_start <= char_offset < word_end:
                return idx
            current_offset = word_end
        # Fallback: estimate from character position
        return min(len(words) - 1, max(0, len(transcript[:char_offset].split()) - 1))
