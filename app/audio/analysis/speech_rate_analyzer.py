"""
Speech Rate Analyzer

Calculates words-per-minute from transcript and segment timestamps,
excluding pause time from the rate calculation.

Algorithm:
  1. Count words in transcript
  2. Calculate total duration from segments
  3. Identify pauses (gaps between segments)
  4. speech_duration = total_duration - sum(pause_durations)
  5. WPM = (word_count / speech_duration_s) * 60

Invariants enforced:
  - Deterministic: same input → same output
  - Speech rate excludes pause time (configurable)
  - Long pause threshold configurable (default: 1000ms)

Does NOT:
  - Call any external service
  - Write to any database
  - Use any randomness
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from app.shared.observability import get_context_logger

from .contracts import SpeechRateResult

logger = get_context_logger(__name__)


class SpeechRateAnalyzer:
    """
    Calculates speech rate (WPM) and detects long pauses
    from transcript segments.

    Parameters
    ----------
    long_pause_threshold_ms : int
        Pauses longer than this are counted as "long pauses" (default: 1000ms).
    slow_threshold_wpm : int
        Speech below this WPM is flagged as abnormally slow (default: 80).
    fast_threshold_wpm : int
        Speech above this WPM is flagged as abnormally fast (default: 200).
    """

    def __init__(
        self,
        long_pause_threshold_ms: int = 1000,
        slow_threshold_wpm: int = 80,
        fast_threshold_wpm: int = 200,
    ) -> None:
        self._long_pause_threshold_ms = long_pause_threshold_ms
        self._slow_threshold_wpm = slow_threshold_wpm
        self._fast_threshold_wpm = fast_threshold_wpm

        logger.info(
            "SpeechRateAnalyzer initialised",
            event_type="audio.analysis.speech_rate.init",
            metadata={
                "long_pause_threshold_ms": long_pause_threshold_ms,
                "slow_threshold_wpm": slow_threshold_wpm,
                "fast_threshold_wpm": fast_threshold_wpm,
            },
        )

    def analyze(
        self,
        transcript: str,
        duration_ms: int,
    ) -> SpeechRateResult:
        """
        Calculate speech rate from transcript and total duration.

        Simple mode: no segment-level pause analysis.

        Parameters
        ----------
        transcript : str
            The transcript text.
        duration_ms : int
            Total duration in milliseconds.

        Returns
        -------
        SpeechRateResult
        """
        if not transcript or not transcript.strip() or duration_ms <= 0:
            return SpeechRateResult(
                speech_rate_wpm=0.0,
                total_words=0,
                speech_duration_ms=max(0, duration_ms),
                total_duration_ms=max(0, duration_ms),
                long_pause_count=0,
                longest_pause_ms=0,
            )

        words = transcript.strip().split()
        total_words = len(words)
        duration_s = duration_ms / 1000.0
        wpm = (total_words / duration_s) * 60.0 if duration_s > 0 else 0.0

        return SpeechRateResult(
            speech_rate_wpm=round(wpm, 1),
            total_words=total_words,
            speech_duration_ms=duration_ms,
            total_duration_ms=duration_ms,
            long_pause_count=0,
            longest_pause_ms=0,
        )

    def analyze_segments(
        self,
        segments: Sequence,
        exclude_pauses: bool = True,
    ) -> SpeechRateResult:
        """
        Calculate speech rate from word-level transcript segments.

        Segments must have ``text``, ``start_ms``, and ``end_ms`` attributes
        (compatible with ``TranscriptSegment`` from ``audio.transcription``).

        Parameters
        ----------
        segments : Sequence
            Ordered list of transcript segments with timing.
        exclude_pauses : bool
            When True, pause time is excluded from the WPM calculation.

        Returns
        -------
        SpeechRateResult
        """
        if not segments:
            return SpeechRateResult(
                speech_rate_wpm=0.0,
                total_words=0,
                speech_duration_ms=0,
                total_duration_ms=0,
                long_pause_count=0,
                longest_pause_ms=0,
            )

        # Count all words across segments
        total_words = sum(
            len(seg.text.split()) for seg in segments if seg.text.strip()
        )

        # Calculate timing
        first_start = segments[0].start_ms
        last_end = segments[-1].end_ms
        total_duration_ms = last_end - first_start

        # Detect pauses (gaps between consecutive segments)
        pauses: List[int] = []
        for i in range(1, len(segments)):
            gap = segments[i].start_ms - segments[i - 1].end_ms
            if gap > 0:
                pauses.append(gap)

        long_pauses = [p for p in pauses if p >= self._long_pause_threshold_ms]
        total_pause_ms = sum(pauses) if exclude_pauses else 0
        speech_duration_ms = max(0, total_duration_ms - total_pause_ms)
        longest_pause_ms = max(pauses) if pauses else 0

        # Calculate WPM
        speech_duration_s = speech_duration_ms / 1000.0
        wpm = (total_words / speech_duration_s) * 60.0 if speech_duration_s > 0 else 0.0

        return SpeechRateResult(
            speech_rate_wpm=round(wpm, 1),
            total_words=total_words,
            speech_duration_ms=speech_duration_ms,
            total_duration_ms=total_duration_ms,
            long_pause_count=len(long_pauses),
            longest_pause_ms=longest_pause_ms,
        )

    @property
    def slow_threshold_wpm(self) -> int:
        """WPM below this is flagged as abnormally slow."""
        return self._slow_threshold_wpm

    @property
    def fast_threshold_wpm(self) -> int:
        """WPM above this is flagged as abnormally fast."""
        return self._fast_threshold_wpm
