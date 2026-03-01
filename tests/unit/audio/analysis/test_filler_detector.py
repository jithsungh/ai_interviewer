"""
Unit tests for FillerDetector.

Covers: common filler detection, context-aware disambiguation,
filler rate calculation, custom filler words, positions, and edge cases.
"""

import pytest

from app.audio.analysis.filler_detector import FillerDetector


@pytest.fixture(scope="module")
def detector():
    """Context-aware detector with default settings."""
    return FillerDetector(context_aware=True)


@pytest.fixture(scope="module")
def simple_detector():
    """Simple (non-context-aware) detector."""
    return FillerDetector(context_aware=False)


# ---------------------------------------------------------------------------
# Common Filler Detection
# ---------------------------------------------------------------------------


class TestCommonFillers:

    def test_common_fillers_detected(self, detector):
        result = detector.detect(
            "Um, I think, uh, the answer is, like, dynamic programming."
        )
        assert result.filler_word_count >= 3
        filler_words = [f.word for f in result.filler_positions]
        assert "um" in filler_words
        assert "uh" in filler_words

    def test_no_fillers_clean_transcript(self, detector):
        result = detector.detect("The algorithm uses dynamic programming.")
        assert result.filler_word_count == 0
        assert result.filler_rate == 0.0

    def test_consecutive_fillers(self, detector):
        result = detector.detect("Um uh like")
        assert result.filler_word_count >= 3

    def test_empty_transcript(self, detector):
        result = detector.detect("")
        assert result.filler_word_count == 0
        assert result.filler_rate == 0.0

    def test_whitespace_only(self, detector):
        result = detector.detect("   ")
        assert result.filler_word_count == 0


# ---------------------------------------------------------------------------
# Context-Aware Disambiguation
# ---------------------------------------------------------------------------


class TestContextAware:

    def test_like_as_verb_not_filler(self, detector):
        """'like' as a verb should NOT be counted as filler."""
        result = detector.detect("I like Python programming.")
        # "like" here is a verb
        filler_words = [f.word for f in result.filler_positions]
        assert "like" not in filler_words

    def test_like_as_filler_detected(self, detector):
        """'like' as a filler SHOULD be detected."""
        result = detector.detect("The answer is, like, dynamic programming.")
        assert result.filler_word_count >= 1
        filler_words = [f.word for f in result.filler_positions]
        assert "like" in filler_words


# ---------------------------------------------------------------------------
# Filler Rate Calculation
# ---------------------------------------------------------------------------


class TestFillerRate:

    def test_filler_rate_calculation(self, simple_detector):
        # "Um so uh basically" = 4 fillers, "the answer is bubble sort" = 5 non-fillers
        # Total: 9 words, 4 fillers → rate ~0.44
        result = simple_detector.detect(
            "Um so uh basically the answer is bubble sort"
        )
        assert result.filler_word_count >= 3
        assert 0.2 < result.filler_rate < 0.6

    def test_all_fillers_rate_one(self, simple_detector):
        """All-filler transcript → rate = 1.0."""
        result = simple_detector.detect("Um uh like so basically")
        assert result.filler_rate == pytest.approx(1.0, abs=0.01)

    def test_rate_always_bounded(self, detector):
        """Filler rate always in [0.0, 1.0]."""
        result = detector.detect("Some random text with um and uh here")
        assert 0.0 <= result.filler_rate <= 1.0


# ---------------------------------------------------------------------------
# Filler Positions
# ---------------------------------------------------------------------------


class TestFillerPositions:

    def test_positions_include_word_index(self, simple_detector):
        result = simple_detector.detect("The um answer is uh correct")
        fillers = result.filler_positions
        assert len(fillers) >= 2
        # "um" is at index 1, "uh" is at index 4
        um_filler = next((f for f in fillers if f.word == "um"), None)
        uh_filler = next((f for f in fillers if f.word == "uh"), None)
        assert um_filler is not None
        assert uh_filler is not None
        assert um_filler.position == 1
        assert uh_filler.position == 4


# ---------------------------------------------------------------------------
# Custom Filler Words
# ---------------------------------------------------------------------------


class TestCustomFillers:

    def test_custom_filler_words(self):
        detector = FillerDetector(
            context_aware=False,
            filler_words={"right", "okay"},
        )
        result = detector.detect("The answer is correct, right? Okay.")
        assert result.filler_word_count >= 2

    def test_custom_replaces_defaults(self):
        detector = FillerDetector(
            context_aware=False,
            filler_words={"right"},
        )
        # "um" should NOT be detected with custom-only list
        result = detector.detect("Um the answer is right")
        filler_words = [f.word for f in result.filler_positions]
        assert "right" in filler_words


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_same_input_same_output(self, detector):
        transcript = "Um, I think, uh, the answer is, like, dynamic programming."
        r1 = detector.detect(transcript)
        r2 = detector.detect(transcript)
        assert r1.filler_word_count == r2.filler_word_count
        assert r1.filler_rate == r2.filler_rate
