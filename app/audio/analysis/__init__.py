"""
Audio Analysis Module

Extracts behavioural signals from transcripts and audio metadata:
  - Sentence completeness classification (spaCy NLP)
  - Filler word detection (context-aware POS tagging)
  - Speech rate calculation (WPM, pause detection)
  - Sentiment analysis (VADER)
  - Intent classification (keyword-based, deterministic)

This module is **stateless** — it owns no tables and persists nothing.
All analysis results are aggregated by the parent ``audio`` module
and persisted to ``audio_analytics``.

Public API:
  - CompletenessClassifier: Sentence completeness classification
  - FillerDetector: Context-aware filler word detection
  - SpeechRateAnalyzer: Words-per-minute and pause detection
  - SentimentAnalyzer: VADER-based sentiment analysis
  - IntentClassifier: Deterministic utterance intent classification
  - All contract types (Request/Result dataclasses)
  - All exception types
"""

from .completeness_classifier import CompletenessClassifier
from .contracts import (
    CompletenessRequest,
    CompletenessResult,
    ConfidenceLevel,
    FillerDetectionRequest,
    FillerDetectionResult,
    FillerWord,
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentType,
    SemanticDepth,
    SentimentRequest,
    SentimentResult,
    SpeechRateRequest,
    SpeechRateResult,
    SpeechState,
)
from .exceptions import (
    AnalysisValidationError,
    AudioAnalysisError,
    SentimentEngineError,
    SpacyModelNotFoundError,
)
from .filler_detector import FillerDetector
from .intent_classifier import IntentClassifier
from .sentiment_analyzer import SentimentAnalyzer
from .speech_rate_analyzer import SpeechRateAnalyzer

__all__ = [
    # Analyzers
    "CompletenessClassifier",
    "FillerDetector",
    "SpeechRateAnalyzer",
    "SentimentAnalyzer",
    "IntentClassifier",
    # Enums
    "SpeechState",
    "IntentType",
    "SemanticDepth",
    "ConfidenceLevel",
    # Input contracts
    "CompletenessRequest",
    "FillerDetectionRequest",
    "SpeechRateRequest",
    "SentimentRequest",
    "IntentClassificationRequest",
    # Output contracts
    "CompletenessResult",
    "FillerDetectionResult",
    "FillerWord",
    "SpeechRateResult",
    "SentimentResult",
    "IntentClassificationResult",
    # Exceptions
    "AudioAnalysisError",
    "SpacyModelNotFoundError",
    "AnalysisValidationError",
    "SentimentEngineError",
]
