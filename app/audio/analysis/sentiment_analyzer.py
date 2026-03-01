"""
Sentiment Analyzer

Text-based sentiment analysis using VADER (primary) with TextBlob fallback.

Algorithm:
  1. Run VADER sentiment on transcript text
  2. Map compound score to [-1.0, +1.0] range
  3. Derive confidence level from score magnitude
  4. Detect hesitation from filler rate + negative sentiment
  5. Detect frustration from strongly negative sentiment

Invariants enforced:
  - Deterministic: same input → same output
  - Sentiment score normalised to [-1.0, +1.0]
  - Rule-based only: NO LLM calls
  - Read-only: transcript is NEVER modified

Does NOT:
  - Call any external service
  - Write to any database
  - Use any randomness
"""

from __future__ import annotations

from typing import Optional

from app.shared.observability import get_context_logger

from .contracts import SentimentResult
from .exceptions import SentimentEngineError

logger = get_context_logger(__name__)

# Thresholds
_HESITATION_FILLER_RATE_THRESHOLD = 0.15
_FRUSTRATION_SENTIMENT_THRESHOLD = -0.3
_HIGH_CONFIDENCE_THRESHOLD = 0.6
_MEDIUM_CONFIDENCE_THRESHOLD = 0.3


class SentimentAnalyzer:
    """
    Analyses sentiment of transcript text using VADER.

    Parameters
    ----------
    engine : str
        Sentiment engine to use (default: "vader"). Supports "vader".
    hesitation_threshold : float
        Filler rate above this triggers hesitation detection (default: 0.15).
    """

    def __init__(
        self,
        engine: str = "vader",
        hesitation_threshold: float = _HESITATION_FILLER_RATE_THRESHOLD,
    ) -> None:
        self._engine = engine
        self._hesitation_threshold = hesitation_threshold
        self._analyzer = None

        if engine == "vader":
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

                self._analyzer = SentimentIntensityAnalyzer()
            except ImportError:
                raise SentimentEngineError(
                    engine="vader",
                    detail="vaderSentiment package is not installed. "
                    "Run: pip install vaderSentiment",
                )
        else:
            raise SentimentEngineError(
                engine=engine,
                detail=f"Unsupported sentiment engine: {engine}",
            )

        logger.info(
            "SentimentAnalyzer initialised",
            event_type="audio.analysis.sentiment.init",
            metadata={"engine": engine},
        )

    def analyze(
        self,
        transcript: str,
        filler_rate: Optional[float] = None,
        audio_features: Optional[dict] = None,
    ) -> SentimentResult:
        """
        Analyse sentiment of *transcript*.

        Parameters
        ----------
        transcript : str
            The transcript text to analyse.
        filler_rate : float | None
            Pre-computed filler rate (0.0–1.0). Used for hesitation detection.
        audio_features : dict | None
            Optional acoustic features (reserved for future use).

        Returns
        -------
        SentimentResult
            Frozen result with sentiment score, confidence, and flags.
        """
        if not transcript or not transcript.strip():
            return SentimentResult(
                sentiment_score=0.0,
                confidence_level="low",
                hesitation_detected=False,
                frustration_detected=False,
            )

        # VADER analysis
        scores = self._analyzer.polarity_scores(transcript)
        compound = scores["compound"]  # Already in [-1.0, 1.0]

        # Clamp to [-1.0, 1.0] for safety
        sentiment_score = max(-1.0, min(1.0, compound))

        # Confidence level based on magnitude
        abs_score = abs(sentiment_score)
        if abs_score >= _HIGH_CONFIDENCE_THRESHOLD:
            confidence_level = "high"
        elif abs_score >= _MEDIUM_CONFIDENCE_THRESHOLD:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # Hesitation detection
        hesitation_detected = False
        if filler_rate is not None and filler_rate > self._hesitation_threshold:
            hesitation_detected = True
        # Also detect hesitation from negative uncertainty patterns
        hesitation_keywords = {"don't know", "not sure", "maybe", "i think"}
        lower_transcript = transcript.lower()
        if any(kw in lower_transcript for kw in hesitation_keywords):
            hesitation_detected = True

        # Frustration detection
        frustration_detected = sentiment_score < _FRUSTRATION_SENTIMENT_THRESHOLD

        return SentimentResult(
            sentiment_score=round(sentiment_score, 4),
            confidence_level=confidence_level,
            hesitation_detected=hesitation_detected,
            frustration_detected=frustration_detected,
        )
