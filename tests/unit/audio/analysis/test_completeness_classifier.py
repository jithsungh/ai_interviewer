"""
Unit tests for CompletenessClassifier.

Covers: complete sentences, incomplete sentences, continuing utterances,
edge cases, determinism, and accuracy on test corpus.
"""

import json
from pathlib import Path

import pytest

from app.audio.analysis.completeness_classifier import CompletenessClassifier


@pytest.fixture(scope="module")
def classifier():
    """Module-scoped fixture — spaCy model loaded once."""
    return CompletenessClassifier()


# ---------------------------------------------------------------------------
# Complete Sentences
# ---------------------------------------------------------------------------


class TestCompleteSentences:

    def test_complete_with_period(self, classifier):
        result = classifier.evaluate("The answer is dynamic programming.")
        assert result.speech_state == "complete"
        assert result.sentence_complete is True
        assert result.confidence > 0.8

    def test_complete_with_question_mark(self, classifier):
        result = classifier.evaluate("Is this the right answer?")
        assert result.speech_state == "complete"
        assert result.sentence_complete is True

    def test_complete_with_exclamation(self, classifier):
        result = classifier.evaluate("That is correct!")
        assert result.speech_state == "complete"
        assert result.sentence_complete is True

    def test_technical_jargon(self, classifier):
        result = classifier.evaluate("I used DFS to traverse the graph.")
        assert result.speech_state == "complete"

    def test_single_word_with_punctuation(self, classifier):
        result = classifier.evaluate("Yes.")
        assert result.speech_state == "complete"
        assert result.confidence > 0.5


# ---------------------------------------------------------------------------
# Incomplete Sentences
# ---------------------------------------------------------------------------


class TestIncompleteSentences:

    def test_ends_with_conjunction(self, classifier):
        result = classifier.evaluate("The answer is correct because")
        assert result.speech_state == "incomplete"
        assert result.sentence_complete is False
        assert result.incomplete_reason == "ends_with_conjunction"

    def test_missing_complement(self, classifier):
        result = classifier.evaluate("I think the answer is")
        assert result.speech_state == "incomplete"
        assert result.sentence_complete is False

    def test_dangling_preposition(self, classifier):
        result = classifier.evaluate("The answer depends on")
        assert result.speech_state == "incomplete"
        assert result.incomplete_reason == "dangling_preposition"

    def test_empty_transcript(self, classifier):
        result = classifier.evaluate("")
        assert result.speech_state == "incomplete"
        assert result.incomplete_reason == "empty_transcript"
        assert result.confidence == 1.0

    def test_whitespace_only(self, classifier):
        result = classifier.evaluate("   ")
        assert result.speech_state == "incomplete"
        assert result.incomplete_reason == "empty_transcript"

    def test_only_fillers(self, classifier):
        result = classifier.evaluate("Um uh so")
        assert result.speech_state == "incomplete"


# ---------------------------------------------------------------------------
# Continuing Utterances
# ---------------------------------------------------------------------------


class TestContinuingUtterances:

    def test_single_word_no_punctuation(self, classifier):
        result = classifier.evaluate("Yes")
        assert result.speech_state == "continuing"
        assert result.confidence < 0.7

    def test_structurally_complete_no_punctuation(self, classifier):
        """Structurally complete but no terminal punctuation."""
        result = classifier.evaluate("The algorithm works well")
        assert 0.5 < result.confidence < 0.8


# ---------------------------------------------------------------------------
# Multi-Sentence
# ---------------------------------------------------------------------------


class TestMultiSentence:

    def test_last_sentence_analysed(self, classifier):
        """Only last sentence matters for completeness."""
        result = classifier.evaluate("First sentence. Second sentence")
        # Last sentence has no punctuation → continuing
        assert result.speech_state == "continuing"

    def test_all_complete(self, classifier):
        result = classifier.evaluate("First sentence. Second sentence.")
        assert result.speech_state == "complete"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_same_output(self, classifier):
        transcript = "The answer is dynamic programming."
        result1 = classifier.evaluate(transcript)
        result2 = classifier.evaluate(transcript)

        assert result1.speech_state == result2.speech_state
        assert result1.confidence == result2.confidence
        assert result1.sentence_complete == result2.sentence_complete
        assert result1.incomplete_reason == result2.incomplete_reason

    def test_determinism_incomplete(self, classifier):
        transcript = "The answer is because"
        result1 = classifier.evaluate(transcript)
        result2 = classifier.evaluate(transcript)

        assert result1.speech_state == result2.speech_state
        assert result1.confidence == result2.confidence


# ---------------------------------------------------------------------------
# Accuracy on Test Corpus
# ---------------------------------------------------------------------------


class TestAccuracy:

    @pytest.fixture
    def test_corpus(self):
        corpus_path = (
            Path(__file__).parent.parent.parent.parent
            / "fixtures"
            / "audio"
            / "completeness_test_corpus.json"
        )
        with open(corpus_path) as f:
            return json.load(f)

    def test_classifier_accuracy_above_85_percent(self, classifier, test_corpus):
        """Completeness classifier must achieve >85% accuracy on test corpus."""
        correct = 0
        total = len(test_corpus)

        for example in test_corpus:
            transcript = example["transcript"]
            expected = example["expected_state"]

            result = classifier.evaluate(transcript)

            # Map: "complete" is "complete", everything else is "incomplete"
            actual = "complete" if result.speech_state == "complete" else "incomplete"
            if actual == expected:
                correct += 1

        accuracy = correct / total if total > 0 else 0.0
        assert accuracy > 0.85, (
            f"Classifier accuracy {accuracy:.2%} ({correct}/{total}) "
            f"below 85% threshold"
        )
