# Audio Analysis Module — Human Testing Guide

## Overview

The `audio/analysis` module is an **internal, stateless** module with **no HTTP endpoints**.
It is consumed programmatically by the parent `audio` module and by the interview orchestrator.

Testing is done via **pytest** and **Python REPL** — not via curl or Postman.

---

## Prerequisites

### 1. Install Dependencies

```bash
# From project root
pip install spacy vaderSentiment
python -m spacy download en_core_web_sm
```

### 2. Verify Installation

```python
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy OK')"
python -c "from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer; print('VADER OK')"
```

---

## Running Tests

### All Unit Tests

```bash
pytest tests/unit/audio/analysis/ -v --tb=short
```

### All Integration Tests

```bash
pytest tests/integration/audio/analysis/ -v --tb=short
```

### Specific Test Files

```bash
# Completeness classifier
pytest tests/unit/audio/analysis/test_completeness_classifier.py -v

# Filler detection
pytest tests/unit/audio/analysis/test_filler_detector.py -v

# Speech rate
pytest tests/unit/audio/analysis/test_speech_rate_analyzer.py -v

# Sentiment analysis
pytest tests/unit/audio/analysis/test_sentiment_analyzer.py -v

# Intent classification
pytest tests/unit/audio/analysis/test_intent_classifier.py -v

# Edge cases
pytest tests/unit/audio/analysis/test_edge_cases.py -v

# Contract validation
pytest tests/unit/audio/analysis/test_contracts.py -v

# Accuracy test (requires test corpus)
pytest tests/unit/audio/analysis/test_completeness_classifier.py::TestAccuracy -v
```

### Coverage Report

```bash
pytest tests/unit/audio/analysis/ tests/integration/audio/analysis/ \
    --cov=app.audio.analysis --cov-report=term-missing
```

---

## Manual REPL Testing

### Completeness Classifier

```python
from app.audio.analysis import CompletenessClassifier

classifier = CompletenessClassifier()

# Complete sentence
result = classifier.evaluate("The answer is dynamic programming.")
print(f"State: {result.speech_state}")      # "complete"
print(f"Confidence: {result.confidence}")    # 0.9

# Incomplete sentence
result = classifier.evaluate("The answer is")
print(f"State: {result.speech_state}")           # "incomplete"
print(f"Reason: {result.incomplete_reason}")      # "missing_complement"

# Empty
result = classifier.evaluate("")
print(f"State: {result.speech_state}")           # "incomplete"
print(f"Reason: {result.incomplete_reason}")      # "empty_transcript"
```

### Filler Detector

```python
from app.audio.analysis import FillerDetector

detector = FillerDetector(context_aware=True)

# With fillers
result = detector.detect("Um, I think the answer is, like, dynamic programming.")
print(f"Count: {result.filler_word_count}")
print(f"Rate: {result.filler_rate:.2f}")
print(f"Positions: {[(f.word, f.position) for f in result.filler_positions]}")

# "like" as verb (NOT filler)
result = detector.detect("I like Python programming.")
print(f"Count: {result.filler_word_count}")  # 0
```

### Speech Rate Analyzer

```python
from app.audio.analysis import SpeechRateAnalyzer
from app.audio.transcription.contracts import TranscriptSegment

analyzer = SpeechRateAnalyzer()

# Simple mode
result = analyzer.analyze("one two three four five", duration_ms=2000)
print(f"WPM: {result.speech_rate_wpm}")  # 150

# Segment mode with pauses
segments = [
    TranscriptSegment(text="Hello world", start_ms=0, end_ms=1000, confidence=0.9),
    TranscriptSegment(text="How are you", start_ms=3000, end_ms=4000, confidence=0.9),
]
result = analyzer.analyze_segments(segments)
print(f"WPM: {result.speech_rate_wpm}")
print(f"Long pauses: {result.long_pause_count}")
print(f"Longest pause: {result.longest_pause_ms}ms")
```

### Sentiment Analyzer

```python
from app.audio.analysis import SentimentAnalyzer

analyzer = SentimentAnalyzer()

# Positive
result = analyzer.analyze("I'm confident this is correct.")
print(f"Score: {result.sentiment_score}")        # > 0
print(f"Confidence: {result.confidence_level}")

# Negative with hesitation
result = analyzer.analyze("I don't know the answer.", filler_rate=0.3)
print(f"Score: {result.sentiment_score}")        # < 0
print(f"Hesitation: {result.hesitation_detected}")  # True
```

### Intent Classifier

```python
from app.audio.analysis import IntentClassifier
from app.audio.analysis.contracts import IntentClassificationRequest

classifier = IntentClassifier()

# Solution attempt
request = IntentClassificationRequest(
    transcript="I would use a recursive algorithm.",
    confidence_score=0.95,
)
result = classifier.classify(request)
print(f"Intent: {result.intent}")                # "ANSWER"
print(f"Solution: {result.contains_solution_attempt}")  # True

# Clarification
request = IntentClassificationRequest(
    transcript="What do you mean by that?",
    confidence_score=0.95,
)
result = classifier.classify(request)
print(f"Intent: {result.intent}")  # "CLARIFICATION"

# Low ASR confidence
request = IntentClassificationRequest(
    transcript="mumble mumble",
    confidence_score=0.3,
)
result = classifier.classify(request)
print(f"Intent: {result.intent}")                    # "INVALID"
print(f"Warning: {result.low_asr_confidence_warning}")  # True
```

---

## Expected Test Results

| Test Suite | Expected Passing | Critical? |
|---|---|---|
| `test_contracts.py` | All | Yes |
| `test_completeness_classifier.py` | All (accuracy > 85%) | Yes |
| `test_filler_detector.py` | All | Yes |
| `test_speech_rate_analyzer.py` | All | Yes |
| `test_sentiment_analyzer.py` | All | Yes |
| `test_intent_classifier.py` | All | Yes |
| `test_edge_cases.py` | All | Yes |
| `test_analysis_pipeline.py` (integration) | All (latency < 500ms) | Yes |

---

## Failure Cases to Verify

| Scenario | Expected Behavior |
|---|---|
| spaCy model not installed | `SpacyModelNotFoundError` raised |
| vaderSentiment not installed | `SentimentEngineError` raised |
| Empty transcript | Valid result with safe defaults |
| None transcript in contract | `ValueError` raised |
| Confidence score out of range | `ValueError` raised |
| All-filler transcript | filler_rate = 1.0, speech_state = "incomplete" |
| 1000+ word transcript | Completes without timeout |

---

## Schema Changes

**None.** This module is stateless — no tables, no migrations.

---

## Architecture Notes

- **No HTTP endpoints** — internal module only
- **No database access** — stateless
- **No API routes to register** — not in router_registry
- **Consumed by:** `audio` parent module, interview orchestrator
- **Dependencies:** spaCy (en_core_web_sm), vaderSentiment
