"""
Unit Tests — Token Estimator

Tests token estimation, truncation, and sentence splitting.
No mocks, no I/O.
"""

import pytest

from app.question.prompting.tokens import TokenEstimator, _split_sentences


# ═══════════════════════════════════════════════════════════════════════
# TokenEstimator.estimate
# ═══════════════════════════════════════════════════════════════════════


class TestTokenEstimatorEstimate:
    """Tests for TokenEstimator.estimate()."""

    def test_empty_string_returns_zero(self):
        est = TokenEstimator(model="gpt-4")
        assert est.estimate("") == 0

    def test_nonempty_returns_positive(self):
        est = TokenEstimator(model="gpt-4")
        count = est.estimate("Hello, world!")
        assert count > 0

    def test_longer_text_more_tokens(self):
        est = TokenEstimator(model="gpt-4")
        short = est.estimate("Hello")
        long = est.estimate("Hello " * 100)
        assert long > short

    def test_single_word(self):
        est = TokenEstimator(model="gpt-4")
        count = est.estimate("test")
        assert count >= 1

    def test_whitespace_only(self):
        est = TokenEstimator(model="gpt-4")
        count = est.estimate("   ")
        assert count >= 0


class TestTokenEstimatorTruncate:
    """Tests for TokenEstimator.truncate_to_fit()."""

    def test_short_text_unchanged(self):
        est = TokenEstimator(model="gpt-4")
        result = est.truncate_to_fit("Hello world.", max_tokens=100)
        assert result == "Hello world."

    def test_long_text_truncated(self):
        est = TokenEstimator(model="gpt-4")
        # Create text that is definitely too long
        long_text = "This is a sentence. " * 200
        result = est.truncate_to_fit(long_text, max_tokens=20)
        assert len(result) < len(long_text)
        assert "[truncated]" in result

    def test_zero_budget_returns_empty(self):
        est = TokenEstimator(model="gpt-4")
        result = est.truncate_to_fit("Some text here.", max_tokens=0)
        assert result == ""

    def test_negative_budget_returns_empty(self):
        est = TokenEstimator(model="gpt-4")
        result = est.truncate_to_fit("Some text.", max_tokens=-5)
        assert result == ""

    def test_preserves_beginning(self):
        est = TokenEstimator(model="gpt-4")
        text = "First sentence here. Second sentence. Third sentence. Fourth."
        result = est.truncate_to_fit(text, max_tokens=5)
        # Should keep content from the beginning
        assert result.startswith("First")


# ═══════════════════════════════════════════════════════════════════════
# _split_sentences
# ═══════════════════════════════════════════════════════════════════════


class TestSplitSentences:
    """Tests for _split_sentences helper."""

    def test_single_sentence(self):
        result = _split_sentences("Hello world.")
        assert result == ["Hello world."]

    def test_multiple_sentences(self):
        result = _split_sentences("First. Second. Third.")
        assert len(result) == 3

    def test_question_marks(self):
        result = _split_sentences("What? Why? How?")
        assert len(result) == 3

    def test_exclamation_marks(self):
        result = _split_sentences("Wow! Amazing! Great!")
        assert len(result) == 3

    def test_no_punctuation(self):
        result = _split_sentences("No punctuation here")
        assert result == ["No punctuation here"]

    def test_empty_string(self):
        result = _split_sentences("")
        assert result == []

    def test_preserves_content(self):
        text = "First sentence. Second sentence."
        result = _split_sentences(text)
        assert "First sentence." in result
        assert "Second sentence." in result

