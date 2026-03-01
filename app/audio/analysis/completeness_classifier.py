"""
Completeness Classifier

Rule-based sentence completeness classification using spaCy dependency parsing.

Algorithm:
  1. Handle edge cases (empty, single word)
  2. For multi-sentence transcripts, analyse last sentence only
  3. Parse with spaCy for dependency structure
  4. Check: punctuation, conjunction ending, dangling preposition,
     complete clause (subject + verb + complement)
  5. Return deterministic CompletenessResult

Invariants enforced:
  - Deterministic: same input → same output
  - Rule-based only: NO LLM calls
  - Read-only: transcript is NEVER modified
  - <500ms latency contribution

Does NOT:
  - Call any external service
  - Write to any database
  - Use any randomness
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

import spacy
from spacy.tokens import Doc

from app.shared.observability import get_context_logger

from .contracts import CompletenessResult
from .exceptions import SpacyModelNotFoundError

logger = get_context_logger(__name__)

# Transitive verbs that require a complement (direct object, attribute, etc.)
_TRANSITIVE_VERBS: Set[str] = frozenset({
    "be", "have",
    "think", "believe", "know", "consider", "find",
    "make", "take", "give", "get", "use",
})

# Common filler words (used to detect filler-only utterances)
_FILLER_WORDS: Set[str] = frozenset({
    "um", "uh", "umm", "uhh", "hmm", "so", "like",
    "basically", "actually", "well", "right", "okay",
})


class CompletenessClassifier:
    """
    Classifies whether a transcript represents a complete, incomplete,
    or continuing utterance using spaCy dependency parsing.

    Parameters
    ----------
    spacy_model : str
        Name of the spaCy model to load (default: ``en_core_web_sm``).
    """

    def __init__(self, spacy_model: str = "en_core_web_sm") -> None:
        try:
            self._nlp = spacy.load(spacy_model)
        except OSError:
            raise SpacyModelNotFoundError(spacy_model)

        logger.info(
            "CompletenessClassifier initialised",
            event_type="audio.analysis.completeness.init",
            metadata={"spacy_model": spacy_model},
        )

    def evaluate(self, transcript: str) -> CompletenessResult:
        """
        Evaluate sentence completeness of *transcript*.

        For multi-sentence transcripts, only the **last sentence** is analysed
        (previous sentences are assumed complete).

        Parameters
        ----------
        transcript : str
            The transcript text to evaluate.

        Returns
        -------
        CompletenessResult
            Frozen result with speech_state, confidence, and linguistic features.
        """
        # Edge case: empty / whitespace-only
        if not transcript or not transcript.strip():
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=1.0,
                incomplete_reason="empty_transcript",
            )

        transcript = transcript.strip()

        # For multi-sentence, analyse last sentence only
        doc = self._nlp(transcript)
        sentences = list(doc.sents)
        last_sent = sentences[-1] if sentences else doc

        return self._classify_sentence(last_sent, transcript)

    def _classify_sentence(self, sent: Doc, original_transcript: str) -> CompletenessResult:
        """Classify a single sentence span."""
        sent_text = sent.text.strip()

        # Edge case: single filler word or very short
        if not sent_text:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=1.0,
                incomplete_reason="empty_transcript",
            )

        # Extract features
        has_punctuation = sent_text[-1] in ".!?"
        ends_with_conjunction = self._ends_with_conjunction(sent)
        has_dangling_preposition = self._has_dangling_preposition(sent)
        has_complete_clause = self._has_complete_clause(sent)
        ends_incomplete_verb = self._ends_with_incomplete_verb(sent)
        filler_only = self._is_filler_only(sent)

        features: Dict[str, Any] = {
            "has_punctuation": has_punctuation,
            "ends_with_conjunction": ends_with_conjunction,
            "has_dangling_preposition": has_dangling_preposition,
            "has_complete_clause": has_complete_clause,
            "token_count": len(sent),
        }

        # Decision tree (ordered by specificity)
        # 1. Structural defects → incomplete
        if ends_with_conjunction:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.85,
                incomplete_reason="ends_with_conjunction",
                linguistic_features=features,
            )

        if has_dangling_preposition:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.8,
                incomplete_reason="dangling_preposition",
                linguistic_features=features,
            )

        if ends_incomplete_verb:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.75,
                incomplete_reason="missing_complement",
                linguistic_features=features,
            )

        # 2. Filler-only utterance → incomplete
        if filler_only:
            return CompletenessResult(
                speech_state="incomplete",
                sentence_complete=False,
                confidence=0.8,
                incomplete_reason="filler_only",
                linguistic_features=features,
            )

        # 3. Terminal punctuation → speaker done → complete
        if has_punctuation:
            return CompletenessResult(
                speech_state="complete",
                sentence_complete=True,
                confidence=0.9 if has_complete_clause else 0.7,
                linguistic_features=features,
            )

        # 4. No punctuation → still speaking → continuing
        return CompletenessResult(
            speech_state="continuing",
            sentence_complete=False,
            confidence=0.6,
            incomplete_reason="no_punctuation",
            linguistic_features=features,
        )

    # ------------------------------------------------------------------
    # Linguistic feature extraction
    # ------------------------------------------------------------------

    def _has_complete_clause(self, sent) -> bool:
        """
        Check if sentence has subject + verb + complement (if required).

        A clause is considered complete when it has:
        1. A subject (nsubj or nsubjpass)
        2. A verb (VERB or AUX — copula verbs like "is" are tagged AUX)
        3. A complement (dobj, attr, acomp, xcomp) if the verb is transitive
        """
        tokens = list(sent)
        has_subject = any(
            token.dep_ in ("nsubj", "nsubjpass") for token in tokens
        )
        has_verb = any(token.pos_ in ("VERB", "AUX") for token in tokens)

        if not (has_subject and has_verb):
            return False

        # Find root and check if complement is needed
        root_tokens = [t for t in tokens if t.dep_ == "ROOT"]
        if root_tokens:
            root = root_tokens[0]
            children_deps = {child.dep_ for child in root.children}
            complement_deps = {"dobj", "attr", "acomp", "xcomp", "ccomp", "oprd"}
            has_complement = bool(children_deps & complement_deps)

            if self._requires_complement(root) and not has_complement:
                return False

        return True

    def _ends_with_incomplete_verb(self, sent) -> bool:
        """Check if sentence ends with a verb/aux that needs a complement."""
        tokens = list(sent)
        if not tokens:
            return False

        last_token = tokens[-1]
        if last_token.is_punct and len(tokens) > 1:
            last_token = tokens[-2]

        if last_token.pos_ not in ("VERB", "AUX"):
            return False

        # If this verb already has a complement child, it is satisfied
        children_deps = {child.dep_ for child in last_token.children}
        complement_deps = {"dobj", "attr", "acomp", "xcomp", "ccomp", "oprd"}
        if children_deps & complement_deps:
            return False

        return self._requires_complement(last_token)

    def _is_filler_only(self, sent) -> bool:
        """Check if utterance is composed entirely of known filler words."""
        tokens = [
            t.text.lower()
            for t in sent
            if not t.is_punct and not t.is_space
        ]
        if not tokens:
            return True
        return all(t in _FILLER_WORDS for t in tokens)

    def _ends_with_conjunction(self, sent) -> bool:
        """Check if the last meaningful token is a conjunction."""
        tokens = list(sent)
        if not tokens:
            return False

        # Skip trailing whitespace tokens
        last_token = tokens[-1]
        # Strip trailing punctuation to check second-to-last
        if last_token.is_punct and len(tokens) > 1:
            last_token = tokens[-2]

        return last_token.pos_ in ("CCONJ", "SCONJ")

    def _has_dangling_preposition(self, sent) -> bool:
        """Check if the sentence ends with a preposition."""
        tokens = list(sent)
        if not tokens:
            return False

        last_token = tokens[-1]
        if last_token.is_punct and len(tokens) > 1:
            last_token = tokens[-2]

        return last_token.pos_ == "ADP"

    def _requires_complement(self, verb_token) -> bool:
        """Check if verb is transitive and requires a direct object / complement."""
        return verb_token.lemma_ in _TRANSITIVE_VERBS
